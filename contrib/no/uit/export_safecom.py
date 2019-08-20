#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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


# Uit specific extension to Cerebrum

from __future__ import unicode_literals

import argparse
import datetime
import logging
import os
import re

import Cerebrum.logutils
import cereconf

from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Utils import Factory
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)


today_tmp = datetime.datetime.today()
tomorrow_tmp = today_tmp + datetime.timedelta(days=1)
TODAY = today_tmp.strftime("%Y%m%d")
TOMORROW = tomorrow_tmp.strftime("%Y%m%d")

DEFAULT_PAYXML = os.path.join(cereconf.DUMPDIR, "safecom",
                              "safecom_pay_%s.xml" % TODAY)
DEFAULT_TRACKXML = os.path.join(cereconf.DUMPDIR, "safecom",
                                "safecom_track_%s.xml" % TODAY)

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)
ou = Factory.get('OU')(db)


def get_sko(ou_id):
    ou.clear()
    ou.find(ou_id)
    return "%s%s%s" % (str(ou.fakultet).zfill(2),
                       str(ou.institutt).zfill(2),
                       str(ou.avdeling).zfill(2))


get_sko = memoize(get_sko)


def get_ouinfo(ou_id, perspective):
    ou.clear()
    ou.find(ou_id)
    ou_short_name = ou.get_name_with_language(name_variant=co.ou_name_short,
                                              name_language=co.language_nb)
    ou_name = ou.get_name_with_language(name_variant=co.ou_name,
                                        name_language=co.language_nb)
    ou_acronym = ou.get_name_with_language(name_variant=co.ou_name_acronym,
                                           name_language=co.language_nb)
    res = {
        'name': ou_name,
        'short_name': ou_short_name,
        'acronym': ou_acronym,
    }
    acronym_path = [res['acronym']]

    try:
        sted_sko = get_sko(ou_id)
    except Errors.NotFoundError:
        sted_sko = ""
    res['sko'] = sted_sko

    # Find company name for this ou_id by going to parent
    visited = []
    parent_id = ou.get_parent(perspective)
    while True:
        if (parent_id is None) or (parent_id == ou.entity_id):
            res['company'] = ou_name
            break
        ou.clear()
        ou.find(parent_id)
        ou_acronym = ou.get_name_with_language(name_variant=co.ou_name_acronym,
                                               name_language=co.language_nb)
        # Detect infinite loops
        if ou.entity_id in visited:
            raise RuntimeError("DEBUG: Loop detected: %r" % visited)
        visited.append(ou.entity_id)
        acronym_path.append(ou_acronym)
        parent_id = ou.get_parent(perspective)
    acronym_path.reverse()
    res['path'] = ".".join(acronym_path)
    return res


get_ouinfo = memoize(get_ouinfo)


def wash_sitosted(name):
    # removes preceeding and trailing numbers and whitespaces
    # samskipnaden has a habit of putting metadata (numbers) in the name... :(
    washed = re.sub(r"^[0-9 ]+|,|& |[0-9 -.]+$", "", name)
    logger.debug("WASH: '%s'->'%s' " % (name, washed))
    return washed


def get_samskipnadstedinfo(ou_id, perspective):
    res = {}
    ou.clear()
    ou.find(ou_id)
    ou_name = ou.get_name_with_language(name_variant=co.ou_name,
                                        name_language=co.language_nb)
    depname = wash_sitosted(ou.get_name_with_language(co.ou_name_display,
                                                      co.language_nb,
                                                      default=''))
    res['sted'] = depname
    # Find company name for this ou_id by going to parents
    visited = []
    while True:
        parent_id = ou.get_parent(perspective)
        logger.debug("Parent to id=%s is %s" % (ou_id, parent_id))
        if (parent_id is None) or (parent_id == ou.entity_id):
            logger.debug("Root for %s is %s, name is  %s" % (
                ou_id, ou.entity_id, ou_name))
            res['company'] = ou_name
            break
        ou.clear()
        ou.find(parent_id)
        ou_name = ou.get_name_with_language(name_variant=co.ou_name,
                                            # const.language_nb
                                            name_language=co.language_nb)
        logger.debug("Current id=%s, name is %s" % (ou.entity_id, ou_name))
        # Detect infinite loops
        if ou.entity_id in visited:
            raise RuntimeError("DEBUG: Loop detected: %r" % visited)
        visited.append(ou.entity_id)
        parentname = wash_sitosted(ou.get_name_with_language(
            co.ou_name_display, co.language_nb, default=''))
        res.setdefault('parents', []).append(parentname)
    res['acropath'].remove(res['company'])
    return res


get_samskipnadstedinfo = memoize(get_samskipnadstedinfo)


class SafecomExporter:

    def __init__(self, payfile, trackfile):
        self.userfile_pay = payfile
        self.userfile_track = trackfile

        self.pay = []
        self.track = []

        self.export_users = []

        # Initialize cache
        self.ad_accounts = None
        self._account_id_to_owner_id = {}
        self._owner_id_to_account_id = {}
        self._account_name_to_account_id = {}
        self._account_id_to_account_name = {}
        self._account_id_to_account_aff = {}
        self._account_affs = {}
        self._person_affs = {}
        self._cached_names = {}
        self._uname_to_primary_mail = {}
        self._num_to_const = {}

    def create_exports(self):
        self._build_cache()
        self._build_data()
        self._build_xml()

    def _build_cache(self):
        """Create caches."""
        logger.info("Start get constants")
        for c in dir(co):
            tmp = getattr(co, c)
            if isinstance(tmp, _CerebrumCode):
                self._num_to_const[int(tmp)] = tmp

        logger.info("Create AD account cache")
        self.ad_accounts = account.search(
            spread=int(co.spread_uit_ad_account),
            expire_start=TOMORROW)

        logger.info("Build helper translation tables")
        for acct in self.ad_accounts:
            self._account_id_to_owner_id[int(acct['account_id'])] = int(
                acct['owner_id'])
            self._owner_id_to_account_id[int(acct['owner_id'])] = int(
                acct['account_id'])
            self._account_name_to_account_id[acct['name']] = int(
                acct['account_id'])
            self._account_id_to_account_name[int(acct['account_id'])] = acct[
                'name']

        logger.info("Caching account primary affiliations.")
        for row in account.list_accounts_by_type(filter_expired=True,
                                                 primary_only=False,
                                                 fetchall=False):
            self._account_affs.setdefault(row['account_id'], []).append(
                (row['affiliation'], row['ou_id']))

        logger.info("Cache person affiliations")
        self._person_affs = self.list_affiliations()

        self.get_safecom_mode()

        logger.info("Cache person names")
        self._cached_names = person.getdict_persons_names(
            source_system=co.system_cached,
            name_types=(co.name_first, co.name_last))

        logger.info("Retrieving account primaryemailaddrs")
        self._uname_to_primary_mail = account.getdict_uname2mailaddr(
            primary_only=True)

    def get_safecom_mode(self):
        pay_filter = [co.affiliation_status_student_aktiv,
                      co.affiliation_status_student_alumni,
                      co.affiliation_status_student_evu,
                      co.affiliation_status_student_opptak,
                      co.affiliation_status_student_perm,
                      co.affiliation_status_student_privatist,
                      co.affiliation_status_student_sys_x,
                      co.affiliation_status_student_tilbud,
                      co.affiliation_status_flyt_hih_student_aktiv,
                      co.affiliation_status_flyt_hin_student_aktiv,
                      co.affiliation_status_student_emnestud]

        for account, values in self._account_affs.iteritems():
            pay = True
            try:
                account_owner_id = self._account_id_to_owner_id[account]
                for single_aff in values:
                    aff = single_aff[0]
                    ou = single_aff[1]

                    # have account aff and ou. find correct entry in
                    # person_affiliation_source
                    aff_data = self._person_affs.get(account_owner_id, None)
                    if not aff_data:
                        # no valid person_affiliation_source entry (exipred ?)
                        logger.debug(
                            "no valid person_affiliation_source for person:"
                            "%s (expired?)" % account_owner_id)
                        continue
                    for item in aff_data:
                        temp_aff_stat = item['affstatus']
                        temp_ou = item['ou_id']
                        temp_aff = item['affiliation']

                        if temp_aff == aff and ou == temp_ou:
                            if aff == co.affiliation_student:
                                if temp_aff_stat not in pay_filter:
                                    pay = False
                                    continue
                            if aff == co.affiliation_ansatt_sito:
                                pay = False
                                continue
                            if aff == co.affiliation_ansatt:
                                pay = False
                                continue
                            if aff == co.affiliation_tilknyttet:
                                if temp_aff_stat not in pay_filter:
                                    pay = False
                                    continue

                if not pay:
                    self.track.append(account)
                elif pay:
                    self.pay.append(account)
            except KeyError:
                logger.warn("account:%s has no valid owner" % account)
                continue

    def list_affiliations(self):
        person_affs = {}
        skip_source = [co.system_lt]

        for aff in person.list_affiliations():
            # simple filtering
            if aff['source_system'] in skip_source:
                logger.warn(
                    'Skip affiliation, unwanted source system %s' % aff)
                continue
            person_id = aff['person_id']
            ou_id = aff['ou_id']
            source_system = aff['source_system']

            if source_system == co.system_sito:
                perspective_code = co.perspective_sito
            else:
                perspective_code = co.perspective_fs

            sko = path = ''
            try:
                ou_info = get_ouinfo(ou_id, perspective_code)
                sko = ou_info['sko']
                path = ou_info['path']
            except EntityExpiredError:
                logger.error(
                    "person id:%s affiliated to expired ou:%s. Do not export"
                    % (person_id, ou_id))
                continue
            except Errors.NotFoundError:
                logger.debug(
                    ("OU id=%s not found on person %s. DB integrity error " +
                     "(this MAY be caused by parent sito ou not having " +
                     "stedkode).") % (
                        ou_id, person_id))
                # sys.exit(1)

            if source_system == co.system_sito:
                # TODO fix hardcoding!!
                path = "Norges arktiske studentsamskipnad"

            aff_stat = self._num_to_const[aff['status']]
            aff_info = {'affstr': str(aff_stat),
                        'affiliation': aff['affiliation'],
                        'ou_id': ou_id,
                        'affstatus': aff['status'],
                        'sko': sko,
                        'path': path,
                        }
            tmp = person_affs.get(person_id, [])
            if aff_info not in tmp:
                tmp.append(aff_info)
                person_affs[person_id] = tmp
        return person_affs

    def _build_data(self):
        """Fetch and build the user data that will be export."""
        logger.info("Processing cerebrum info...")
        count = 0
        for item in self.ad_accounts:
            count += 1
            if count % 500 == 0:
                logger.info("Processed %d accounts" % count)
            acc_id = item['account_id']
            name = item['name']
            owner_id = item['owner_id']

            account_affiliations = self._account_affs.get(acc_id, None)
            person_affiliations = self._person_affs.get(owner_id, None)

            if account_affiliations is None or person_affiliations is None:
                cost_code = ''
            else:
                primary_aff, primary_ou = account_affiliations[0]
                cost_code = ''
                for aff in person_affiliations:
                    if aff['affiliation'] == primary_aff and \
                            aff['ou_id'] == primary_ou:
                        cost_code = "{0}@{1}".format(aff['affstr'],
                                                     aff['path'])

            if cost_code == '':
                # account in grace to be closed, cannot calculate new status.
                logger.debug("Account %s without affiliations. Do not process"
                             % name)
                continue

            mode = 'Pay' if acc_id in self.pay else 'Track'

            owner_type = item['owner_type']
            namelist = self._cached_names.get(owner_id, None)
            first_name = last_name = ''
            try:
                first_name = namelist.get(int(co.name_first))
                last_name = namelist.get(int(co.name_last))
            except AttributeError:
                if owner_type == co.entity_person:
                    logger.error("Failed to get name for a_id/o_id=%s/%s" %
                                 (acc_id, owner_id))
                else:
                    logger.warn(
                        "No name found for a_id/o_id=%s/%s, ownertype was %s" %
                        (acc_id, owner_id, owner_type))

            primary_mail = self._uname_to_primary_mail.get(item['name'], '')
            entry = {
                'UserLogon': '{0}'.format(name),
                'FullName': '{0} {1}'.format(first_name, last_name),
                'Email': primary_mail,
                'CostCode': cost_code,
                'Mode': mode,
            }
            self.export_users.append(entry)

    def _build_xml(self):
        """Generate the xml files."""
        with AtomicFileWriter(self.userfile_pay, 'wb') as fh_pay, \
                AtomicFileWriter(self.userfile_track, 'wb') as fh_trk:

            logger.info(
                "Start building pay export, writing to %s" % self.userfile_pay)
            xml_pay = xmlprinter(fh_pay,
                                 indent_level=2,
                                 data_mode=True,
                                 input_encoding='utf-8')
            xml_pay.startDocument(encoding='utf-8')
            xml_pay.startElement('UserList')
            logger.info(
                "Start building track export, writing to %s" %
                self.userfile_track)
            xml_trk = xmlprinter(fh_trk,
                                 indent_level=2,
                                 data_mode=True,
                                 input_encoding='utf-8')
            xml_trk.startDocument(encoding='utf-8')
            xml_trk.startElement('UserList')

            for item in self.export_users:
                if item['Mode'] == "Pay":
                    xml_pay.startElement('User')
                    xml_pay.dataElement('UserLogon', item['UserLogon'])
                    xml_pay.dataElement('CostCode', item['CostCode'])
                    xml_pay.dataElement('FullName', item['FullName'])
                    xml_pay.dataElement('Email', item['Email'])
                    xml_pay.endElement('User')
                elif item['Mode'] == "Track":
                    xml_trk.startElement('User')
                    xml_trk.dataElement('UserLogon', item['UserLogon'])
                    xml_trk.dataElement('CostCode', item['CostCode'])
                    xml_trk.dataElement('FullName', item['FullName'])
                    xml_trk.dataElement('Email', item['Email'])
                    xml_trk.endElement('User')
                else:
                    logger.error("MODE invalid: %s" % (item['Mode'],))

            xml_pay.endElement('UserList')
            xml_pay.endDocument()
            xml_trk.endElement('UserList')
            xml_trk.endDocument()
            logger.info("Writing done")


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    # TODO do we write to these or do we read from?
    parser.add_argument('-p',
                        '--payfile',
                        dest='payfile',
                        help='Write Safecom Pay users to file')
    parser.add_argument('-t',
                        '--trackfile',
                        dest='trackfile',
                        help='Write Safecom Track user to file'
                        )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Starting Safecom exports')

    payfile = DEFAULT_PAYXML
    trackfile = DEFAULT_TRACKXML

    if args.payfile:
        payfile = args.payfile

    if args.trackfile:
        trackfile = args.trackfile

    start = datetime.datetime.now()
    worker = SafecomExporter(payfile, trackfile)
    worker.create_exports()
    stop = datetime.datetime.now()
    runtime = stop - start
    logger.info("Started %s ended %s" % (start, stop))
    logger.info("Script running time was %d seconds" % (
        int(runtime.total_seconds())))


if __name__ == '__main__':
    main()
