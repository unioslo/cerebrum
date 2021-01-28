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
"""Uit specific extension to Cerebrum"""

from __future__ import unicode_literals

import argparse
import datetime
import logging
import os
import re
import sys

import cereconf
from Cerebrum import Errors
from Cerebrum import logutils
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Utils import Factory
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.modules.Email import EmailTarget, EmailForward
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError
from Cerebrum.modules.fs.import_from_FS import AtomicStreamRecoder
from Cerebrum.modules.no.uit.Account import UsernamePolicy
from Cerebrum.modules.no.uit.PagaDataParser import PagaDataParserClass
from Cerebrum.utils.date import now, parse_date
from Cerebrum.utils.date_compat import to_mx_format
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)


def wash_sitosted(name):
    # removes preceeding and trailing numbers and whitespaces
    # samskipnaden has a habit of putting metadata (numbers) in the name... :(
    washed = re.sub(r"^[0-9 ]+|,|& |[0-9 -.]+$", "", name)
    return washed


def is_valid_tils_date(t, today=None):
    """
    Check if tils dict is valid according to its start/end dates.

    :param dict t:
        (data > person > tils) object from an uit employee file

    :param date today:
        Check if `t` is valid at given date (default: datetime.date.today())

    :returns bool: True if the tils object is valid according to `today`
    """
    today = today or datetime.date.today()
    dato_fra = parse_date(t["dato_fra"])
    earliest = dato_fra - datetime.timedelta(days=cereconf.PAGA_EARLYDAYS)
    if today < earliest:
        return False
    if t['dato_til'] and today > parse_date(t["dato_til"]):
        return False
    return True


class AdExport(object):

    def __init__(self, userfile, sito_userfile, db):
        self.userfile = userfile
        self.sito_userfile = sito_userfile
        self.db = db
        self.co = Factory.get('Constants')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.ef = EmailForward(self.db)
        self.et = EmailTarget(self.db)
        self.aff_to_stilling_map = dict()
        self.num2const = dict()
        self.userexport = []

    def load_cbdata(self, empfile):

        logger.info("Loading stillingtable")
        self.stillingskode_map = load_stillingstable(self.db)

        logger.info(
            'Generating dict of PAGA persons affiliations and their '
            'stillingskoder, dbh_kat, etc')
        PagaDataParserClass(empfile, self.scan_person_affs)

        logger.info("Loading PagaIDs")
        self.pid2pagaid = dict()
        for row in self.person.search_external_ids(
                id_type=self.co.externalid_paga_ansattnr,
                source_system=self.co.system_paga):
            self.pid2pagaid[row['entity_id']] = row['external_id']

        logger.info("Loading Sito IDs")
        self.pid2sitoid = dict()
        for row in self.person.search_external_ids(
                id_type=self.co.externalid_sito_ansattnr,
                source_system=self.co.system_sito):
            self.pid2sitoid[row['entity_id']] = row['external_id']
        logger.info("Start get constants")
        for c in dir(self.co):
            tmp = getattr(self.co, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
        self.person_affs = self.list_affiliations()
        logger.info("#####")
        logger.info("Cache person names")
        self.cached_names = self.person.getdict_persons_names(
            source_system=self.co.system_cached,
            name_types=(self.co.name_first, self.co.name_last))

        logger.info("Cache AD accounts")
        expire_start = now() + datetime.timedelta(days=1)
        self.ad_accounts = self.account.search(
            spread=int(self.co.spread_uit_ad_account),
            expire_start=expire_start)
        logger.info("Build helper translation tables")
        self.accid2ownerid = dict()
        self.ownerid2accid = dict()
        self.accname2accid = dict()
        self.accid2accname = dict()
        self.accid2accaff = dict()
        for acct in self.ad_accounts:
            self.accid2ownerid[int(acct['account_id'])] = int(acct['owner_id'])
            self.ownerid2accid[int(acct['owner_id'])] = int(acct['account_id'])
            self.accname2accid[acct['name']] = int(acct['account_id'])
            self.accid2accname[int(acct['account_id'])] = acct['name']
        self.account_affs = dict()
        aff_cached = 0
        logger.info("Caching account affiliations.")
        for row in self.account.list_accounts_by_type(filter_expired=True,
                                                      primary_only=False,
                                                      fetchall=False):
            self.account_affs.setdefault(row['account_id'], list()).append(
                (row['affiliation'], row['ou_id']))
            aff_cached += 1
        logger.debug("Cached %d affiliations", aff_cached)

        # quarantines
        logger.info("Loading account quarantines...")
        self.account_quarantines = dict()
        for row in self.account.list_entity_quarantines(
                entity_types=self.co.entity_account,
                quarantine_types=[self.co.quarantine_tilbud,
                                  self.co.quarantine_generell,
                                  self.co.quarantine_slutta]):
            acc_name = self.accid2accname.get(int(row['entity_id']))
            q = self.num2const[int(row['quarantine_type'])]
            self.account_quarantines.setdefault(acc_name, list()).append(q)

        logger.info("Retrieving account emailaddrs")
        self.uname2mail = self.account.getdict_uname2mailaddr(
            primary_only=False)
        logger.info("Retrieving account primaryemailaddrs")
        self.uname2primarymail = self.account.getdict_uname2mailaddr(
            primary_only=True)

        logger.info("Loading email targets")
        self.mailtargetid2entityid = dict()
        for row in self.et.list_email_targets_ext():
            self.mailtargetid2entityid[row['target_id']] = row[
                'target_entity_id']

        logger.info("Retreiving email forwards")
        self.email_forwards = dict()
        self.uname2forwards = dict()
        for row in self.ef.list_email_forwards():
            if row['enable'] == "T":
                e_id = self.mailtargetid2entityid[row['target_id']]
                try:
                    uname = self.accid2accname[e_id]
                except KeyError:
                    continue
                self.uname2forwards[uname] = row['forward_to']

        logger.info("Retrieving contact info (phonenrs and such)")
        self.person2contact = dict()
        for c in self.person.list_contact_info(
                entity_type=self.co.entity_person):
            self.person2contact.setdefault(c['entity_id'], list()).append(c)

        logger.info(
            "Retrieve contact info (phonenrs and such) for account objects")
        # uit account stuff
        self.account2contact = dict()
        # valid uit source systems
        for c in self.person.list_contact_info(
                entity_type=self.co.entity_account):
            self.account2contact.setdefault(c['entity_id'], list()).append(c)

        logger.info("Retreiving person campus loaction")
        self.person2campus = dict()
        for c in self.person.list_entity_addresses(
                entity_type=self.co.entity_person,
                source_system=self.co.system_paga,
                address_type=self.co.address_location):
            self.person2campus.setdefault(c['entity_id'], list()).append(c)
        logger.info("Cache done")

    def list_affiliations(self):
        person_affs = dict()
        skip_source = []
        for aff in self.person.list_affiliations():
            # simple filtering
            aff_status_filter = (self.co.affiliation_status_student_tilbud,)
            if aff['status'] in aff_status_filter:
                continue
            if aff['source_system'] in skip_source:
                logger.warn(
                    'Skip affiliation, unwanted source system %s', aff)
                continue
            p_id = aff['person_id']
            ou_id = aff['ou_id']
            source_system = aff['source_system']
            precedence = aff['precedence']

            if source_system == self.co.system_sito:
                perspective_code = self.co.perspective_sito
                ou_info = self.get_ouinfo_sito(ou_id, perspective_code)
            else:
                perspective_code = self.co.perspective_fs
                ou_info = self.get_ouinfo(ou_id, perspective_code)
                if ou_info is False:
                    # this is is quarantined, continue with next affiliation
                    logger.debug(
                        "ou id:%s is quarantined, continue with "
                        "next affiliation", ou_id)
                    continue
            last_date = aff['last_date'].strftime("%Y-%m-%d")
            try:
                sko = ou_info['sko']
                company = ou_info['company']
            except EntityExpiredError:
                logger.error(
                    "person id:%s affiliated to expired ou:%s. Do not export",
                    p_id, ou_id)
                continue
            except Errors.NotFoundError:
                logger.error(
                    "OU id=%s not found on person %s. DB integrety error!",
                    ou_id, p_id)
                continue
            aff_stat = self.num2const[aff['status']]
            affinfo = {'affstr': str(aff_stat).replace('/', '-'),
                       'sko': sko,
                       'lastdate': last_date,
                       'precedence': precedence,
                       'company': company}

            if aff['source_system'] == self.co.system_paga:
                paga_id = self.pid2pagaid.get(p_id, None)
                try:
                    aux_key = (paga_id, sko, str(aff_stat))
                    tils_info = self.aff_to_stilling_map[aux_key]
                except KeyError:
                    pass
                else:
                    affinfo['stillingskode'] = tils_info['stillingskode']
                    affinfo['stillingstittel'] = tils_info[
                        'stillingstittel_paga']
                    affinfo['prosent'] = tils_info['prosent']
                    affinfo['dbh_kat'] = tils_info['dbh_kat']
                    affinfo['hovedarbeidsforhold'] = tils_info[
                        'hovedarbeidsforhold']
            elif aff['source_system'] == self.co.system_sito:
                # get worktitle from person_name table for samskipnaden
                # Need to look it up  because cached names in script only
                # contains names from cached name variants, and worktitle is
                # not there
                sito_id = self.pid2sitoid.get(p_id, None)
                self.person.clear()
                self.person.find(p_id)
                try:
                    worktitle = self.person.get_name(self.co.system_sito,
                                                     self.co.name_work_title)
                    affinfo['stillingstittel'] = worktitle
                except Errors.NotFoundError:
                    logger.info("Unable to find title for person:%s", sito_id)

                sitosted = self.get_samskipnadstedinfo(ou_id, perspective_code)
                affinfo['company'] = sitosted['company']
                affinfo['sted'] = sitosted['sted']
                affinfo['parents'] = ",".join(sitosted['parents'])
                logger.debug("processing sito person:%s", sito_id)

            tmp = person_affs.get(p_id, list())
            if affinfo not in tmp:
                tmp.append(affinfo)
                person_affs[p_id] = tmp

        return person_affs

    def build_cbdata(self):
        logger.info("Processing cerebrum info...")
        count = 0
        userexport = list()
        for item in self.ad_accounts:
            count += 1
            if count % 500 == 0:
                logger.info("Processed %d accounts", count)
            acc_id = item['account_id']
            name = item['name']
            owner_id = item['owner_id']
            owner_type = item['owner_type']
            expire_date = item['expire_date'].strftime("%Y-%m-%d")
            emails = self.uname2mail.get(name, "")
            forward = self.uname2forwards.get(name, "")
            namelist = self.cached_names.get(owner_id, None)
            first_name = last_name = ""
            try:
                first_name = namelist.get(int(self.co.name_first))
                last_name = namelist.get(int(self.co.name_last))
            except AttributeError:
                if owner_type == self.co.entity_person:
                    logger.error("Failed to get name for a_id/o_id=%s/%s",
                                 acc_id, owner_id)
                else:
                    logger.warn(
                        "No name found for a_id/o_id=%s/%s, ownertype was %s",
                        acc_id, owner_id, owner_type)

            # now to get any email forward addresses
            entry = dict()
            entry['name'] = name
            if UsernamePolicy.is_valid_sito_name(name):
                upndomain = cereconf.SITO_PRIMARY_MAILDOMAIN
            else:
                upndomain = cereconf.INSTITUTION_DOMAIN_NAME
            entry['userPrincipalName'] = "%s@%s" % (name, upndomain)
            entry['givenName'] = first_name
            entry['sn'] = last_name
            entry['expire'] = expire_date
            entry['emails'] = emails
            entry['forward'] = forward
            userexport.append(entry)
        self.userexport = userexport

    def build_xml(self, export_destination='AD', acctlist=None):

        incrmax = 20
        # write to correct outfile
        if export_destination == 'AD':
            userfile = self.userfile
        elif export_destination == 'sito_AD':
            userfile = self.sito_userfile

        if acctlist is not None and len(acctlist) > incrmax:
            logger.error("Too many changes in incremental mode")
            return

        logger.info("Start building export, writing to %s" % userfile)
        stream = AtomicStreamRecoder(userfile,
                                     mode=str('w'),
                                     encoding='utf-8')
        xml = xmlprinter(stream, indent_level=2, data_mode=True,
                         input_encoding='utf-8')
        xml.startDocument(encoding='utf-8')
        xml.startElement('data')
        xml.startElement('properties')
        xml.dataElement('tstamp', to_mx_format(now()))
        if acctlist:
            export_type = "incr"
        else:
            export_type = "fullsync"
        xml.dataElement('type', export_type)
        xml.endElement('properties')

        xml.startElement('users')
        for item in self.userexport:
            if (acctlist is not None) and (item['name'] not in acctlist):
                continue

            if export_destination == 'AD':
                if not any(valid(item['name'])
                           for valid in (UsernamePolicy.is_valid_uit_name,
                                         UsernamePolicy.is_valid_sito_name,
                                         UsernamePolicy.is_valid_guest_name)):
                    logger.error("Username not valid for AD: %s", item['name'])
                    continue
            elif export_destination == 'sito_AD':
                if not UsernamePolicy.is_valid_sito_name(item['name']):
                    # continue to next user if current username
                    # is not valid for sito
                    continue

            xml.startElement('user')
            xml.dataElement('samaccountname', item['name'])
            xml.dataElement('userPrincipalName', item['userPrincipalName'])
            xml.dataElement('sn', item['sn'])
            xml.dataElement('givenName', item['givenName'])
            xml.dataElement('accountExpire', str(item['expire']))
            xml.startElement('proxyAddresses')
            emtmp = list()
            for email in item['emails']:
                email = email.strip()
                attrs = dict()
                primaryemail = self.uname2primarymail.get(item['name'], None)
                if email == primaryemail:
                    attrs['primary'] = "yes"
                if email not in emtmp:
                    xml.dataElement('mail', email, attrs)
                    emtmp.append(email)
            xml.endElement('proxyAddresses')

            accid = self.accname2accid[item['name']]
            contact = self.person2contact.get(self.accid2ownerid[accid])

            #
            # In some cases the person object AND the account object will
            # have different contact information.
            # If an account object contains contact data of the same type as
            # the person object and from the same source,
            # the account contact data will superseede the person object
            # contact data of that type.
            # To facilitate this, we will parse the person2contact dict and
            # account2contact dict and replace
            # the relevant contact data in the person2contact dict.
            # If the account object contains contact data not in contact list,
            # the relevant data will be appended to the contact list.
            # The person2contact dict will then be used when writing the xml
            # file.
            #
            contact_account = self.account2contact.get(accid)
            if contact and contact_account:
                new_contact = {}
                for a in contact_account:
                    already_exists = False
                    replaced = False
                    for c in contact:
                        if (a['contact_type'] == c['contact_type'] and
                                a['source_system'] == c['source_system']):
                            already_exists = True
                            if not any(d['contact_value'] == a['contact_value']
                                       for d in contact):
                                logger.debug("replace:%s with: %s",
                                             c['contact_value'],
                                             a['contact_value'])
                                c['contact_value'] = a['contact_value']
                                replaced = True
                    if already_exists is False and replaced is False:
                        new_contact.update(a)

                if len(new_contact) > 0:
                    contact.append(new_contact)

            # get campus information
            campus = self.person2campus.get(self.accid2ownerid[accid])
            if campus:
                for c in campus:
                    campus_name = str(c['address_text'].encode('utf-8'))
                    xml.dataElement('l', str(campus_name))
            if item['forward'] != '':
                xml.dataElement('targetAddress', str(item['forward']))
            if contact:
                xml.startElement('contactinfo')
                for c in contact:
                    source = str(
                        self.co.AuthoritativeSystem(c['source_system']))
                    ctype = str(self.co.ContactInfo(c['contact_type']))
                    xml.emptyElement('contact',
                                     {'source': source,
                                      'type': ctype,
                                      'pref': str(c['contact_pref']),
                                      'value': str(
                                          c['contact_value'].encode('utf-8'))
                                      })
                xml.endElement('contactinfo')

            person_affs = self.person_affs.get(self.accid2ownerid[accid],
                                               list())
            account_affs = self.account_affs.get(accid, list())
            resaffs = list()
            for person_aff in person_affs:
                for acc_aff, ou_id in account_affs:
                    paff = person_aff['affstr'].split('-')[
                        0]  # first elment in "ansatt-123456"
                    aaff = str(self.num2const[acc_aff])
                    if paff == aaff:
                        person_aff['affstr'] = person_aff['affstr'].replace(
                            'sys_x-ansatt', 'sys_xansatt')
                        resaffs.append(person_aff)
                        break  # leave inner for loop
                    else:
                        pass
            if resaffs:
                # Sort the affiliations by precedence and delete the precedence
                # key before writing to file. To accomplish this we have to
                # make copies of the entries in the list, otherwise they still
                # point to the dicts in the old list and we risk removing the
                # precedence key from an affiliation that may be used later.
                xml.startElement('affiliations')
                for aff in sorted(resaffs,
                                  key=lambda row: row.get('precedence', 999)):
                    # dumps content of dict as xml attributes
                    # skip precedence key
                    xml.emptyElement(
                        'aff',
                        dict((k, aff[k]) for k in aff if k != 'precedence')
                    )
                xml.endElement('affiliations')

            quarantines = self.account_quarantines.get(item['name'])

            if quarantines:
                quarantines = self.sort_quarantines(quarantines)
                xml.startElement('quarantines')
                for q in quarantines:
                    xml.emptyElement('quarantine', {'qname': str(q)})
                xml.endElement('quarantines')

            xml.endElement('user')
        xml.endElement('users')
        xml.endElement('data')
        xml.endDocument()
        stream.close()

    def scan_person_affs(self, person):

        pagaid = person['ansattnr']

        for t in person.get('tils', ()):
            if not is_valid_tils_date(t):
                continue

            stedkode = "%s%s%s" % (t['fakultetnr_utgift'].zfill(2),
                                   t['instituttnr_utgift'].zfill(2),
                                   t['gruppenr_utgift'].zfill(2))

            if t['hovedkategori'] == 'TEKN':
                tilknytning = self.co.affiliation_status_ansatt_tekadm
            elif t['hovedkategori'] == 'ADM':
                tilknytning = self.co.affiliation_status_ansatt_tekadm
            elif t['hovedkategori'] == 'VIT':
                tilknytning = self.co.affiliation_status_ansatt_vitenskapelig
            else:
                logger.warning("Unknown hovedkat: %s", t['hovedkategori'])
                continue

            pros = "%2.2f" % float(t['stillingsandel'])

            # Looking up stillingstittel and dbh_kat from DB
            stillingskode = t['stillingskode']
            tmp = self.stillingskode_map.get(stillingskode, None)
            if tmp:
                stillingstittel = tmp['stillingstittel']
                dbh_kat = tmp['stillingstype']
            else:
                # default to fileinfo
                stillingstittel = t['tittel']
                dbh_kat = t['dbh_kat']

            hovedarbeidsforhold = ''
            if 'hovedarbeidsforhold' in t:
                hovedarbeidsforhold = t['hovedarbeidsforhold']

            aux_key = (pagaid, stedkode, str(tilknytning))
            aux_val = {'stillingskode': stillingskode,
                       'stillingstittel_paga': t['tittel'],
                       'stillingstittel': stillingstittel,
                       'prosent': pros,
                       'dbh_kat': dbh_kat,
                       'hovedarbeidsforhold': hovedarbeidsforhold}
            self.aff_to_stilling_map[aux_key] = aux_val

    @memoize
    def get_samskipnadstedinfo(self, ou_id, perspective):
        res = dict()
        self.ou.clear()
        self.ou.find(ou_id)
        depname = wash_sitosted(self.ou.get_name_with_language(
            name_variant=self.co.ou_name_display,
            name_language=self.co.language_nb))

        res['sted'] = depname
        # Find company name for this ou_id by going to parents
        visited = []
        while True:
            parent_id = self.ou.get_parent(perspective)
            if (parent_id is None) or (parent_id == self.ou.entity_id):
                res['company'] = self.ou.get_name_with_language(
                    name_variant=self.co.ou_name,
                    name_language=self.co.language_nb)
                break
            self.ou.clear()
            self.ou.find(parent_id)
            # Detect infinite loops
            if self.ou.entity_id in visited:
                raise RuntimeError("DEBUG: Loop detected: %r" % visited)
            visited.append(self.ou.entity_id)
            parentname = wash_sitosted(self.ou.get_name_with_language(
                name_variant=self.co.ou_name_display,
                name_language=self.co.language_nb))
            res.setdefault('parents', list()).append(parentname)
        res['parents'].remove(res['company'])
        return res

    def sort_quarantines(self, quarantines):
        """ Sort all quarantines and return the one with the lowest number

        As of now the different quarantines and their order are
        slutta : 1
        generell: 2
        tilbud : 3
        """
        if self.co.quarantine_slutta in quarantines:
            return [self.co.quarantine_slutta]
        elif self.co.quarantine_generell in quarantines:
            return [self.co.quarantine_generell]
        elif self.co.quarantine_tilbud in quarantines:
            return [self.co.quarantine_tilbud]
        else:
            logger.warn("unknown quarantine:%s", quarantines)
            return -1

    @memoize
    def get_ouinfo_sito(self, ou_id, perspective):
        self.ou.clear()
        self.ou.find(ou_id)

        res = dict()
        res['name'] = self.ou.get_name_with_language(self.co.ou_name,
                                                     self.co.language_nb)
        res['short_name'] = self.ou.get_name_with_language(
            self.co.ou_name_short, self.co.language_nb)
        res['acronym'] = self.ou.get_name_with_language(
            self.co.ou_name_acronym, self.co.language_nb)

        sted_sko = ""
        res['sko'] = sted_sko
        # Find company name for this ou_id by going to parent
        visited = []
        parent_id = self.ou.get_parent(perspective)
        while True:
            if (parent_id is None) or (parent_id == self.ou.entity_id):
                res['company'] = self.ou.get_name_with_language(
                    self.co.ou_name, self.co.language_nb)
                break
            self.ou.clear()
            self.ou.find(parent_id)
            # Detect infinite loops
            if self.ou.entity_id in visited:
                raise RuntimeError("DEBUG: Loop detected: %r" % visited)
            visited.append(self.ou.entity_id)
            parent_id = self.ou.get_parent(perspective)
        return res

    @memoize
    def get_ouinfo(self, ou_id, perspective):

        self.ou.clear()
        self.ou.find(ou_id)

        # Determine if OU is quarantined
        if self.ou.get_entity_quarantine(qtype=self.co.quarantine_ou_notvalid):
            return False

        res = dict()
        res['name'] = self.ou.get_name_with_language(self.co.ou_name,
                                                     self.co.language_nb)
        try:
            res['short_name'] = self.ou.get_name_with_language(
                self.co.ou_name_short, self.co.language_nb)
        except Errors.NotFoundError:
            res['short_name'] = ""
        try:
            res['acronym'] = self.ou.get_name_with_language(
                self.co.ou_name_acronym, self.co.language_nb)
        except Errors.NotFoundError:
            res['acronym'] = ""
        self.ou.clear()

        try:
            self.ou.find(ou_id)
            sted_sko = u'{:02}{:02}{:02}'.format(self.ou.fakultet,
                                                 self.ou.institutt,
                                                 self.ou.avdeling)

        except Errors.NotFoundError:
            sted_sko = ""
        res['sko'] = sted_sko
        # Find company name for this ou_id by going to parent
        visited = []
        parent_id = self.ou.get_parent(perspective)
        while True:
            if (parent_id is None) or (parent_id == self.ou.entity_id):
                res['company'] = self.ou.get_name_with_language(
                    self.co.ou_name, self.co.language_nb)
                break
            self.ou.clear()
            self.ou.find(parent_id)
            logger.debug("Lookup returned: id=%s", self.ou.entity_id)
            # Detect infinite loops
            if self.ou.entity_id in visited:
                raise RuntimeError("DEBUG: Loop detected: %r" % visited)
            visited.append(self.ou.entity_id)
            parent_id = self.ou.get_parent(perspective)
        return res


def load_stillingstable(db):
    sql = """
        SELECT stillingskode,stillingstittel,stillingstype
        FROM [:table schema=cerebrum name=person_stillingskoder]
        """
    stillingskode_map = dict()
    for row in db.query(sql, dict()):
        stillingskode_map[str(row['stillingskode'])] = {
            'stillingstittel': row['stillingstittel'],
            'stillingstype': row['stillingstype']
        }
    return stillingskode_map


default_sito_user_file = os.path.join(
    sys.prefix, 'var/cache/AD',
    'sito_ad_export_{}.xml'.format(datetime.date.today().strftime('%Y-%m-%d')))
default_user_file = os.path.join(
    sys.prefix, 'var/cache/AD',
    'ad_export_{}.xml'.format(datetime.date.today().strftime('%Y-%m-%d')))

default_employees_file = os.path.join(
    sys.prefix, 'var/cache/employees',
    'paga_persons_{}.xml'.format(datetime.date.today().strftime('%Y-%m-%d')))


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-i', '--in',
        dest='infile',
        default=default_employees_file,
        help='Read employee data from %(metavar)s (%(default)s)',
        metavar='<file>',
    )
    parser.add_argument(
        '-o', '--out',
        dest='outfile',
        default=default_user_file,
        help='Write AD data to %(metavar)s (%(default)s)',
        metavar='<file>',
    )
    parser.add_argument('-a', '--account',
                        default=None,
                        help='export single account. NB DOES NOT WORK!'
                        )
    parser.add_argument('-t', '--type',
                        default='fullsync',
                        help='fullsync or incr (use only fullsync)')
    parser.add_argument('-s', '--export-sito',
                        metavar='<filename>',
                        nargs='?',
                        action='store',
                        dest='export_sito',
                        const=default_sito_user_file,
                        default='',
                        help='optional export filename',
                        )

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    if args.type == "incr":
        acctlist = args.account.split(",")
    else:
        acctlist = None

    start = datetime.datetime.now()
    db = Factory.get('Database')()

    export = AdExport(args.outfile, args.export_sito, db)
    export.load_cbdata(args.infile)
    export.build_cbdata()
    export.build_xml('AD', acctlist)
    if args.export_sito:
        # generate separate sito export file
        export.build_xml('sito_AD', acctlist)

    stop = datetime.datetime.now()
    logger.debug("Started at=%s, ended at=%s",
                 start.isoformat(), stop.isoformat())
    logger.debug('Script used %f seconds', (stop - start).total_seconds())
    logger.info('Wrote ad data to filename=%r', args.outfile)
    if args.export_sito:
        logger.info('Wrote ad data for sito to filename=%r', args.export_sito)
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
