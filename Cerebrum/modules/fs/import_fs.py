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


import logging
import argparse
import cereconf
from os.path import join as pj

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio.AutoStud import StudentInfo


logger=logging.getLogger('cronjob')

def main():
    # global verbose, ou, db, co, logger, gen_groups, group, \
    #     old_aff, include_delete, no_name

    # "globals"
    db = Factory.get('Database')()
    db.cl_init(change_program='import_fs')
    co = Factory.get('Constants')(db)
    ou = Factory.get('OU')(db)
    group = Factory.get('Group')(db)

    group_name = cereconf.FS_GROUP_NAME
    group_desc = cereconf.FS_GROUP_DESC

    studieprog2sko = {}
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
    args=parser.parse_args()

    if "system_fs" not in cereconf.SYSTEM_LOOKUP_ORDER:
        raise SystemExit("Check cereconf, SYSTEM_LOOKUP_ORDER is wrong!")

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

    for s in StudentInfo.StudieprogDefParser(args.studieprogramfile):
        studieprog2sko[s['studieprogramkode']] = _get_sko(
            s, 'faknr_studieansv', 'instituttnr_studieansv',
            'gruppenr_studieansv')

    if cereconf.FS_EMNEFILE_ARGUMENT:
        emne2sko = _get_emne2sko(args.emnefile)

    if include_delete:
        old_aff = _load_cere_aff()
    StudentInfo.StudentInfoParser(args.personfile, process_person_callback,
                                  logger)
    if cereconf.FS_FNR_2_PERSON:
        fnr2person_id, person = _get_fnr2person(db)

    if include_delete:
        rem_old_aff()
    db.commit()
    logger.info("Found %d persons without name.", no_name)
    logger.info("Completed")


def _get_emne2sko(emnefile, ou):
    for e in StudentInfo.EmneDefParser(emnefile):
        emne2sko={}
        emne2sko[e['emnekode']] = _get_sko(
            e, 'faknr_reglement', 'instituttnr_reglement',
            'gruppenr_reglement', ou, ou_cache)
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

def _get_fnr2person(db):
    person = Factory.get('person')(db)
    # create fnr2person_id mapping, always using fnr from FS when set
    fnr2person_id = {}
    for p in person.list_external_ids(id_type=co.externalid_fodselsnr):
        if co.system_fs == p['source_system']:
            fnr2person_id[p['external_id']] = p['entity_id']
        elif p['external_id'] not in fnr2person_id:
            fnr2person_id[p['external_id']] = p['entity_id']
    return  fnr2person_id, person


def _add_res(entity_id):
    if not group.has_member(entity_id):
        group.add_member(entity_id)


def _rem_res(entity_id):
    if group.has_member(entity_id):
        group.remove_member(entity_id)


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


def _process_affiliation(aff, aff_status, new_affs, ou):
    # TBD: Should we for example remove the 'opptak' affiliation if we
    # also have the 'aktiv' affiliation?
    if ou is not None:
        new_affs.append((ou, aff, aff_status))


def _get_sted_address(a_dict, k_institusjon, k_fak, k_inst, k_gruppe, source):
    ou_id = _get_sko(a_dict, k_fak, k_inst, k_gruppe,
                     kinstitusjon=k_institusjon)
    if not ou_id:
        return None
    ou_id = int(ou_id)
    if ou_id not in ou_adr_cache:
        ou = Factory.get('OU')(db)
        ou.find(ou_id)
        rows = ou.get_entity_address(source=source,
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
                ret[i] = _get_sted_address(tmp, *addr_cols)
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


def _load_cere_aff():
    fs_aff = {}
    person = Factory.get("Person")(db)
    for row in person.list_affiliations(source_system=co.system_fs):
        k = "%s:%s:%s" % (row['person_id'], row['ou_id'], row['affiliation'])
        fs_aff[str(k)] = True
    return(fs_aff)


def get_fnr(person_info):
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


if __name__ == '__main__':
    main()
