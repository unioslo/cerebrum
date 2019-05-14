#!/bin/env python
# -- coding: utf-8 --

# Copyright 2002-2019 University of Oslo, Norway
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

"""
UiT specific extension to Cerebrum.

Create an csv file that SecuriMaster (access control system) reads
"""
# kbj005 2015.02.26: Copied from Leetah.

from __future__ import unicode_literals

import argparse
import logging
import os
import time

import cereconf
import Cerebrum.logutils
from Cerebrum import Errors
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Utils import Factory
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError

logger = logging.getLogger(__name__)


class SecurimasterExporter(object):
    """Generate cvs export from Cerebrum for the Securimaster system."""

    def __init__(self, db):

        self._pid_to_fnr = None
        self._pnr_to_account = None

        self._db = db

        # Remove
        self._sysx_to_accountid = None
        self._account_to_name = {}
        self._owner_to_account = {}
        self._num_to_const = {}
        self._owner_to_email = {}
        self._worktitle_cache = None
        self._name_cache = None
        self._ou_cache = {}

        self._export_attrs = {}
        self._person_affs = {}

        self._char_separator = ';'
        self._aff_char_separator = '|'

        # Build cache and fetch data from cerebrum
        self.create_cache()
        self.load_cerebrum_data()

    def create_cache(self):
        """Create cache."""
        ac = Factory.get('Account')(self._db)
        p = Factory.get('Person')(self._db)
        co = Factory.get('Constants')(self._db)

        logger.info("Caching fnr's")
        self._pid_to_fnr = p.getdict_fodselsnr()
        logger.info("Creating pnr->acc cache")
        self._pnr_to_account = p.getdict_external_id2primary_account(
            co.externalid_fodselsnr)
        logger.info("Creating names cache")
        self._name_cache = p.getdict_persons_names(
            source_system=co.system_cached,
            name_types=(co.name_first, co.name_last))
        logger.info("Creating work title cache")
        self._worktitle_cache = p.getdict_persons_names(
            source_system=co.system_paga,
            name_types=co.name_work_title)
        logger.info("Start get account names")
        for a in ac.list_names(co.account_namespace):
            self._account_to_name[a['entity_id']] = a['entity_name']
        logger.info("Creating account owner cache")
        for a in ac.list(filter_expired=False):
            self._owner_to_account[a['owner_id']] = a['account_id']
        logger.info("Creating primary email cache")
        for entity_id, email in p.list_primary_email_address(co.entity_person):
            self._owner_to_email[entity_id] = email
        logger.info("Creating constant cache")
        for c in dir(co):
            tmp = getattr(co, c)
            if isinstance(tmp, _CerebrumCode):
                self._num_to_const[int(tmp)] = tmp

        logger.info("Finished cache creation")

    def load_cerebrum_data(self):
        """Load data from cerebrum."""
        logger.info("Fetching affiliations from Cerebrum")
        ou = Factory.get('OU')(self._db)
        sko = Stedkode(self._db)
        co = Factory.get('Constants')(self._db)
        p = Factory.get('Person')(self._db)

        for aff in p.list_affiliations():
            # simple filtering
            aff_status_filter = (co.affiliation_status_student_tilbud,)
            if aff['status'] in aff_status_filter:
                continue

            ou_id = aff['ou_id']
            last_date = "2019-05-03"
            #last_date = aff['last_date'].strftime("%Y-%m-%d")

            if not self._ou_cache.get(ou_id, None):
                ou.clear()
                try:
                    ou.find(ou_id)
                except EntityExpiredError:
                    logger.warn('Expired ou (%s) for person: %s',
                                aff['ou_id'],
                                aff['person_id'])
                    continue
                except Errors.NotFoundError:
                    logger.warn(
                        "Unable to find ou id:%s possible sito ou? these " +
                        "are not to be exported anyways", ou_id)
                    continue
                sko.clear()
                try:
                    sko.find(ou_id)
                except Errors.NotFoundError:
                    logger.warn(
                        "unable to find stedkode for ou:%s. Not exported.",
                        ou_id)
                    continue

                sko_sted = "%02d%02d%02d" % (sko.fakultet, sko.institutt,
                                             sko.avdeling)
                ou_name = ou.get_name_with_language(co.ou_name, co.language_nb,
                                                    default='')
                self._ou_cache[ou_id] = (ou_name, sko_sted)

            sko_name, sko_sted = self._ou_cache[ou_id]
            p_id = aff['person_id']
            aff_stat = self._num_to_const[aff['status']]
            pnr = self._pid_to_fnr.get(p_id, "")

            acc_name = self._pnr_to_account.get(pnr, None)
            if not acc_name:
                acc_id = self._owner_to_account.get(p_id, None)
                acc_name = self._account_to_name.get(acc_id, None)

            primary_mail = self._owner_to_email.get(p_id, '')
            namelist = self._name_cache.get(p_id, None)

            if namelist:
                first_name = namelist.get(int(co.name_first), "")
                last_name = namelist.get(int(co.name_last), "")
            else:
                first_name = ""
                last_name = ""

            worktitlelist = self._worktitle_cache.get(p_id, None)
            if worktitlelist:
                worktitle = worktitlelist.get(int(co.name_work_title), "")
            else:
                worktitle = ""

            if not acc_name:
                logger.warn("No account for %s %s (fnr=%s)(pid=%s)",
                            first_name,
                            last_name,
                            pnr,
                            p_id)
                acc_name = ""

            affstr = "%s::%s::%s::%s" % (
                str(aff_stat), sko_sted, sko_name, last_date)

            self._person_affs.setdefault(p_id, []).append(affstr)

            attrs = [
                acc_name,
                str(pnr),
                first_name,
                last_name,
                worktitle,
                primary_mail
            ]
            if not self._export_attrs.get(acc_name, None):
                self._export_attrs[p_id] = attrs

    def build_export(self, outfile):
        """Build and create the export file."""
        logger.info("Start building export, writing to %s", outfile)
        export = [
            self._char_separator.join((
                '#username',
                'fnr',
                'firstname',
                'lastname',
                'worktitle',
                'primary_mail',
                'affiliation'))
            ]
        for person_id in self._export_attrs:
            attrs = self._export_attrs[person_id]
            affs = self._person_affs.get(person_id)
            aff_str = self._aff_char_separator.join(affs)
            attrs.append(aff_str)
            try:
                export.append(self._char_separator.join(attrs))
            except Exception as m:
                logger.error(
                    "Failed to dump person_id=%s, attrs=%s, reason: %s",
                    person_id,
                    attrs,
                    m)

        logger.info("Starting write export")
        with open(outfile, "w") as fp:
            for row in export:
                fp.write("{}\n".format(row).encode('utf-8'))
        logger.info("Export finished")


def main():
    db = Factory.get('Database')()
    default_outfile = os.path.join(cereconf.DUMPDIR,
                                   "securimaster",
                                   "securimaster_dump_{0}.csv".format(
                                        time.strftime("%Y%m%d")))
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
    exporter = SecurimasterExporter(db)
    exporter.build_export(args.outfile)
    logger.info("Finished generating Securimaster export")


if __name__ == "__main__":
    main()
