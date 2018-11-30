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

import mx
import logging
import argparse
import datetime
from os.path import join as pj
from collections import defaultdict

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio.AutoStud import StudentInfo

import cereconf

# Globals
logger = logging.getLogger('cronjob')


def main():
    # global verbose, ou, db, co, logger, gen_groups, group, \
    #     old_aff, include_delete, no_name
    verbose = 0

    # "globals"
    db = Factory.get('Database')()
    db.cl_init(change_program='import_fs')
    co = Factory.get('Constants')(db)
    ou = Factory.get('OU')(db)
    group = Factory.get('Group')(db)

    # parsing
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v', '--verbose',
        action='count')
    parser.add_argument(
        '-p', '--person-file',
        dest='personfile',
        default=pj(cereconf.FS_DATA_DIR, "merged_persons.xml"))
    parser.add_argument(
        '-s', '--studieprogram-file',
        dest='studieprogramfile',
        default=pj(cereconf.FS_DATA_DIR, "studieprog.xml"))
    parser.add_argument(
        '-g', '--generate-groups',
        dest='gen_groups',
        action='store_true')
    parser.add_argument(
        '-d', '--include-delete',
        dest='include_delete',
        action='store_true')
    if cereconf.FS_EMNEFILE_ARGUMENT:
        parser.add_argument(
            '-e', '--emne-file',
            dest='emnefile',
            default=pj(cereconf.FS_DATA_DIR, "emner.xml"))
    args = parser.parse_args()

    if "system_fs" not in cereconf.SYSTEM_LOOKUP_ORDER:
        raise SystemExit("Check cereconf, SYSTEM_LOOKUP_ORDER is wrong!")

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
    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        logger.warn("Warning: ENABLE_MKTIME_WORKAROUND is set")

    studieprog2sko = {}
    for s in StudentInfo.StudieprogDefParser(args.studieprogramfile):
        studieprog2sko[s['studieprogramkode']] = _get_sko(
            s, 'faknr_studieansv', 'instituttnr_studieansv',
            'gruppenr_studieansv', ou)

    # if cereconf.FS_EMNEFILE_ARGUMENT:
    #     emne2sko = _get_emne2sko(args.emnefile, ou)

    if include_delete:
        old_aff = _load_cere_aff(db, co)

    fnr2person_id = None
    if cereconf.FS_FIND_PERSON_BY == 'fnr':
        fnr2person_id, person = _get_fnr2person(db, co)

    person_processor = PersonProcessor(studieprog2sko, db, co, ou, gen_groups,
                                       fnr2person_id, include_delete, old_aff)
    StudentInfo.StudentInfoParser(args.personfile,
                                  person_processor.process_person_callback,
                                  logger)

    if include_delete:
        rem_old_aff(old_aff, db, co)
    db.commit()
    logger.info("Found %d persons without name.", person_processor.no_name)
    logger.info("Completed")


def _get_emne2sko(emnefile, ou):
    emne2sko = {}
    for e in StudentInfo.EmneDefParser(emnefile):
        emne2sko[e['emnekode']] = _get_sko(
            e, 'faknr_reglement', 'instituttnr_reglement',
            'gruppenr_reglement', ou)
        return emne2sko


def _get_sko(a_dict, kfak, kinst, kgr, ou, kinstitusjon=None):
    # We cannot ignore institusjon (inst A, sko x-y-z is NOT the same as
    # inst B, sko x-y-z)
    if kinstitusjon is not None:
        institusjon = a_dict[kinstitusjon]
    else:
        institusjon = cereconf.DEFAULT_INSTITUSJONSNR

    if cereconf.FS_KEY_INCLUDE_INST:
        key = "-".join((str(institusjon),
                        a_dict[kfak], a_dict[kinst], a_dict[kgr]))
    else:
        key = "-".join((a_dict[kfak], a_dict[kinst], a_dict[kgr]))

    ou_cache = {}
    if key not in ou_cache:
        try:
            ou.find_stedkode(int(a_dict[kfak]), int(a_dict[kinst]),
                             int(a_dict[kgr]), institusjon=institusjon)
            ou_cache[key] = ou.entity_id
        except Errors.NotFoundError:
            logger.warn("Cannot find an OU in Cerebrum with stedkode: %s", key)
            ou_cache[key] = None
    return ou_cache[key]


class PersonProcessor(object):
    def __init__(self, studieprog2sko, db, co, ou, gen_groups, fnr2person_id,
                 include_delete, old_aff):
        # Variables passed to/from main
        self.no_name = 0

        self.studieprog2sko = studieprog2sko
        self.db = db
        self.co = co
        self.ou = ou
        self.gen_groups = gen_groups
        self.fnr2person_id = fnr2person_id
        self.group = None
        self.include_delete = include_delete
        self.old_aff = old_aff

    def process_person_callback(self, person_info):
        """Called when we have fetched all data on a person from the xml
        file.  Updates/inserts name, address and affiliation
        information."""
        try:
            fnr = _get_fnr(person_info)
        except fodselsnr.InvalidFnrError:
            return

        gender = _get_gender(fnr, self.co)

        affiliations = aktiv_sted = []

        if cereconf.FS_ITERATE_PERSONS == 'hiof':
            etternavn, fornavn, studentnr, birth_date = _iterate_persons_hiof(
                person_info, self.studieprog2sko, aktiv_sted, affiliations,
                self.co)
        elif cereconf.FS_ITERATE_PERSONS == 'uia':
            etternavn, fornavn, studentnr, birth_date, address_info = \
                _iterate_persons_uia(person_info, self.studieprog2sko,
                                     aktiv_sted, affiliations, self.co,
                                     self.ou, fnr)

        if etternavn is None:
            logger.debug("Ikke noe navn på %s" % fnr)
            self.no_name += 1
            return

        if not birth_date:
            logger.warn('No birth date registered for studentnr %s', studentnr)

        # TODO: If the person already exist and has conflicting data from
        # another source-system, some mechanism is needed to determine the
        # superior setting.
        if cereconf.FS_FIND_PERSON_BY == 'fnr':
            new_person = _get_person_by_fnr(fnr, self.fnr2person_id, self.db)
        elif cereconf.FS_FIND_PERSON_BY == 'studentnr':
            new_person = _get_person_by_studentnr(fnr, studentnr, self.db,
                                                  self.co)

        _db_add_person(new_person, birth_date, gender, fornavn, etternavn,
                       studentnr, fnr, person_info, self.include_delete,
                       self.old_aff, affiliations, self.db, self.co, self.ou)

        if self.gen_groups:
            self.group = _add_reservations(person_info, new_person, self.group)

        self.db.commit()


def _get_fnr(person_info):
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


def _get_gender(fnr, co):
    gender = co.gender_male
    if fodselsnr.er_kvinne(fnr):
        gender = co.gender_female
    return gender


def _get_person_by_fnr(fnr, fnr2person_id, db):
    new_person = Factory.get('Person')(db)
    if fnr in fnr2person_id:
        new_person.find(fnr2person_id[fnr])
    return new_person


def _get_person_by_studentnr(fnr, studentnr, db, co):
    fsids = [(co.externalid_fodselsnr, fnr)]
    if studentnr is not None:
        fsids.append((co.externalid_studentnr, studentnr))
    new_person = Factory.get('Person')(db)
    try:
        new_person.find_by_external_ids(*fsids)
    except Errors.NotFoundError:
        pass
    except Errors.TooManyRowsError as e:
        logger.error("Trying to find studentnr %r, "
                     "getting several persons: %r",
                     studentnr, e)
    return new_person


def _iterate_persons_hiof(person_info, studieprog2sko, aktiv_sted,
                          affiliations, co):
    etternavn = fornavn = studentnr = birth_date = address_info = None

    # Iterate over all person_info entries and extract relevant data
    if 'aktiv' in person_info:
        for row in person_info['aktiv']:
            if studieprog2sko[row['studieprogramkode']] is not None:
                aktiv_sted.append(
                    int(studieprog2sko[row['studieprogramkode']]))
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
            _process_affiliation(
                co.affiliation_tilknyttet,
                co.affiliation_status_tilknyttet_fagperson,
                affiliations,
                _get_sko(p, 'faknr', 'instituttnr', 'gruppenr',
                         'institusjonsnr'))
        elif dta_type in ('aktiv',):
            for row in x:
                # aktiv_sted is necessary in order to avoid different
                # affiliation statuses to a same 'stedkode' to be overwritten
                # e.i. if a person has both affiliations status 'evu' and
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
            subtype = co.affiliation_status_student_evu
            if studieprog2sko[row['studieprogramkode']] in aktiv_sted:
                subtype = co.affiliation_status_student_aktiv
            _process_affiliation(co.affiliation_student,
                                 subtype, affiliations,
                                 studieprog2sko[row['studieprogramkode']])
    # end for-loop
    return etternavn, fornavn, studentnr, birth_date


def _iterate_persons_uia(person_info, studieprog2sko, aktiv_sted,
                         affiliations, co, ou, fnr):
    etternavn = fornavn = studentnr = birth_date = address_info = None

    # Iterate over all person_info entries and extract relevant data
    for dta_type in person_info.keys():
        x = person_info[dta_type]
        p = x[0]
        if isinstance(p, basestring):
            continue
        if dta_type not in ('tilbud', 'eksamen', 'evu'):
            if 'studentnr_tildelt' in p:
                studentnr = p['studentnr_tildelt']
            else:
                logger.info("\n%s mangler studentnr!", fnr)
        # Get name
        if dta_type in ('aktiv', 'tilbud', 'evu', 'privatist_studieprogram',):
            etternavn = p['etternavn']
            fornavn = p['fornavn']

        if not birth_date and 'dato_fodt' in p:
            birth_date = datetime.datetime.strptime(p['dato_fodt'],
                                                    "%Y-%m-%d %H:%M:%S.%f")

        address_info = _get_address(address_info, dta_type, p)

        # Get affiliations
        # Lots of changes here compared to import_FS.py @ uio
        # TODO: split import_FS into a common part and organization spesific
        # parts
        if dta_type in ('aktiv',):
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
                             'gruppenr_adm_ansvar', ou))
        elif dta_type in ('privatist_studieprogram',):
            for row in x:
                _process_affiliation(
                    co.affiliation_student,
                    co.affiliation_status_student_privatist,
                    affiliations, studieprog2sko[row['studieprogramkode']])
        elif dta_type in ('tilbud',):
            for row in x:
                subtype = co.affiliation_status_student_tilbud
                if studieprog2sko[row['studieprogramkode']] in aktiv_sted:
                    subtype = co.affiliation_status_student_aktiv
                _process_affiliation(co.affiliation_student,
                                     subtype, affiliations,
                                     studieprog2sko[row['studieprogramkode']])
    return etternavn, fornavn, studentnr, birth_date, address_info


def _db_add_person(new_person, birth_date, gender, fornavn, etternavn,
                   studentnr, fnr, person_info, include_delete,
                   old_aff, affiliations, db, co, ou):
    """Fills in the necessary information about the new_person.
    Then the new_person gets written to the database"""
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

    ad_post, ad_post_private, ad_street = _calc_address(person_info, db, co,
                                                        ou)
    for address_info, ad_const in ((ad_post, co.address_post),
                                   (ad_post_private, co.address_post_private),
                                   (ad_street, co.address_street)):
        # TBD: Skal vi slette evt. eksisterende adresse v/None?
        if address_info is not None:
            logger.debug("Populating address...")
            new_person.populate_address(co.system_fs, ad_const, **address_info)
    # if this is a new Person, there is no entity_id assigned to it
    # until written to the database.
    op = new_person.write_db()

    if cereconf.FS_FILTER_AFFILIATIONS:
        affiliations = filter_affiliations(affiliations, co)

    for ou, aff, aff_status in affiliations:
        new_person.populate_affiliation(co.system_fs, ou, aff, aff_status)
        if include_delete:
            key_a = "%s:%s:%s" % (new_person.entity_id, ou, int(aff))
            if key_a in old_aff:
                old_aff[key_a] = False

    register_cellphone(new_person, person_info, co)

    op2 = new_person.write_db()
    if op is None and op2 is None:
        logger.info("**** EQUAL ****")
    elif op:
        logger.info("**** NEW ****")
    else:
        logger.info("**** UPDATE ****")


def _add_reservations(person_info, new_person, group):
    should_add = False
    for dta_type in person_info.keys():
        p = person_info[dta_type][0]
        if isinstance(p, str):
            continue
        # Presence of 'fagperson' elements for a person should not
        # affect that person's reservation status.
        if dta_type in ('fagperson',):
            continue
        # We only fetch the column in these queries
        if dta_type not in ('evu'):
            continue
        # If 'status_reserv_nettpubl' == "N": add to group
        if p.get('status_reserv_nettpubl', "") == "N":
            should_add = True
        else:
            should_add = False
    if should_add:
        # The student has explicitly given us permission to be
        # published in the directory.
        group = _add_res(group, new_person.entity_id)
    else:
        # The student either hasn't registered an answer to
        # the "Can we publish info about you in the directory"
        # question at all, or has given an explicit "I don't
        # want to appear in the directory" answer.
        _rem_res(group, new_person.entity_id)
    return group


def _get_fnr2person(db, co):
    person = Factory.get('person')(db)
    # create fnr2person_id mapping, always using fnr from FS when set
    fnr2person_id = {}
    for p in person.list_external_ids(id_type=co.externalid_fodselsnr):
        if co.system_fs == p['source_system']:
            fnr2person_id[p['external_id']] = p['entity_id']
        elif p['external_id'] not in fnr2person_id:
            fnr2person_id[p['external_id']] = p['entity_id']
    return fnr2person_id, person


def _add_aktiv_sted(person_info, studieprog2sko, aktiv_sted):
    for row in person_info['aktiv']:
        if studieprog2sko[row['studieprogramkode']] is not None:
            aktiv_sted.append(
                int(studieprog2sko[row['studieprogramkode']]))
            logger.debug("App2akrivts")


def _get_address(address_info, dta_type, p):
    if address_info is None:
        if dta_type in ('aktiv', 'privatist_studieprogram',):
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
    return address_info


def rem_old_aff(old_aff, db, co):
    """ Remove old affiliations.

    This method loops through the global `old_affs` mapping. The
    `process_person_callback` marks affs as False if they are still present in
    the FS import files.

    For the rest, we check if they are past the
    cereconf.FS_STUDENT_REMOVE_AFF_GRACE_DAYS limit, and remove them if they
    are.

    """
    logger.info("Removing old FS affiliations")
    stats = defaultdict(lambda: 0)
    person = Factory.get("Person")(db)
    person_ids = set()
    for k in old_aff:
        if not old_aff[k]:
            # Aff still present in import files
            continue

        person_id, ou_id, aff_id = (int(val) for val in k.split(':'))
        aff_const = co.PersonAffiliation(aff_id)

        logger.debug("Attempting to remove aff %r (%r)", k, aff_const)
        stats['old'] += 1

        aff = person.list_affiliations(person_id=person_id,
                                       source_system=co.system_fs,
                                       affiliation=aff_const,
                                       ou_id=ou_id)
        if not aff:
            logger.warn(
                'Possible race condition when attempting to remove aff '
                '{} for {}'.format(aff_const, person_id))
            continue
        if len(aff) > 1:
            logger.warn("More than one aff for person %s, what to do?",
                        person_id)
            # if more than one aff we should probably just remove both/all
            continue
        aff = aff[0]

        # Check date, do not remove affiliation for active students until end
        # of grace period. Some institutions' EVU affiliations should be
        # removed at once.
        grace_days = cereconf.FS_STUDENT_REMOVE_AFF_GRACE_DAYS
        not_expired = aff['last_date'] > (mx.DateTime.now() - grace_days) and \
                      not (cereconf.FS_REMOVE_EVU_AFF and int(aff['status']) ==
                           int(co.affiliation_status_student_evu))
        if not_expired:
            logger.debug("Sparing aff (%s) for person_id=%r at ou_id=%r",
                         aff_const, person_id, ou_id)
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
                    co.PersonAffiliation(aff_id), person_id, ou_id)
        person.delete_affiliation(ou_id=ou_id, affiliation=aff_const,
                                  source=co.system_fs)
        stats['delete'] += 1
        person_ids.add(person_id)

    logger.info("Old affs: %d affs on %d persons",
                stats['old'], len(person_ids))
    logger.info("Affiliations spared: %d", stats['grace'])
    logger.info("Affiliations removed: %d", stats['delete'])


def filter_affiliations(affiliations, co):
    """The affiliation list with cols (ou, affiliation, status) may
    contain multiple status values for the same (ou, affiliation)
    combination, while the db-schema only allows one.  Return a list
    where duplicates are removed, preserving the most important
    status.  """
    aff_status_pri_order = [int(x) for x in (  # Most significant first
        co.affiliation_status_student_aktiv,
        co.affiliation_status_student_evu)]
    aff_status_pri_order = dict([(aff_status_pri_order[i], i)
                                 for i in range(len(aff_status_pri_order))])

    affiliations.sort(lambda x, y: aff_status_pri_order.get(int(y[2]), 99) -
                                   aff_status_pri_order.get(int(x[2]), 99))

    ret = {}
    for ou, aff, aff_status in affiliations:
        ret[(ou, aff)] = aff_status
    return [(ou, aff, aff_status) for (ou, aff), aff_status in ret.items()]


def _add_res(group, entity_id):
    if not group.has_member(entity_id):
        group.add_member(entity_id)
    return group


def _rem_res(group, entity_id):
    if group.has_member(entity_id):
        group.remove_member(entity_id)
    return group


def register_cellphone(person, person_info, co):
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


def _process_affiliation(aff, aff_status, new_affs, ou):
    # TBD: Should we for example remove the 'opptak' affiliation if we
    # also have the 'aktiv' affiliation?
    if ou is not None:
        new_affs.append((ou, aff, aff_status))


def _get_sted_address(db, co, ou, a_dict, k_institusjon, k_fak, k_inst,
                      k_gruppe):
    ou_adr_cache = {}

    ou_id = _get_sko(a_dict, k_fak, k_inst, k_gruppe, ou,
                     kinstitusjon=k_institusjon)
    if not ou_id:
        return None
    ou_id = int(ou_id)
    if ou_id not in ou_adr_cache:
        ou = Factory.get('OU')(db)
        ou.find(ou_id)

        rows = ou.get_entity_address(type=co.address_street,
                                     source=getattr(co,
                                                    cereconf.FS_SOURCE_SYSTEM))

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


def _calc_address(person_info, db, co, ou):
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
    for key, addr_src in cereconf.FS_RULES:
        if key not in person_info:
            continue
        tmp = person_info[key][0].copy()
        for i in range(len(addr_src)):
            addr_cols = cereconf.FS_ADR_MAP.get(addr_src[i], None)
            if (ret[i] is not None) or not addr_cols:
                continue
            if len(addr_cols) == 4:
                ret[i] = _get_sted_address(db, co, ou, tmp, *addr_cols)
            else:
                ret[i] = _ext_address_info(tmp, *addr_cols)
    return ret


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
        logger.debug("No address found")
        return None
    return ret


def _load_cere_aff(db, co):
    fs_aff = {}
    person = Factory.get("Person")(db)
    for row in person.list_affiliations(source_system=co.system_fs):
        k = "%s:%s:%s" % (row['person_id'], row['ou_id'], row['affiliation'])
        fs_aff[str(k)] = True
    return (fs_aff)


if __name__ == '__main__':
    main()
