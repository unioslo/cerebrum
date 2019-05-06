#!/bin/env python
# -- coding: utf-8 --

# Copyright 2002, 2003 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

#
# UiT specific extension to Cerebrum
# Create an csv file that SecuriMaster (access control system) reads
#

# kbj005 2015.02.26: Copied from Leetah.

from __future__ import unicode_literals

import argparse
import os
import time

import cereconf
import Cerebrum.logutils
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Utils import Factory
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError

db = Factory.get('Database')()
ou = Factory.get('OU')(db)
p = Factory.get('Person')(db)
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
logger = Factory.get_logger("console")

CHARSEP = u";"
AFF_CHARSEP = u"|"

pid2fnr = pnr2account = sysx2accountid = account2name = owner2account = num2const = owner2email = worktitle_cache = None


def load_cache():
    global pid2fnr, pnr2account, sysx2accountid, account2name, owner2account, owner2email, worktitle_cache
    global name_cache, num2const

    logger.info("Starting get fnr's")
    pid2fnr = p.getdict_fodselsnr()
    logger.info("Start pnr->acc")
    pnr2account = p.getdict_external_id2primary_account(
        co.externalid_fodselsnr)
    logger.info("Start get names")
    name_cache = p.getdict_persons_names(source_system=co.system_cached,
                                         name_types=(
                                         co.name_first, co.name_last))

    worktitle_cache = p.getdict_persons_names(source_system=co.system_paga,
                                              name_types=(co.name_work_title))

    logger.info("Start get account names")
    account2name = dict()
    owner2account = dict()
    for a in ac.list_names(co.account_namespace):
        account2name[a['entity_id']] = a['entity_name']

    logger.info("Start get account owners")
    for a in ac.list(filter_expired=False):
        owner2account[a['owner_id']] = a['account_id']

    logger.info("Start get primary email")
    owner2email = {}
    for entity_id, email in p.list_primary_email_address(co.entity_person):
        owner2email[entity_id] = email

    logger.info("Start get constants")
    num2const = dict()
    for c in dir(co):
        tmp = getattr(co, c)
        if isinstance(tmp, _CerebrumCode):
            num2const[int(tmp)] = tmp

    ou_cache = dict()
    logger.info("Cache finished")


def load_cb_data():
    global export_attrs, person_affs
    logger.info("Listing affiliations")
    export_attrs = dict()
    person_affs = dict()
    ou_cache = dict()
    for aff in p.list_affiliations():

        # simple filtering
        aff_status_filter = (co.affiliation_status_student_tilbud,)
        if aff['status'] in aff_status_filter:
            continue

        ou_id = aff['ou_id']
        last_date = aff['last_date'].strftime("%Y-%m-%d")
        if not ou_cache.get(ou_id, None):
            ou.clear()

            try:
                ou.find(ou_id)
            except EntityExpiredError:
                logger.warn('Expired ou (%s) for person: %s' % (
                aff['ou_id'], aff['person_id']))
                continue
            except Errors.NotFoundError:
                logger.warn(
                    "Unable to find ou id:%s possible sito ou? these are not to be exported anyways" % ou_id)
                continue
            ou.clear()
            try:
                ou.find(ou_id)
            except Errors.NotFoundError:
                # ou has no stedkode. possibly sito ou. it is not to be exported to securimaster
                logger.warn(
                    "unable to find stedkode for ou:%s. Not exported." % ou_id)
                continue
            sko_sted = "%02d%02d%02d" % (ou.fakultet, ou.institutt,
                                         ou.avdeling)
            ou_name = ou.get_name_with_language(co.ou_name, co.language_nb,
                                                default='')
            ou_cache[ou_id] = (ou_name, sko_sted)
        sko_name, sko_sted = ou_cache[ou_id]

        p_id = aff['person_id']
        aff_stat = num2const[aff['status']]

        pnr = pid2fnr.get(p_id, "")
        acc_name = pnr2account.get(pnr, None)
        if not acc_name:
            acc_id = owner2account.get(p_id, None)
            acc_name = account2name.get(acc_id, None)

        primary_mail = owner2email.get(p_id, '')

        namelist = name_cache.get(p_id, None)
        first_name = last_name = worktitle = ""
        if namelist:
            first_name = namelist.get(int(co.name_first), "")
            last_name = namelist.get(int(co.name_last), "")
        worktitlelist = worktitle_cache.get(p_id, None)
        if worktitlelist:
            worktitle = worktitlelist.get(int(co.name_work_title), "")

        if not acc_name:
            logger.warn("No account for %s %s (fnr=%s)(pid=%s)" % \
                        (first_name, last_name, pnr, p_id))
            acc_name = ""

        affstr = "%s::%s::%s::%s" % (
        str(aff_stat), sko_sted, sko_name, last_date)
        person_affs.setdefault(p_id, list()).append(affstr)

        attrs = []
        attrs.append(acc_name)
        attrs.append(str(pnr))
        attrs.append(first_name)
        attrs.append(last_name)
        attrs.append(worktitle)
        attrs.append(primary_mail)
        if not export_attrs.get(acc_name, None):
            export_attrs[p_id] = attrs
    return export_attrs, person_affs


def build_export(outfile):
    logger.info("Start building export, writing to %s" % outfile)
    export = list()
    export.append(CHARSEP.join((
                               u"#username", u"fnr", u"firstname", u"lastname",
                               u"worktitle", u"primary_mail", u"affiliation")))
    for person_id in export_attrs:
        attrs = export_attrs[person_id]
        affs = person_affs.get(person_id)
        aff_str = AFF_CHARSEP.join(affs)
        attrs.append(aff_str)
        try:
            export.append(CHARSEP.join(attrs))
        except Exception, m:
            logger.error("Failed to dump person_id=%s, attrs=%s, reason: %s" % \
                         (person_id, attrs, m))

    logger.info("Starting write export")
    fh = open(outfile, "w")
    for row in export:
        fh.write("{}\n".format(row).encode('utf-8'))
    # fh.write(u"\n".join(export))
    fh.close()
    logger.info("Export finished")


def main():
    default_outfile = os.path.join(cereconf.DUMPDIR,
                                   "securimaster",
                                   "securimaster_dump_{0}.csv".format(
                                        time.strftime("%Y%m%d"))
                                   )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--outfile',
        dest='outfile',
        default=default_outfile,
        help='The ePhorte XML export file'
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Generating Securimaster export")

    disk_spread = None
    outfile = None

    print(args)
    exit(0)

    load_cache()
    load_cb_data()
    build_export(args.outfile)

    logger.info("Finished generating Securimaster export")


if __name__ == "__main__":
    main()
