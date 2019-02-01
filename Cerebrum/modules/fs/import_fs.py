#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2018 University of Oslo, Norway
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
from __future__ import unicode_literals

import mx
import json
import logging
import datetime
from collections import defaultdict

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio.AutoStud import StudentInfo

import cereconf

# Globals
logger = logging.getLogger(__name__)


class FsImporter(object):
    def __init__(self, gen_groups, include_delete, commit,
                 studieprogramfile, source, rules, adr_map,
                 rule_map=None, reg_fagomr=False,
                 reservation_query=None):
        # Variables passed to/from main
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='import_fs')
        self.co = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.group = Factory.get('Group')(self.db)
        self.no_name = 0

        self.gen_groups = gen_groups
        self.include_delete = include_delete

        self.reg_fagomr = reg_fagomr
        self._init_aff_status_pri_order()
        self.rules = rules
        if rule_map:
            self.rule_map = rule_map
        else:
            self.rule_map = {}
        self.adr_map = adr_map

        if "system_fs" not in cereconf.SYSTEM_LOOKUP_ORDER:
            raise SystemExit("Check cereconf, SYSTEM_LOOKUP_ORDER is wrong!")

        if self.gen_groups:
            self.init_reservation_group()
            self.reservation_query = reservation_query

        if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
            logger.warn("Warning: ENABLE_MKTIME_WORKAROUND is set")

        self.ou_adr_cache = {}
        self.ou_cache = {}
        self._init_studieprog2sko(studieprogramfile)

        self.old_aff = None
        if self.include_delete:
            self.old_aff = self._load_cere_aff()

        self.commit = commit
        self.source = source

    def init_reservation_group(self):
        """ get callbacks to add/remove members in reservation group """
        group_name = cereconf.FS_GROUP_NAME
        group_desc = cereconf.FS_GROUP_DESC

        try:
            self.group.find_by_name(group_name)
        except Errors.NotFoundError:
            self.group.clear()
            ac = Factory.get('Account')(self.db)
            ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self.group.populate(ac.entity_id,
                                self.co.group_visibility_internal,
                                group_name,
                                group_desc)
            self.group.write_db()

    def _load_cere_aff(self):
        fs_aff = {}
        person = Factory.get("Person")(self.db)
        for row in person.list_affiliations(source_system=self.co.system_fs):
            k = "%s:%s:%s" % (row['person_id'],
                              row['ou_id'],
                              row['affiliation'])
            fs_aff[str(k)] = True
        return (fs_aff)

    def _init_studieprog2sko(self, studieprogramfile):
        self.studieprog2sko = {}
        for s in StudentInfo.StudieprogDefParser(studieprogramfile):
            self.studieprog2sko[s['studieprogramkode']] = self._get_sko(
                s, 'faknr_studieansv', 'instituttnr_studieansv',
                'gruppenr_studieansv')

    def _init_aff_status_pri_order(self):
        aff_status_pri_order = [int(x) for x in
                                (  # Most significant first
                                    self.co.affiliation_status_student_aktiv,
                                    self.co.affiliation_status_student_evu)]
        aff_status_pri_order = dict([(aff_status_pri_order[i], i)
                                     for i in
                                     range(len(aff_status_pri_order))])

        self.aff_status_pri_order = aff_status_pri_order

    def _get_sko(self, a_dict, kfak, kinst, kgr, kinstitusjon=None):
        # We cannot ignore institusjon (inst A, sko x-y-z is NOT the same as
        # inst B, sko x-y-z)
        if kinstitusjon is not None:
            institusjon = a_dict[kinstitusjon]
        else:
            institusjon = cereconf.DEFAULT_INSTITUSJONSNR

        key = "-".join((str(institusjon), a_dict[kfak], a_dict[kinst],
                        a_dict[kgr]))
        if key not in self.ou_cache:
            ou = Factory.get("OU")(self.db)
            try:
                ou.find_stedkode(int(a_dict[kfak]), int(a_dict[kinst]),
                                 int(a_dict[kgr]), institusjon=institusjon)
                self.ou_cache[key] = ou.entity_id
            except Errors.NotFoundError:
                logger.warn("Cannot find an OU in Cerebrum with stedkode: %s",
                            key)
                self.ou_cache[key] = None
        return self.ou_cache[key]

    def process_person_callback(self, person_info):
        """Called when we have fetched all data on a person from the xml
        file.  Updates/inserts name, address and affiliation
        information."""
        try:
            fnr = self._get_fnr(person_info)
        except fodselsnr.InvalidFnrError:
            return

        gender = self._get_gender(fnr)

        etternavn, fornavn, studentnr, birth_date, affiliations, aktiv_sted = \
            self._get_person_data(person_info, fnr)

        if etternavn is None:
            logger.debug("Ikke noe navn på %s" % fnr)
            self.no_name += 1
            return

        if not birth_date:
            logger.warn('No birth date registered for studentnr %s', studentnr)

        new_person = self._get_person(fnr, studentnr)

        if self._db_add_person(new_person, birth_date, gender, fornavn,
                               etternavn, studentnr, fnr, person_info,
                               affiliations):
            # Perform following operations only if _db_add_person didn't fail
            if self.reg_fagomr:
                self._register_fagomrade(new_person, person_info)
            if self.gen_groups:
                self._add_reservations(person_info, new_person)

            if self.commit:
                self.db.commit()
            else:
                self.db.rollback()

    def _get_person(self, fnr, studentnr):
        fsids = [(self.co.externalid_fodselsnr, fnr)]
        if studentnr is not None:
            fsids.append((self.co.externalid_studentnr, studentnr))
        person = Factory.get('Person')(self.db)
        try:
            person.find_by_external_ids(*fsids)
        except Errors.NotFoundError:
            pass
        except Errors.TooManyRowsError as e:
            logger.error("Trying to find studentnr %r, "
                         "getting several persons: %r",
                         studentnr, e)
        return person

    def _get_fnr(self, person_info):
        try:
            fnr = fodselsnr.personnr_ok("%06d%05d" % (
                int(person_info['fodselsdato']),
                int(person_info['personnr'])))
            fnr = fodselsnr.personnr_ok(fnr)
            logger.info("Processing %s", fnr)
        except fodselsnr.InvalidFnrError:
            logger.warn("Ugyldig fødselsnr: %s" % fnr)
            raise fodselsnr.InvalidFnrError
        return fnr

    def _get_gender(self, fnr):
        gender = self.co.gender_male
        if fodselsnr.er_kvinne(fnr):
            gender = self.co.gender_female
        return gender

    def _get_person_data(self, person_info, fnr):
        etternavn = None
        fornavn = None
        studentnr = None
        birth_date = None
        affiliations = []
        aktiv_sted = []

        # Iterate over all person_info entries and extract relevant data
        if 'aktiv' in person_info:
            for row in person_info['aktiv']:
                if self.studieprog2sko[row['studieprogramkode']] is not None:
                    aktiv_sted.append(
                        int(self.studieprog2sko[row['studieprogramkode']]))
                    logger.debug("App2akrivts")

        for dta_type in person_info.keys():
            x = person_info[dta_type]
            p = x[0]
            if isinstance(p, str):
                continue
            # Get name
            if dta_type in ('fagperson', 'evu', 'aktiv'):
                etternavn = p['etternavn']
                fornavn = p['fornavn']
            if 'studentnr_tildelt' in p:
                studentnr = p['studentnr_tildelt']
            if not birth_date and 'dato_fodt' in p:
                birth_date = datetime.datetime.strptime(p['dato_fodt'],
                                                        "%Y-%m-%d %H:%M:%S.%f")
            # Get affiliations
            if dta_type in ('fagperson',):
                self._process_affiliation(
                    self.co.affiliation_tilknyttet,
                    self.co.affiliation_status_tilknyttet_fagperson,
                    affiliations,
                    self._get_sko(p, 'faknr', 'instituttnr', 'gruppenr',
                                  'institusjonsnr'))
            elif dta_type in ('aktiv',):
                for row in x:
                    # aktiv_sted is necessary in order to avoid different
                    # affiliation statuses to a same 'stedkode' to be
                    # overwritten e.i. if a person has both affiliations status
                    #  'evu' and aktive to a single stedkode we want to
                    # register the status 'aktive' in cerebrum
                    if self.studieprog2sko[
                            row['studieprogramkode']] is not None:
                        aktiv_sted.append(
                            int(self.studieprog2sko[row['studieprogramkode']]))
                        self._process_affiliation(
                            self.co.affiliation_student,
                            self.co.affiliation_status_student_aktiv,
                            affiliations,
                            self.studieprog2sko[row['studieprogramkode']])
            elif dta_type in ('evu',):
                subtype = self.co.affiliation_status_student_evu
                if self.studieprog2sko[row['studieprogramkode']] in aktiv_sted:
                    subtype = self.co.affiliation_status_student_aktiv
                self._process_affiliation(self.co.affiliation_student,
                                          subtype, affiliations,
                                          self.studieprog2sko[
                                              row['studieprogramkode']])
        # end for-loop
        return (etternavn, fornavn, studentnr, birth_date, affiliations,
                aktiv_sted)

    def _process_affiliation(self, aff, aff_status, new_affs, ou):
        # TBD: Should we for example remove the 'opptak' affiliation if we
        # also have the 'aktiv' affiliation?
        if ou is not None:
            new_affs.append((ou, aff, aff_status))

    def _db_add_person(self, new_person, birth_date, gender, fornavn,
                       etternavn, studentnr, fnr, person_info, affiliations):
        """Fills in the necessary information about the new_person.
        Then the new_person gets written to the database"""
        new_person.populate(birth_date, gender)
        new_person.affect_names(self.co.system_fs, self.co.name_first,
                                self.co.name_last)
        new_person.populate_name(self.co.name_first, fornavn)
        new_person.populate_name(self.co.name_last, etternavn)

        if studentnr is not None:
            new_person.affect_external_id(self.co.system_fs,
                                          self.co.externalid_fodselsnr,
                                          self.co.externalid_studentnr)
            new_person.populate_external_id(self.co.system_fs,
                                            self.co.externalid_studentnr,
                                            studentnr)
        else:
            new_person.affect_external_id(self.co.system_fs,
                                          self.co.externalid_fodselsnr)
        new_person.populate_external_id(self.co.system_fs,
                                        self.co.externalid_fodselsnr,
                                        fnr)

        ad_post, ad_post_private, ad_street = self._calc_address(person_info)
        for address_info, ad_const in ((ad_post, self.co.address_post),
                                       (ad_post_private,
                                        self.co.address_post_private),
                                       (ad_street, self.co.address_street)):
            # TBD: Skal vi slette evt. eksisterende adresse v/None?
            if address_info is not None:
                logger.debug("Populating address %s for %s", ad_const, fnr)
                new_person.populate_address(self.co.system_fs, ad_const,
                                            **address_info)
        # if this is a new Person, there is no entity_id assigned to it
        # until written to the database.
        try:
            op = new_person.write_db()
        except Exception, e:
            logger.exception("write_db failed for person %s: %s", fnr, e)
            # Roll back in case of db exceptions:
            self.db.rollback()
            return False

        affiliations = self._filter_affiliations(affiliations)

        for ou, aff, aff_status in affiliations:
            new_person.populate_affiliation(self.co.system_fs, ou, aff,
                                            aff_status)
            if self.include_delete:
                key_a = "%s:%s:%s" % (new_person.entity_id, ou, int(aff))
                if key_a in self.old_aff:
                    self.old_aff[key_a] = False

        self._register_cellphone(new_person, person_info)

        op2 = new_person.write_db()

        if op is None and op2 is None:
            logger.info("**** EQUAL ****")
        elif op:
            logger.info("**** NEW ****")
        else:
            logger.info("**** UPDATE ****")
        return True

    def _register_cellphone(self, person, person_info):
        """Register person's cell phone number from person_info.

        @param person:
          Person db proxy associated with a newly created/fetched person.

        @param person_info:
          Dict returned by StudentInfoParser.
        """

        def _fetch_cerebrum_contact(co):
            return [x["contact_value"]
                    for x in person.get_contact_info(
                    source=co.system_fs,
                    type=co.contact_mobile_phone)]

        # NB! We may encounter several phone numbers. If they do not match,
        # there is nothing we can do but to complain.
        fnr = "%06d%05d" % (int(person_info["fodselsdato"]),
                            int(person_info["personnr"]))
        phone_selector = "telefonnr_mobil"
        phone_country = "telefonlandnr_mobil"
        phone_region = "telefonretnnr_mobil"
        numbers = set()
        for key in person_info:
            for dct in person_info[key]:
                if phone_selector in dct:
                    phone = (dct.get(phone_region) or '') + dct[phone_selector]
                    if dct.get(phone_country):
                        phone = '+' + dct[phone_country] + phone
                    numbers.add(phone.strip().replace(' ', ''))

        if len(numbers) < 1:
            return
        if len(numbers) == 1:
            cell_phone = numbers.pop()
            # empty string is registered as phone number
            if not cell_phone:
                return

            # No point in registering a number that's already there.
            if cell_phone in _fetch_cerebrum_contact(self.co):
                return

            person.populate_contact_info(self.co.system_fs)
            person.populate_contact_info(self.co.system_fs,
                                         self.co.contact_mobile_phone,
                                         cell_phone)
            logger.debug("Registering cell phone number %s for %s",
                         cell_phone, fnr)
            return
        logger.warn(
            "Person %s has several cell phone numbers. Ignoring them all",
            fnr)

    def _filter_affiliations(self, affiliations):
        """The affiliation list with cols (ou, affiliation, status) may
        contain multiple status values for the same (ou, affiliation)
        combination, while the db-schema only allows one.  Return a list
        where duplicates are removed, preserving the most important
        status.  """
        affiliations.sort(
            lambda x, y: self.aff_status_pri_order.get(int(y[2]), 99) -
            self.aff_status_pri_order.get(int(x[2]), 99))

        ret = {}
        for ou, aff, aff_status in affiliations:
            ret[(ou, aff)] = aff_status
        return [(ou, aff, aff_status) for (ou, aff), aff_status in
                ret.items()]

    def _calc_address(self, person_info):
        """Evaluerer personens adresser iht. til flereadresser_spek.txt og
        returnerer en tuple (address_post, address_post_private,
        address_street)"""
        # FS.PERSON     *_hjemsted (1)
        # FS.STUDENT    *_semadr (2)
        # FS.FAGPERSON  *_arbeide (3)
        # FS.DELTAKER   *_job (4)
        # FS.DELTAKER   *_hjem (5)
        # FS.SOKNAD     *_kontakt(6)
        logger.debug("Getting address for person %s%s",
                     person_info['fodselsdato'], person_info['personnr'])
        ret = [None, None, None]
        for key, addr_src in self.rules:
            if key not in person_info:
                continue
            tmp = person_info[key][0].copy()

            if key in self.rule_map:
                if not self.rule_map[key] in person_info:
                    continue
                tmp = person_info[self.rule_map[key]][0].copy()

            for i in range(len(addr_src)):
                addr_cols = self.adr_map.get(addr_src[i], None)
                if (ret[i] is not None) or not addr_cols:
                    continue
                if len(addr_cols) == 4:
                    ret[i] = self._get_sted_address(tmp, *addr_cols)
                else:
                    ret[i] = self._ext_address_info(tmp, *addr_cols)
        return ret

    def _get_sted_address(self, a_dict, k_institusjon, k_fak, k_inst,
                          k_gruppe):
        ou_id = self._get_sko(a_dict, k_fak, k_inst, k_gruppe,
                              kinstitusjon=k_institusjon)
        if not ou_id:
            return None
        ou_id = int(ou_id)
        if ou_id not in self.ou_adr_cache:
            ou = Factory.get('OU')(self.db)
            ou.find(ou_id)

            rows = ou.get_entity_address(type=self.co.address_street,
                                         source=getattr(self.co, self.source))

            if rows:
                self.ou_adr_cache[ou_id] = {
                    'address_text': rows[0]['address_text'],
                    'postal_number': rows[0]['postal_number'],
                    'city': rows[0]['city']
                }
            else:
                self.ou_adr_cache[ou_id] = None
                logger.warn("No address for %i", ou_id)
        return self.ou_adr_cache[ou_id]

    def _ext_address_info(self, a_dict, kline1, kline2, kline3, kpost, kland):
        ret = {}
        ret['address_text'] = "\n".join([a_dict.get(f, None)
                                         for f in (kline1, kline2)
                                         if a_dict.get(f, None)])
        postal_number = a_dict.get(kpost, '')
        if postal_number:
            postal_number = "%04i" % int(postal_number)
        ret['postal_number'] = postal_number
        ret['city'] = a_dict.get(kline3, '')

        logger.debug('%s,  %s,  %s', ret['address_text'], postal_number,
                     ret['city'])
        if len(ret['address_text']) == 1:
            logger.debug("Address might not be complete, "
                         "but we need to cover one-line addresses")
        # we have to register at least the city in order to have a "proper"
        # address this mean that addresses containing only ret['city'] will be
        # imported as well
        if len(ret['address_text']) < 1 and not ret['city']:
            logger.debug("No address found")
            return None
        return ret

    def _add_reservations(self, person_info, new_person):
        should_add = False
        if self.reservation_query:
            # Method currently used by uia, nih and hiof
            for dta_type in person_info.keys():
                p = person_info[dta_type][0]
                if isinstance(p, str):
                    continue
                # We only fetch the column in these queries
                if dta_type not in self.reservation_query:
                    continue
                # If 'status_reserv_nettpubl' == "N": add to group
                if p.get('status_reserv_nettpubl', "") == "N":
                    should_add = True
                else:
                    should_add = False
        else:
            # Method currently used by uio and nmh. Looks at 'nettpubl'
            # instead of 'status_reserv_nettpubl'.
            if 'nettpubl' in person_info:
                for row in person_info['nettpubl']:
                    if (
                            row.get('akseptansetypekode', "") == "NETTPUBL" and
                            row.get('status_svar', "") == "J"
                    ):
                        should_add = True

        if should_add:
            # The student has explicitly given us permission to be
            # published in the directory.
            self._add_res(new_person.entity_id)
        else:
            # The student either hasn't registered an answer to
            # the "Can we publish info about you in the directory"
            # question at all, or has given an explicit "I don't
            # want to appear in the directory" answer.
            self._rem_res(new_person.entity_id)

    def _add_res(self, entity_id):
        if not self.group.has_member(entity_id):
            self.group.add_member(entity_id)
            logging.debug('Added member %r to group %r', entity_id, self.group)
            return True
        return False

    def _rem_res(self, entity_id):
        if self.group.has_member(entity_id):
            self.group.remove_member(entity_id)
            logging.debug('Removed member %r from group %r', entity_id,
                          self.group)
            return True
        return False

    def rem_old_aff(self):
        """ Remove old affiliations.

        This method loops through the global `old_affs` mapping. The
        `process_person_callback` marks affs as False if they are still present
         in the FS import files.

        For the rest, we check if they are past the
        cereconf.FS_STUDENT_REMOVE_AFF_GRACE_DAYS limit, and remove them if
        they are.
        """

        disregard_grace_for_affs = [
            int(self.co.human2constant(x)) for x in
            cereconf.FS_EXCLUDE_AFFILIATIONS_FROM_GRACE]

        logger.info("Removing old FS affiliations")
        stats = defaultdict(lambda: 0)
        person = Factory.get("Person")(self.db)
        person_ids = set()
        for k in self.old_aff:
            if not self.old_aff[k]:
                # Aff still present in import files
                continue

            person_id, ou_id, aff_id = (int(val) for val in k.split(':'))
            logger.debug("Attempting to remove aff %r (%r)", k, aff_id)
            stats['old'] += 1
            aff = person.list_affiliations(person_id=person_id,
                                           source_system=self.co.system_fs,
                                           affiliation=aff_id,
                                           ou_id=ou_id)
            if not aff:
                logger.warn(
                    'Possible race condition when attempting to remove aff '
                    '{} for {}'.format(aff_id, person_id))
                continue
            if len(aff) > 1:
                logger.warn("More than one aff for person %s, what to do?",
                            person_id)
                # if more than one aff we should probably just remove both/all
                continue
            aff = aff[0]

            self._remove_consent(person, person_id)

            # Check date, do not remove affiliation for active students until
            # end of grace period. Some affiliations should be removed at once
            # for certain institutions.
            grace_days = cereconf.FS_STUDENT_REMOVE_AFF_GRACE_DAYS
            if (aff['last_date'] > (mx.DateTime.now() - grace_days) and
                    int(aff['status']) not in disregard_grace_for_affs):
                logger.debug("Sparing aff (%s) for person_id=%r at ou_id=%r",
                             aff_id, person_id, ou_id)
                stats['grace'] += 1
                continue

            person.clear()
            try:
                person.find(person_id)
            except Errors.NotFoundError:
                logger.warn("Couldn't find person_id:%s, not removing aff",
                            person_id)
                continue
            logger.info("Removing aff %s for person=%s, at ou_id=%s",
                        self.co.PersonAffiliation(aff_id), person_id, ou_id)
            person.delete_affiliation(ou_id=ou_id, affiliation=aff_id,
                                      source=self.co.system_fs)
            stats['delete'] += 1
            person_ids.add(person_id)

        logger.info("Old affs: %d affs on %d persons",
                    stats['old'], len(person_ids))
        logger.info("Affiliations spared: %d", stats['grace'])
        logger.info("Affiliations removed: %d", stats['delete'])

    def _remove_consent(self, person, person_id):
        # Consent removal:
        # We want to check all existing FS affiliations
        # We remove existing reservation consent if all FS-affiliations
        # are about to be removed (if there is not a single active FS aff.)
        logger.debug('Checking for consent removal for person: '
                     '{person_id}'.format(person_id=person_id))
        fs_affiliations = person.list_affiliations(
            person_id=person_id,
            source_system=self.co.system_fs)
        for fs_aff in fs_affiliations:
            aff_str = '{person_id}:{ou_id}:{affiliation_id}'.format(
                person_id=fs_aff['person_id'],
                ou_id=fs_aff['ou_id'],
                affiliation_id=fs_aff['affiliation'])
            logger.debug('Processing affiliation: {aff}={avalue}'.format(
                aff=aff_str,
                avalue=str(self.old_aff[aff_str])))
            if aff_str not in self.old_aff:
                # should not happen
                logger.warn('Affiliation {affiliation_id} for person-id '
                            '{person_id} not found in affiliation list'.format(
                                affiliation_id=fs_aff['affiliation'],
                                person_id=fs_aff['person_id']))
                break  # we keep existing consent
            if not self.old_aff[aff_str]:
                # we found at least one active FS affiliation for this person
                # we will not make any consent changes
                break
        else:
            # we didn't find any active FS affiliations
            logger.debug(
                'No active FS affiliations for person {person_id}'.format(
                    person_id=person_id))
            if self._rem_res(person_id):
                logger.info(
                    'Removing publish consent for person {person_id} with '
                    'expired FS affiliations'.format(person_id=person_id))

    def _register_fagomrade(self, person, person_info):
        """Register 'fagomrade'/'fagfelt' for a person.
        This is stored in trait_fagomrade_fagfelt as a pickled list of strings.
        The trait is not set if no 'fagfelt' is registered.

        @param person:
          Person db proxy associated with a newly created/fetched person.

        @param person_info:
          Dict returned by StudentInfoParser.

        """
        fnr = "%06d%05d" % (int(person_info["fodselsdato"]),
                            int(person_info["personnr"]))

        fagfelt_trait = person.get_trait(trait=self.co.trait_fagomrade_fagfelt)
        fagfelt = []

        # Extract fagfelt from any fagperson rows
        if 'fagperson' in person_info:
            fagfelt = [data.get('fagfelt') for data in person_info['fagperson']
                       if data.get('fagfelt') is not None]
            # Sort alphabetically as the rows are returned in random order
            fagfelt.sort()

        if fagfelt_trait and not fagfelt:
            logger.debug('Removing fagfelt for %s', fnr)
            person.delete_trait(code=self.co.trait_fagomrade_fagfelt)
        elif fagfelt:
            logger.debug('Populating fagfelt for %s', fnr)
            person.populate_trait(
                code=self.co.trait_fagomrade_fagfelt,
                date=mx.DateTime.now(),
                strval=json.dumps(fagfelt))

        person.write_db()
