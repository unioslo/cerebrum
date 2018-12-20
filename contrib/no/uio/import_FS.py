#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
"""Importerer personer fra FS iht. fs_import.txt."""
from __future__ import unicode_literals


import datetime
import getopt
import sys
from os.path import join as pj

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio.AutoStud import StudentInfo

import cereconf

import mx.DateTime

# Defaults
DEFAULT_PERSONFILE = pj(cereconf.FS_DATA_DIR, "merged_persons.xml")
DEFAULT_STUDIEPROGRAMFILE = pj(cereconf.FS_DATA_DIR, "studieprog.xml")
DEFAULT_EMNEFILE = pj(cereconf.FS_DATA_DIR, "emner.xml")

# Lookup tables for 'studieprogramkode' and 'emnekode' attributes to OU
studieprog2sko = {}
emne2sko = {}

# Lookup table for 'fnr' to person_id (persons already in Cerebrum)
fnr2person_id = {}

# List of affiliations in Cerebrum, and whether the aff has been seen in this
# import. Maps 'entity_id:ou_id:aff_code' -> bool. Use:
# 1. Load: `_load_cere_affs` populates existing affiliations with `True`
# 2. Update: `_process_student_callback` sets seen affiliations to `False`
# 3. Use: `rem_old_aff` cleans up old affiliations
old_aff = {}

# Script options
gen_groups = False  # Generate FS reservation group
include_delete = False  # Run affiliation cleanup

# Stats
no_name = 0  # count persons for which we do not have any name data from FS

# objects
logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
db.cl_init(change_program='import_FS')
co = Factory.get('Constants')(db)

# Vekting av affiliation_status
aff_status_pri_order = [
    co.affiliation_status_student_drgrad,
    co.affiliation_status_student_aktiv,
    co.affiliation_status_student_emnestud,
    co.affiliation_status_student_evu,
    co.affiliation_status_student_privatist,
    # Ikke i bruk p.t.
    #    co.affiliation_status_student_permisjon,
    co.affiliation_status_student_ny,
    co.affiliation_status_student_opptak,
    co.affiliation_status_student_alumni,
    # Ikke i bruk p.t.
    #    co.affiliation_status_student_tilbud,
    co.affiliation_status_student_soker,
]
aff_status_pri_order = dict(
    (int(status), index) for index, status in enumerate(aff_status_pri_order))


def _add_res(entity_id):
    raise NotImplementedError("init_reservation_group not called")


def _rem_res(entity_id):
    raise NotImplementedError("init_reservation_group not called")


def init_reservation_group():
    """ get callbacks to add/remove members in reservation group """
    group = Factory.get('Group')(db)
    group_name = cereconf.FS_GROUP_NAME
    group_desc = cereconf.FS_GROUP_DESC

    try:
        group.find_by_name(group_name)
    except Errors.NotFoundError:
        group.clear()
        ac = Factory.get('Account')(db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        group.populate(ac.entity_id, co.group_visibility_internal,
                       group_name, group_desc)
        group.write_db()

    def add_member(entity_id):
        """ add person to reservation group """
        if not group.has_member(entity_id):
            group.add_member(entity_id)
            return True
        return False

    def remove_member(entity_id):
        """ remove person from reservation group """
        if group.has_member(entity_id):
            group.remove_member(entity_id)
            return True
        return False

    return add_member, remove_member


def _get_sko(a_dict, kfak, kinst, kgr, kinstitusjon=None):
    """ Lookup ou_id from a_dict SKO data """
    ou_cache = _get_sko.cache
    if kinstitusjon is not None:
        institusjon = a_dict[kinstitusjon]
    else:
        institusjon = cereconf.DEFAULT_INSTITUSJONSNR

    key = "-".join((str(institusjon), a_dict[kfak], a_dict[kinst], a_dict[kgr]))
    if key not in ou_cache:
        ou = Factory.get('OU')(db)
        try:
            ou.find_stedkode(int(a_dict[kfak]), int(a_dict[kinst]),
                             int(a_dict[kgr]), institusjon=institusjon)
            ou_cache[key] = ou.entity_id
        except Errors.NotFoundError:
            logger.info("Cannot find an OU in Cerebrum with stedkode: %s", key)
            ou_cache[key] = None
    return ou_cache[key]
_get_sko.cache = {}


def _process_affiliation(aff, aff_status, new_affs, ou):
    # TBD: Should we for example remove the 'opptak' affiliation if we
    # also have the 'aktiv' affiliation?
    if ou is not None:
        new_affs.append((ou, aff, aff_status))


def _get_sted_address(a_dict, k_institusjon, k_fak, k_inst, k_gruppe):
    ou_adr_cache = _get_sted_address.cache
    ou_id = _get_sko(a_dict, k_fak, k_inst, k_gruppe,
                     kinstitusjon=k_institusjon)
    if not ou_id:
        return None
    ou_id = int(ou_id)
    if ou_id not in ou_adr_cache:
        ou = Factory.get('OU')(db)
        ou.find(ou_id)
        rows = ou.get_entity_address(source=co.system_sap,
                                     type=co.address_street)
        if rows:
            ou_adr_cache[ou_id] = {
                'address_text': rows[0]['address_text'],
                'postal_number': rows[0]['postal_number'],
                'city': rows[0]['city']
                }
        else:
            ou_adr_cache[ou_id] = None
            logger.warn("No address for ou_id:%i" % ou_id)
    return ou_adr_cache[ou_id]
_get_sted_address.cache = {}


def _ext_address_info(a_dict, kline1, kline2, kline3, kpost, kland):
    ret = {}
    ret['address_text'] = "\n".join([a_dict.get(f, None)
                                     for f in (kline1, kline2)
                                     if a_dict.get(f, None)])
    postal_number = a_dict.get(kpost, '')
    if postal_number:
        postal_number = "%04i" % int(postal_number)
    ret['postal_number'] = postal_number
    ret['city'] = a_dict.get(kline3, '')
    if len(ret['address_text']) == 1:
        logger.debug("Address might not be complete, "
                     "but we need to cover one-line addresses")
    # we have to register at least the city in order to have a "proper" address
    # this mean that addresses containing only ret['city'] will be imported
    # as well
    if len(ret['address_text']) < 1 and not ret['city']:
        logger.debug("No adress found")
        return None
    return ret


def _calc_address(person_info):
    """Evaluerer personens adresser iht. til flereadresser_spek.txt og
    returnerer en tuple (address_post, address_post_private,
    address_street)"""

    # FS.PERSON     *_hjemsted (1)
    # FS.STUDENT    *_semadr (2)
    # FS.FAGPERSON  *_arbeide (3)
    # FS.DELTAKER   *_job (4)
    # FS.DELTAKER   *_hjem (5)
    rules = [
        ('fagperson', ('_arbeide', '_hjemsted', '_besok_adr')),
        ('aktiv', ('_semadr', '_hjemsted', None)),
        ('emnestud', ('_semadr', '_hjemsted', None)),
        ('evu', ('_job', '_hjem', None)),
        ('drgrad', ('_semadr', '_hjemsted', None)),
        ('privatist_emne', ('_semadr', '_hjemsted', None)),
        ('privatist_studieprogram', ('_semadr', '_hjemsted', None)),
        ('opptak', (None, '_hjemsted', None)),
        ]

    adr_map = {
        '_arbeide': ('adrlin1_arbeide', 'adrlin2_arbeide', 'adrlin3_arbeide',
                     'postnr_arbeide', 'adresseland_arbeide'),
        '_hjemsted': ('adrlin1_hjemsted', 'adrlin2_hjemsted',
                      'adrlin3_hjemsted', 'postnr_hjemsted',
                      'adresseland_hjemsted'),
        '_semadr': ('adrlin1_semadr', 'adrlin2_semadr', 'adrlin3_semadr',
                    'postnr_semadr', 'adresseland_semadr'),
        '_job': ('adrlin1_job', 'adrlin2_job', 'adrlin3_job', 'postnr_job',
                 'adresseland_job'),
        '_hjem': ('adrlin1_hjem', 'adrlin2_hjem', 'adrlin3_hjem',
                  'postnr_hjem', 'adresseland_hjem'),
        '_besok_adr': ('institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')
        }
    logger.debug("Getting address for person %s%s" % (
        person_info['fodselsdato'], person_info['personnr']))
    ret = [None, None, None]
    for key, addr_src in rules:
        if key not in person_info:
            continue
        tmp = person_info[key][0].copy()
        if key == 'aktiv':
            # Henter ikke adresseinformasjon for aktiv, men vi vil
            # alltid ha minst et opptak når noen er aktiv.
            if not any(tag in person_info for tag in (
                    'opptak', 'privatist_studieprogram', 'emnestud')):
                logger.error(
                    "Har aktiv tag uten opptak/privatist/emnestud tag! "
                    "(fnr: %s%s)",
                    person_info['fodselsdato'], person_info['personnr'])
                continue
            tmp = person_info['opptak'][0].copy()
        for i in range(len(addr_src)):
            addr_cols = adr_map.get(addr_src[i], None)
            if (ret[i] is not None) or not addr_cols:
                continue
            if len(addr_cols) == 4:
                ret[i] = _get_sted_address(tmp, *addr_cols)
            else:
                ret[i] = _ext_address_info(tmp, *addr_cols)
    return ret


def _load_cere_aff():
    fs_aff = {}
    person = Factory.get("Person")(db)
    for row in person.list_affiliations(source_system=co.system_fs):
        k = "%s:%s:%s" % (row['person_id'], row['ou_id'], row['affiliation'])
        fs_aff[str(k)] = True
    return(fs_aff)


def rem_old_aff():
    """Deleting the remaining person affiliations that were not processed by the
    import. This is all student affiliations from FS which should not be here
    anymore.

    Note that affiliations are really not removed until 365 days after they are
    not found from FS any more. This is a workaround to prolong the XXX

    """
    logger.info("Removing old FS affiliations")
    person = Factory.get("Person")(db)
    disregard_grace_for_affs = [co.human2constant(x) for x in
                                cereconf.FS_EXCLUDE_AFFILIATIONS_FROM_GRACE]

    for k in old_aff:
        if not old_aff[k]:
            # The affiliation is still present
            continue
        ent_id, ou, affi = (int(x) for x in k.split(':'))
        aff = person.list_affiliations(person_id=ent_id,
                                       source_system=co.system_fs,
                                       affiliation=affi,
                                       ou_id=ou)
        if not aff:
            logger.debug("No affiliation %s for person %s, skipping",
                         co.PersonAffiliation(affi), ent_id)
            continue
        if len(aff) > 1:
            logger.warn("More than one aff for person %s, what to do?", ent_id)
            # if more than one aff we should probably just remove both/all
            continue
        aff = aff[0]
        # Consent removal:
        # We want to check all existing FS affiliations
        # We remove existing reservation consent if all FS-affiliations
        # are about to be removed (if there is not a single active FS aff.)
        logger.debug('Checking for consent removal for person: '
                     '{person_id}'.format(person_id=ent_id))
        fs_affiliations = person.list_affiliations(
            person_id=ent_id,
            source_system=co.system_fs)
        for fs_aff in fs_affiliations:
            aff_str = '{person_id}:{ou_id}:{affiliation_id}'.format(
                person_id=fs_aff['person_id'],
                ou_id=fs_aff['ou_id'],
                affiliation_id=fs_aff['affiliation'])
            logger.debug('Processing affiliation: {aff}={avalue}'.format(
                aff=aff_str,
                avalue=str(old_aff[aff_str])))
            if aff_str not in old_aff:
                # should not happen
                logger.warn('Affiliation {affiliation_id} for person-id '
                            '{person_id} not found in affiliation list'.format(
                                affiliation_id=fs_aff['affiliation'],
                                person_id=fs_aff['person_id']))
                break  # we keep existing consent
            if not old_aff[aff_str]:
                # we found at least one active FS affiliation for this person
                # we will not make any consent changes
                break
        else:
            # we didn't find any active FS affiliations
            logger.debug(
                'No active FS affiliations for person {person_id}'.format(
                    person_id=ent_id))
            if _rem_res(ent_id):
                logger.info(
                    'Removing publish consent for person {person_id} with '
                    'expired FS affiliations'.format(person_id=ent_id))
        # Check date, do not remove affiliation for active students until end
        # of grace period. EVU affiliations should be removed at once.
        grace_days = cereconf.FS_STUDENT_REMOVE_AFF_GRACE_DAYS
        if (aff['last_date'] > (mx.DateTime.now() - grace_days) and
                int(aff['status']) not in disregard_grace_for_affs):
            logger.info("Too fresh aff for person %s, skipping", ent_id)
            continue
        person.clear()
        try:
            person.find(ent_id)
        except Errors.NotFoundError:
            logger.warn("Couldn't find person_id:%s, not removing aff", ent_id)
            continue
        logger.info("Removing aff %s for person=%s, at ou_id=%s",
                    co.PersonAffiliation(affi), ent_id, ou)
        person.delete_affiliation(ou_id=ou,
                                  affiliation=affi,
                                  source=co.system_fs)


def filter_affiliations(affiliations):
    """The affiliation list with cols (ou, affiliation, status) may
    contain multiple status values for the same (ou, affiliation)
    combination, while the db-schema only allows one.  Return a list
    where duplicates are removed, preserving the most important
    status.  """

    # Reverse sort affiliations list according to aff_status_pri_order
    affiliations.sort(
        lambda x, y: (
            aff_status_pri_order.get(int(y[2]), 99) -
            aff_status_pri_order.get(int(x[2]), 99)))
    aktiv = False

    for ou, aff, aff_status in affiliations:
        if (
                aff_status == int(co.affiliation_status_student_aktiv) or
                aff_status == int(co.affiliation_status_student_drgrad) or
                aff_status == int(co.affiliation_status_student_evu)
        ):
            aktiv = True

    ret = {}
    for ou, aff, aff_status in affiliations:
        if aff_status == int(co.affiliation_status_student_emnestud) and aktiv:
            logger.debug("Dropping emnestud-affiliation")
            continue
        else:
            ret[(ou, aff)] = aff_status
    return [(ou, aff, aff_status) for (ou, aff), aff_status in ret.items()]


def register_cellphone(person, person_info):
    """Register person's cell phone number from person_info.

    @param person:
      Person db proxy associated with a newly created/fetched person.

    @param person_info:
      Dict returned by StudentInfoParser.
    """

    def _fetch_cerebrum_contact():
        return [x["contact_value"]
                for x in person.get_contact_info(source=co.system_fs,
                                                 type=co.contact_mobile_phone)]

    # NB! We may encounter several phone numbers. If they do not match, there
    # is nothing we can do but to complain.
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
        if cell_phone in _fetch_cerebrum_contact():
            return

        person.populate_contact_info(co.system_fs)
        person.populate_contact_info(co.system_fs,
                                     co.contact_mobile_phone,
                                     cell_phone)
        logger.debug("Registering cell phone number %s for %s",
                     cell_phone, fnr)
        return
    logger.warn("Person %s has several cell phone numbers. Ignoring them all",
                fnr)


def _get_admission_date_func(for_date, grace_days=0):
    """ Get a admission date filter function to evaluate *new* students.

    For any given date `for_date`, this method returns a filter function that
    tests admission dates. Students with an admission date that passes this
    filter are considered *new* students.

    """
    date_ranges = [
        # Dec. 1 (previous year) - Feb. 1 (same year)
        (
            mx.DateTime.DateTime(for_date.year - 1, mx.DateTime.December, 1),
            mx.DateTime.DateTime(for_date.year, mx.DateTime.February, 1)
        ),
        # June. 1 (same year) - Sept. 1 (same year)
        (
            mx.DateTime.DateTime(for_date.year, mx.DateTime.June, 1),
            mx.DateTime.DateTime(for_date.year, mx.DateTime.September, 1)
        ),
        # Dec 1. (same year) - Feb. 1 (next year)
        (
            mx.DateTime.DateTime(for_date.year, mx.DateTime.December, 1),
            mx.DateTime.DateTime(for_date.year + 1, mx.DateTime.February, 1)
        )
    ]

    for from_date, to_date in date_ranges:
        if from_date <= for_date <= to_date + grace_days:
            return lambda date: (
                isinstance(date, mx.DateTime.DateTimeType) and
                from_date <= date <= to_date + grace_days)

    return lambda date: False


_new_student_filter = _get_admission_date_func(mx.DateTime.now(), grace_days=7)


def _is_new_admission(admission_date_str):
    """ Parse date string and apply `_new_student_filter`. """
    if not isinstance(admission_date_str, basestring):
        return False
    try:
        # parse YYYY-mm-dd string
        date = mx.DateTime.Parser.DateFromString(admission_date_str,
                                                 formats=('ymd1', ))
    except mx.DateTime.Error:
        return False
    return _new_student_filter(date)


def process_person_callback(person_info):
    """Called when we have fetched all data on a person from the xml
    file.  Updates/inserts name, address and affiliation
    information."""
    global no_name
    try:
        fnr = "%06d%05d" % (int(person_info['fodselsdato']),
                            int(person_info['personnr']))
        fnr = fodselsnr.personnr_ok(fnr)
        logger.info("Process %s " % (fnr))
    except fodselsnr.InvalidFnrError:
        logger.warn("Ugyldig fødselsnr: %s" % fnr)
        return

    gender = co.gender_male
    if(fodselsnr.er_kvinne(fnr)):
        gender = co.gender_female

    etternavn = fornavn = None
    birth_date = None
    studentnr = None
    affiliations = []
    address_info = None
    aktiv_sted = []
    aktivemne_sted = []

    # Iterate over all person_info entries and extract relevant data
    if 'aktiv' in person_info:
        for row in person_info['aktiv']:
            if studieprog2sko[row['studieprogramkode']] is not None:
                aktiv_sted.append(
                    int(studieprog2sko[row['studieprogramkode']]))
                logger.debug("App2akrivts")
    if 'emnestud' in person_info:
        for row in person_info['emnestud']:
            if emne2sko[row['emnekode']] is not None:
                aktivemne_sted.append(int(emne2sko[row['emnekode']]))
                logger.debug('Add sko %s based on emne %s',
                             int(emne2sko[row['emnekode']]), row['emnekode'])

    for dta_type in person_info.keys():
        x = person_info[dta_type]
        p = x[0]
        if isinstance(p, str):
            continue
        # Get name
        if dta_type in (
                'fagperson',
                'opptak',
                'tilbud',
                'evu',
                'privatist_emne',
                'privatist_studieprogram',
                'alumni',
                'emnestud', ):
            etternavn = p['etternavn']
            fornavn = p['fornavn']

            if not birth_date and 'dato_fodt' in p:
                birth_date = datetime.datetime.strptime(p['dato_fodt'],
                                                        "%Y-%m-%d %H:%M:%S.%f")

        if 'studentnr_tildelt' in p:
            studentnr = p['studentnr_tildelt']
        # Get affiliations
        if dta_type in ('fagperson',):
            _process_affiliation(co.affiliation_tilknyttet,
                                 co.affiliation_tilknyttet_fagperson,
                                 affiliations,
                                 _get_sko(p,
                                          'faknr',
                                          'instituttnr',
                                          'gruppenr',
                                          'institusjonsnr'))
        elif dta_type in ('opptak', ):
            for row in x:
                subtype = co.affiliation_status_student_opptak
                if studieprog2sko[row['studieprogramkode']] in aktiv_sted:
                    subtype = co.affiliation_status_student_aktiv
                elif row['studierettstatkode'] == 'EVU':
                    subtype = co.affiliation_status_student_evu
                elif row['studierettstatkode'] == 'FULLFØRT':
                    subtype = co.affiliation_status_student_alumni
                elif int(row['studienivakode']) >= 900:
                    subtype = co.affiliation_status_student_drgrad
                elif _is_new_admission(row.get('dato_studierett_tildelt')):
                    subtype = co.affiliation_status_student_ny
                _process_affiliation(co.affiliation_student,
                                     subtype,
                                     affiliations,
                                     studieprog2sko[row['studieprogramkode']])
        elif dta_type in ('emnestud',):
            for row in x:
                subtype = co.affiliation_status_student_emnestud
                # We may have some situations here where students get
                # emnestud and aonther affiliation to the same sko,
                # but this seems to work for now.
                try:
                    sko = emne2sko[row['emnekode']]
                except KeyError:
                    logger.warn("Fant ingen emner med koden %s", p['emnekode'])
                    continue
                if sko in aktiv_sted:
                    subtype = co.affiliation_status_student_aktiv
                _process_affiliation(co.affiliation_student, subtype,
                                     affiliations, sko)
        elif dta_type in ('privatist_studieprogram',):
            _process_affiliation(co.affiliation_student,
                                 co.affiliation_status_student_privatist,
                                 affiliations,
                                 studieprog2sko[p['studieprogramkode']])
        elif dta_type in ('privatist_emne',):
            try:
                sko = emne2sko[p['emnekode']]
            except KeyError:
                logger.warn("Fant ingen emner med koden %s" % p['emnekode'])
                continue
            _process_affiliation(co.affiliation_student,
                                 co.affiliation_status_student_privatist,
                                 affiliations,
                                 sko)
        elif dta_type in ('perm',):
            _process_affiliation(co.affiliation_student,
                                 co.affiliation_status_student_aktiv,
                                 affiliations,
                                 studieprog2sko[p['studieprogramkode']])
        elif dta_type in ('tilbud',):
            for row in x:
                _process_affiliation(co.affiliation_student,
                                     co.affiliation_status_student_tilbud,
                                     affiliations,
                                     studieprog2sko[row['studieprogramkode']])
        elif dta_type in ('evu', ):
            _process_affiliation(co.affiliation_student,
                                 co.affiliation_status_student_evu,
                                 affiliations,
                                 _get_sko(p,
                                          'faknr_adm_ansvar',
                                          'instituttnr_adm_ansvar',
                                          'gruppenr_adm_ansvar'))
        else:
            logger.debug2("No such affiliation type: %s, skipping", dta_type)

    if etternavn is None:
        logger.debug("Ikke noe navn på %s" % fnr)
        no_name += 1
        return

    if not birth_date:
        logger.warn('No birth date registered for studentnr %s', studentnr)

    # TODO: If the person already exist and has conflicting data from
    # another source-system, some mechanism is needed to determine the
    # superior setting.

    new_person = Factory.get('Person')(db)
    if fnr in fnr2person_id:
        new_person.find(fnr2person_id[fnr])

    new_person.populate(birth_date, gender)

    new_person.affect_names(co.system_fs, co.name_first, co.name_last)
    new_person.populate_name(co.name_first, fornavn)
    new_person.populate_name(co.name_last, etternavn)

    if studentnr is not None:
        new_person.affect_external_id(co.system_fs,
                                      co.externalid_fodselsnr,
                                      co.externalid_studentnr)
        new_person.populate_external_id(co.system_fs, co.externalid_studentnr,
                                        studentnr)
    else:
        new_person.affect_external_id(co.system_fs,
                                      co.externalid_fodselsnr)
    new_person.populate_external_id(co.system_fs, co.externalid_fodselsnr, fnr)

    ad_post, ad_post_private, ad_street = _calc_address(person_info)
    for address_info, ad_const in ((ad_post, co.address_post),
                                   (ad_post_private, co.address_post_private),
                                   (ad_street, co.address_street)):
        # TBD: Skal vi slette evt. eksisterende adresse v/None?
        if address_info is not None:
            logger.debug("Populating address %s for %s", ad_const, studentnr)
            new_person.populate_address(co.system_fs, ad_const, **address_info)
    # if this is a new Person, there is no entity_id assigned to it
    # until written to the database.
    try:
        op = new_person.write_db()
    except Exception, e:
        logger.exception("write_db failed for person %s: %s", fnr, e)
        # Roll back in case of db exceptions:
        db.rollback()
        return

    for a in filter_affiliations(affiliations):
        ou, aff, aff_status = a
        new_person.populate_affiliation(co.system_fs, ou, aff, aff_status)
        if include_delete:
            key_a = "%s:%s:%s" % (new_person.entity_id, ou, int(aff))
            if key_a in old_aff:
                old_aff[key_a] = False

    register_cellphone(new_person, person_info)

    op2 = new_person.write_db()
    if op is None and op2 is None:
        logger.info("**** EQUAL ****")
    elif op:
        logger.info("**** NEW ****")
    else:
        logger.info("**** UPDATE ****")

    # Reservations
    if gen_groups:
        should_add = False

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
            _add_res(new_person.entity_id)
        else:
            # The student either hasn't registered an answer to
            # the "Can we publish info about you in the directory"
            # question at all, or has given an explicit "I don't
            # want to appear in the directory" answer.
            _rem_res(new_person.entity_id)
    db.commit()


def usage(exitcode=0):
    print """Usage: import_FS.py [options]

    Goes through the XML files generated by import_from_FS.py and updates the
    students in the database.

    Files:

    -p --person-file        Specify where the person file is located.

    -s --studieprogram-file Specify where the study programs file is located.

    -e --emne-file          Specify where the course file is located.

    Action:

    -g --generate-groups    If set, the group for accept for being published at
                            uio.no gets populated with the students.

    -d --include-delete     If set, old person affiliations are deleted from
                            the students that should not have this anymore.

    Misc:

    -h --help               Show this and quit.
    """
    sys.exit(exitcode)


def main():
    global gen_groups, group
    global old_aff, include_delete
    global _add_res, _rem_res
    opts, args = getopt.getopt(sys.argv[1:], 'p:s:e:gdfh', [
        'person-file=', 'studieprogram-file=',
        'emne-file=', 'generate-groups', 'include-delete', 'help'])

    personfile = DEFAULT_PERSONFILE
    studieprogramfile = DEFAULT_STUDIEPROGRAMFILE
    emnefile = DEFAULT_EMNEFILE
    for opt, val in opts:
        if opt in ('-p', '--person-file'):
            personfile = val
        elif opt in ('-s', '--studieprogram-file'):
            studieprogramfile = val
        elif opt in ('-e', '--emne-file'):
            emnefile = val
        elif opt in ('-g', '--generate-groups'):
            gen_groups = True
        elif opt in ('-d', '--include-delete'):
            include_delete = True
        elif opt in ('-h', '--help'):
            usage()
        else:
            print "Unknown argument: %s" % opt
            usage(1)
    if "system_fs" not in cereconf.SYSTEM_LOOKUP_ORDER:
        print "Check your config, SYSTEM_LOOKUP_ORDER is wrong!"
        sys.exit(1)

    logger.info("Started")
    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        logger.warn("Warning: ENABLE_MKTIME_WORKAROUND is set")

    # Initialize reservation group
    if gen_groups:
        _add_res, _rem_res = init_reservation_group()

    # Build cache data
    for s in StudentInfo.StudieprogDefParser(studieprogramfile):
        studieprog2sko[s['studieprogramkode']] = _get_sko(
            s,
            'faknr_studieansv',
            'instituttnr_studieansv',
            'gruppenr_studieansv')

    for e in StudentInfo.EmneDefParser(emnefile):
        emne2sko[e['emnekode']] = _get_sko(
            e,
            'faknr_reglement',
            'instituttnr_reglement',
            'gruppenr_reglement')

    if include_delete:
        old_aff = _load_cere_aff()

    # create fnr2person_id mapping, always using fnr from FS when set
    person = Factory.get('Person')(db)
    for p in person.list_external_ids(id_type=co.externalid_fodselsnr):
        if co.system_fs == p['source_system']:
            fnr2person_id[p['external_id']] = p['entity_id']
        elif p['external_id'] not in fnr2person_id:
            fnr2person_id[p['external_id']] = p['entity_id']

    # Start import
    StudentInfo.StudentInfoParser(personfile, process_person_callback, logger)

    # Clean old affs
    if include_delete:
        rem_old_aff()

    db.commit()  # note that process_person_callback does commit as well
    logger.info("Found %d persons without name." % no_name)
    logger.info("Completed")


if __name__ == '__main__':
    main()
