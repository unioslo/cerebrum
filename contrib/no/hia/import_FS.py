#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from os.path import join as pj

import sys
import getopt
import mx

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.modules.no import fodselsnr
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.AutoStud import StudentInfo

default_personfile = pj(cereconf.FS_DATA_DIR, "merged_persons.xml")
default_studieprogramfile = pj(cereconf.FS_DATA_DIR, "studieprogrammer.xml")
group_name = cereconf.FS_GROUP_NAME
group_desc = cereconf.FS_GROUP_DESC

# Global names used. Declared here, set elsewhere
co = None
db = None
group = None
logger = None
old_aff = None
include_delete = None
gen_groups = None


studieprog2sko = {}
ou_cache = {}
ou_adr_cache = {}
no_name = 0  # count persons for which we do not have any name data from FS

"""Importerer personer fra FS iht. fs_import.txt."""


def _add_res(entity_id):
    if not group.has_member(entity_id):
        group.add_member(entity_id)


def _rem_res(entity_id):
    if group.has_member(entity_id):
        group.remove_member(entity_id)


def _get_sted_address(a_dict, k_institusjon, k_fak, k_inst, k_gruppe):
    ou_id = _get_sko(a_dict, k_fak, k_inst, k_gruppe,
                     kinstitusjon=k_institusjon)
    if not ou_id:
        return None
    ou_id = int(ou_id)
    if ou_id not in ou_adr_cache:
        ou = Factory.get('OU')(db)
        ou.find(ou_id)
        rows = ou.get_entity_address(source=co.system_lt,
                                     type=co.address_street)
        if rows:
            ou_adr_cache[ou_id] = {
                'address_text': rows[0]['address_text'],
                'postal_number': rows[0]['postal_number'],
                'city': rows[0]['city']
                }
        else:
            ou_adr_cache[ou_id] = None
            logger.warn("No address for %i", ou_id)
    return ou_adr_cache[ou_id]


def _get_sko(a_dict, kfak, kinst, kgr, kinstitusjon=None):
    key = "-".join((a_dict[kfak], a_dict[kinst], a_dict[kgr]))
    if key not in ou_cache:
        ou = Factory.get('OU')(db)
        if kinstitusjon is not None:
            institusjon = a_dict[kinstitusjon]
        else:
            institusjon = cereconf.DEFAULT_INSTITUSJONSNR
        try:
            ou.find_stedkode(int(a_dict[kfak]), int(a_dict[kinst]),
                             int(a_dict[kgr]), institusjon=institusjon)
            ou_cache[key] = ou.entity_id
        except Errors.NotFoundError:
            logger.info("Cannot find an OU in Cerebrum with stedkode: %s", key)
            ou_cache[key] = None
    return ou_cache[key]


def _process_affiliation(aff, aff_status, new_affs, ou):
    # TBD: Should we for example remove the 'opptak' affiliation if we
    # also have the 'aktiv' affiliation?
    if ou is not None:
        new_affs.append((ou, aff, aff_status))


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
        logger.debug("Address might not be complete, but we need to cover "
                     "one-line addresses")
    # we have to register at least the city in order to have a "proper" address
    # this mean that addresses containing only ret['city'] will be imported as
    # well
    if len(ret['address_text']) < 1 and not ret['city']:
        logger.debug("No address available")
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
    # FS.SOKNAD     *_kontakt(6)
    rules = [
        ('tilbud', ('_kontakt', '_hjemsted', None)),
        ('aktiv', ('_semadr', '_hjemsted', None)),
        ('evu', ('_job', '_hjem', None)),
        ('privatist_studieprogram', ('_semadr', '_hjemsted', None)),
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
        '_kontakt': ('adrlin1_kontakt', 'adrlin2_kontakt', 'adrlin3_kontakt',
                     'postnr_kontakt', 'adresseland_kontakt'),
        '_besok_adr': ('institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')
        }

    ret = [None, None, None]
    for key, addr_src in rules:
        if key not in person_info:
            continue
        tmp = person_info[key][0].copy()
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
    person = Person.Person(db)  # ?!?
    for row in person.list_affiliations(source_system=co.system_fs):
        k = "%s:%s:%s" % (row['person_id'], row['ou_id'], row['affiliation'])
        fs_aff[str(k)] = True
    return(fs_aff)


def rem_old_aff():
    """Remove the remaining person affiliations that were not processed by the
    import. This is all student affiliations from FS which should not be here
    anymore.

    Note that affiliations might not be removed until after a defined grace
    period, as defined in L{cereconf.FS_STUDENT_REMOVE_AFF_GRACE_DAYS}

    """
    logger.info("Removing old FS affiliations")
    person = Factory.get("Person")(db)
    for k, v in old_aff.iteritems():
        if not v:
            continue
        ent_id, ou, affi = (int(x) for x in k.split(':'))
        aff = person.list_affiliations(person_id=ent_id,
                                       source_system=co.system_fs,
                                       affiliation=affi, ou_id=ou)
        if not aff:
            logger.debug("No affiliation %s for person %s, skipping",
                         co.PersonAffiliation(affi), ent_id)
            continue
        if len(aff) > 1:
            logger.warn("More than one aff for person %s, what to do?", ent_id)
            # if more than one aff we should probably just remove both/all
            continue
        aff = aff[0]

        # Check date, do not remove affiliation for active students until end of
        # grace period. EVU affiliations should be removed at once.
        grace_days = cereconf.FS_STUDENT_REMOVE_AFF_GRACE_DAYS
        if (aff['last_date'] > (mx.DateTime.now() - grace_days) and
                int(aff['status']) != int(co.affiliation_status_student_evu)):
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
        person.delete_affiliation(ou_id=ou, affiliation=affi,
                                  source=co.system_fs)


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


def process_person_callback(person_info):
    """Called when we have fetched all data on a person from the xml
    file.  Updates/inserts name, address and affiliation
    information."""
    global no_name
    try:
        fnr = fodselsnr.personnr_ok("%06d%05d" % (
            int(person_info['fodselsdato']),
            int(person_info['personnr'])))
        fnr = fodselsnr.personnr_ok(fnr)
        logger.info("Processing %s", fnr)

        (year, mon, day) = fodselsnr.fodt_dato(fnr)
        if (year < 1970
                and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
            # Seems to be a bug in time.mktime on some machines
            year = 1970
    except fodselsnr.InvalidFnrError:
        logger.warn(u"Ugyldig f�dselsnr for: %s",
                    person_info['fodselsdato'])
        return

    gender = co.gender_male
    if(fodselsnr.er_kvinne(fnr)):
        gender = co.gender_female

    etternavn = fornavn = None
    studentnr = None
    affiliations = []
    address_info = None
    aktiv_sted = []
    # Iterate over all person_info entries and extract relevant data
    for dta_type in person_info.keys():
        x = person_info[dta_type]
        p = x[0]
        if isinstance(p, str):
            continue
        if dta_type not in ('tilbud', 'eksamen', 'evu'):
            if 'studentnr_tildelt' in p:
                studentnr = p['studentnr_tildelt']
            else:
                logger.info("\n%s mangler studentnr!", fnr)
        # Get name
        if dta_type in ('aktiv', 'tilbud', 'evu', 'privatist_studieprogram', ):
            etternavn = p['etternavn']
            fornavn = p['fornavn']
        # Get address
        if address_info is None:
            if dta_type in ('aktiv', 'privatist_studieprogram', ):
                address_info = _ext_address_info(
                    p,
                    'adrlin1_semadr', 'adrlin2_semadr',
                    'adrlin3_semadr', 'postnr_semadr',
                    'adresseland_semadr')
                if address_info is None:
                    address_info = _ext_address_info(
                        p,
                        'adrlin1_hjemsted', 'adrlin2_hjemsted',
                        'adrlin3_hjemsted', 'postnr_hjemsted',
                        'adresseland_hjemsted')
            elif dta_type in ('evu',):
                address_info = _ext_address_info(
                    p, 'adrlin1_hjem',
                    'adrlin2_hjem', 'adrlin3_hjem', 'postnr_hjem',
                    'adresseland_hjem')
                if address_info is None:
                    address_info = _ext_address_info(
                        p,
                        'adrlin1_hjemsted', 'adrlin2_hjemsted',
                        'adrlin3_hjemsted', 'postnr_hjemsted',
                        'adresseland_hjemsted')
            elif dta_type in ('tilbud',):
                address_info = _ext_address_info(
                    p,
                    'adrlin1_kontakt', 'adrlin2_kontakt',
                    'adrlin3_kontakt', 'postnr_kontakt',
                    'adresseland_kontakt')

        # Get affiliations
        # Lots of changes here compared to import_FS.py @ uio
        # TODO: split import_FS into a common part and organization spesific
        # parts
        if dta_type in ('aktiv', ):
            for row in x:
                # aktiv_sted is necessary in order to avoid different
                # affiliation statuses to a same 'stedkode' to be overwritten
                # e.i. if a person has both affiliations status 'tilbud' and
                # aktive to a single stedkode we want to register the status
                # 'aktive' in cerebrum
                if studieprog2sko[row['studieprogramkode']] is not None:
                    aktiv_sted.append(
                        int(studieprog2sko[row['studieprogramkode']]))
                    _process_affiliation(
                        co.affiliation_student,
                        co.affiliation_status_student_aktiv, affiliations,
                        studieprog2sko[row['studieprogramkode']])
        elif dta_type in ('evu',):
            for row in x:
                _process_affiliation(
                    co.affiliation_student,
                    co.affiliation_status_student_evu, affiliations,
                    _get_sko(p, 'faknr_adm_ansvar',
                             'instituttnr_adm_ansvar',
                             'gruppenr_adm_ansvar'))
        elif dta_type in ('privatist_studieprogram', ):
            for row in x:
                _process_affiliation(
                    co.affiliation_student,
                    co.affiliation_status_student_privatist,
                    affiliations, studieprog2sko[row['studieprogramkode']])
        elif dta_type in ('tilbud', ):
            for row in x:
                subtype = co.affiliation_status_student_tilbud
                if studieprog2sko[row['studieprogramkode']] in aktiv_sted:
                    subtype = co.affiliation_status_student_aktiv
                _process_affiliation(co.affiliation_student,
                                     subtype, affiliations,
                                     studieprog2sko[row['studieprogramkode']])
    if etternavn is None:
        logger.info("Ikke noe navn p� %s", fnr)
        no_name += 1
        return

    # TODO: If the person already exist and has conflicting data from
    # another source-system, some mechanism is needed to determine the
    # superior setting.
    fsids = [(co.externalid_fodselsnr, fnr)]
    if studentnr is not None:
        fsids.append((co.externalid_studentnr, studentnr))

    new_person = Factory.get('Person')(db)
    try:
        new_person.find_by_external_ids(*fsids)
    except Errors.NotFoundError:
        pass
    except Errors.TooManyRowsError, e:
        logger.error("Trying to find studentnr %s, getting several persons: %s",
                     studentnr, e)
        return
    new_person.populate(db.Date(year, mon, day), gender)

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
            new_person.populate_address(co.system_fs, ad_const, **address_info)
    # if this is a new Person, there is no entity_id assigned to it
    # until written to the database.
    op = new_person.write_db()
    for ou, aff, aff_status in affiliations:
        new_person.populate_affiliation(co.system_fs, ou, aff, aff_status)
        if include_delete:
            key_a = "%s:%s:%s" % (new_person.entity_id, ou, int(aff))
            if key_a in old_aff:
                old_aff[key_a] = False

    register_cellphone(new_person, person_info)

    op2 = new_person.write_db()
    if op is None and op2 is None:
        logger.info("**** EQUAL ****")
    elif op is True:
        logger.info("**** NEW ****")
    else:
        logger.info("**** UPDATE ****")

    # Reservations
    if gen_groups:
        should_add = False
        for dta_type in person_info.keys():
            p = person_info[dta_type][0]
            if isinstance(p, str):
                continue
            # We only fetch the column in these queries
            if dta_type not in ('tilbud', 'aktiv', 'privatist_studieprogram',
                                'evu',):
                continue
            # If 'status_reserv_nettpubl' == "N": add to group
            if p.get('status_reserv_nettpubl', "") == "N":
                should_add = True
            else:
                should_add = False
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


def main():
    global verbose, ou, db, co, logger, gen_groups, group, \
        old_aff, include_delete, no_name
    verbose = 0
    gen_groups = False
    include_delete = False
    logger = Factory.get_logger("cronjob")
    opts, args = getopt.getopt(sys.argv[1:], 'vp:s:gdf', [
        'verbose', 'person-file=', 'studieprogram-file=',
        'generate-groups', 'include-delete', ])

    personfile = default_personfile
    studieprogramfile = default_studieprogramfile
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-p', '--person-file'):
            personfile = val
        elif opt in ('-s', '--studieprogram-file'):
            studieprogramfile = val
        elif opt in ('-g', '--generate-groups'):
            gen_groups = True
        elif opt in ('-d', '--include-delete'):
            include_delete = True
    if "system_fs" not in cereconf.SYSTEM_LOOKUP_ORDER:
        print "Check your config, SYSTEM_LOOKUP_ORDER is wrong!"
        sys.exit(1)
    logger.info("Started")
    db = Factory.get('Database')()
    db.cl_init(change_program='import_FS')
    ou = Factory.get('OU')(db)
    co = Factory.get('Constants')(db)

    group = Factory.get('Group')(db)
    try:
        group.find_by_name(group_name)
    except Errors.NotFoundError:
        group.clear()
        ac = Factory.get('Account')(db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        group.populate(ac.entity_id, co.group_visibility_internal,
                       group_name, group_desc)
        group.write_db()
    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        logger.warn("Warning: ENABLE_MKTIME_WORKAROUND is set")

    for s in StudentInfo.StudieprogDefParser(studieprogramfile):
        studieprog2sko[s['studieprogramkode']] = \
            _get_sko(s, 'faknr_studieansv', 'instituttnr_studieansv',
                     'gruppenr_studieansv')

    if include_delete:
        old_aff = _load_cere_aff()
    StudentInfo.StudentInfoParser(personfile, process_person_callback, logger)
    if include_delete:
        rem_old_aff()
    db.commit()
    logger.info("Found %d persons without name.", no_name)
    logger.info("Completed")

if __name__ == '__main__':
    main()
