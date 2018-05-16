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

from os.path import join as pj

import sys
import getopt
import mx
import json

import cereconf

from Cerebrum import Errors
from Cerebrum.modules.no import fodselsnr
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.AutoStud import StudentInfo

default_personfile = pj(cereconf.FS_DATA_DIR, "merged_persons.xml")
default_studieprogramfile = pj(cereconf.FS_DATA_DIR, "studieprog.xml")
default_emnefile = pj(cereconf.FS_DATA_DIR, "emner.xml")
group_name = cereconf.FS_GROUP_NAME
group_desc = cereconf.FS_GROUP_DESC


studieprog2sko = {}
emne2sko = {}
ou_cache = {}
ou_adr_cache = {}
gen_groups = False
no_name = 0  # count persons for which we do not have any name data from FS

db = Factory.get('Database')()
db.cl_init(change_program='import_FS')
co = Factory.get('Constants')(db)
aff_status_pri_order = [int(x) for x in (  # Most significant first
    co.affiliation_status_student_aktiv,
    co.affiliation_status_student_evu)]
aff_status_pri_order = dict([
    (aff_status_pri_order[i], i)
    for i in range(len(aff_status_pri_order))
])


def _add_res(entity_id):
    if not group.has_member(entity_id):
        group.add_member(entity_id)


def _rem_res(entity_id):
    if group.has_member(entity_id):
        group.remove_member(entity_id)


def _get_sko(a_dict, kfak, kinst, kgr, kinstitusjon=None):
    #
    # We cannot ignore institusjon (inst A, sko x-y-z is NOT the same as
    # inst B, sko x-y-z)
    if kinstitusjon is not None:
        institusjon = a_dict[kinstitusjon]
    else:
        institusjon = cereconf.DEFAULT_INSTITUSJONSNR
    # fi

    key = "-".join((str(institusjon), a_dict[kfak], a_dict[kinst], a_dict[kgr]))
    if not ou_cache.has_key(key):
        ou = Factory.get('OU')(db)
        try:
            ou.find_stedkode(int(a_dict[kfak]), int(a_dict[kinst]), int(a_dict[kgr]),
                             institusjon=institusjon)
            ou_cache[key] = ou.entity_id
        except Errors.NotFoundError:
            logger.warn("Cannot find an OU in Cerebrum with stedkode: %s", key)
            ou_cache[key] = None
    return ou_cache[key]


def _process_affiliation(aff, aff_status, new_affs, ou):
    if ou is not None:
        new_affs.append((ou, aff, aff_status))


def _get_sted_address(a_dict, k_institusjon, k_fak, k_inst, k_gruppe):
    ou_id = _get_sko(a_dict, k_fak, k_inst, k_gruppe,
                     kinstitusjon=k_institusjon)
    if not ou_id:
        return None
    ou_id = int(ou_id)
    if not ou_adr_cache.has_key(ou_id):
        ou = Factory.get('OU')(db)
        ou.find(ou_id)
        rows = ou.get_entity_address(source=co.system_fs, type=co.address_street)
        if rows:
            ou_adr_cache[ou_id] = {
                'address_text': rows[0]['address_text'],
                'postal_number': rows[0]['postal_number'],
                'city': rows[0]['city']
                }
        else:
            ou_adr_cache[ou_id] = None
            logger.warn("No address for %i" % ou_id)
    return ou_adr_cache[ou_id]


def _ext_address_info(a_dict, kline1, kline2, kline3, kpost, kland):
    ret = {}
    ret['address_text'] = "\n".join([a_dict.get(f, None)
                                     for f in (kline1, kline2)
                                     if a_dict.get(f, None)])
    postal_number = a_dict.get(kpost, '')
    if postal_number:
        postal_number = "%04i" % int(postal_number)
    ret['postal_number'] = postal_number
    ret['city'] =  a_dict.get(kline3, '')
    if len(ret['address_text']) == 1:
        logger.debug("Address might not be complete, but we need to cover one-line addresses")
    # we have to register at least the city in order to have a "proper" address
    # this mean that addresses containing only ret['city'] will be imported
    # as well
    if len(ret['address_text']) < 1 and not ret['city']:
        logger.debug("No address found")
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
        ('aktiv', ('_hjemsted', '_semadr', None)),
        ('evu', ('_job', '_hjem', None)),
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
    logger.debug("Getting address for person %s%s" % (person_info['fodselsdato'], person_info['personnr']))

    ret = [None, None, None]
    for key, addr_src in rules:
        if not person_info.has_key(key):
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
    person = Factory.get("Person")(db)
    for row in person.list_affiliations(source_system=co.system_fs):
        k = "%s:%s:%s" % (row['person_id'],row['ou_id'],row['affiliation'])
        fs_aff[str(k)] = True
    return(fs_aff)


def rem_old_aff():
    person = Factory.get("Person")(db)
    for k, v in old_aff.items():
        if v:
            ent_id, ou, affi = k.split(':')
            person.clear()
            person.find(int(ent_id))
            person.delete_affiliation(ou, affi, co.system_fs)


def filter_affiliations(affiliations):
    """The affiliation list with cols (ou, affiliation, status) may
    contain multiple status values for the same (ou, affiliation)
    combination, while the db-schema only allows one.  Return a list
    where duplicates are removed, preserving the most important
    status.  """

    affiliations.sort(lambda x,y: aff_status_pri_order.get(int(y[2]), 99) -
                      aff_status_pri_order.get(int(x[2]), 99))

    ret = {}
    for ou, aff, aff_status in affiliations:
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

    logger.warn("Person %s has several cell phone numbers. Ignoring them all", fnr)


def process_person_callback(person_info):
    """Called when we have fetched all data on a person from the xml
    file.  Updates/inserts name, address and affiliation
    information."""

    global no_name
    try:
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                                  int(person_info['personnr'])))
        fnr = fodselsnr.personnr_ok(fnr)
        logger.info("Process %s " % (fnr))
        (year, mon, day) = fodselsnr.fodt_dato(fnr)
        if (year < 1970
            and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
            # Seems to be a bug in time.mktime on some machines
            year = 1970
    except fodselsnr.InvalidFnrError:
        logger.warn("Ugyldig fødselsnr: %s" % fnr)
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
    if person_info.has_key('aktiv'):
        for row in person_info['aktiv']:
            if studieprog2sko[row['studieprogramkode']] is not None:
                aktiv_sted.append(int(studieprog2sko[row['studieprogramkode']]))

    for dta_type in person_info.keys():
        x = person_info[dta_type]
        p = x[0]
        if isinstance(p, basestring):
            continue
        # Get name
        if dta_type in ('fagperson', 'evu', 'aktiv'):
            etternavn = p['etternavn']
            fornavn = p['fornavn']
        if p.has_key('studentnr_tildelt'):
            studentnr = p['studentnr_tildelt']

        # Get affiliations
        if dta_type in ('fagperson',):
            _process_affiliation(co.affiliation_tilknyttet,
                                 co.affiliation_status_tilknyttet_fagperson,
                                 affiliations, _get_sko(p, 'faknr',
                                 'instituttnr', 'gruppenr', 'institusjonsnr'))
        elif dta_type in ('aktiv', ):
            for row in x:
                # aktiv_sted is necessary in order to avoid different affiliation statuses
                # to a same 'stedkode' to be overwritten
                # e.i. if a person has both affiliations status 'evu' and
                # aktive to a single stedkode we want to register the status 'aktive'
                # in cerebrum
                if studieprog2sko[row['studieprogramkode']] is not None:
                    aktiv_sted.append(int(studieprog2sko[row['studieprogramkode']]))
                    _process_affiliation(
                        co.affiliation_student,
                        co.affiliation_status_student_aktiv,
                        affiliations,
                        studieprog2sko[row['studieprogramkode']])
        elif dta_type in ('evu',):
            subtype = co.affiliation_status_student_evu
            if studieprog2sko[row['studieprogramkode']] in aktiv_sted:
                subtype = co.affiliation_status_student_aktiv
            _process_affiliation(co.affiliation_student,
                                 subtype, affiliations,
                                 studieprog2sko[row['studieprogramkode']])

    if etternavn is None:
        logger.debug("Ikke noe navn på %s" % fnr)
        no_name += 1
        return

    # TODO: If the person already exist and has conflicting data from
    # another source-system, some mechanism is needed to determine the
    # superior setting.

    new_person = Factory.get('Person')(db)
    if fnr2person_id.has_key(fnr):
        new_person.find(fnr2person_id[fnr])

    new_person.populate(mx.DateTime.Date(year, mon, day), gender)

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
            logger.debug("Populating address...")
            new_person.populate_address(co.system_fs, ad_const, **address_info)

    # if this is a new Person, there is no entity_id assigned to it
    # until written to the database.
    op = new_person.write_db()

    for a in filter_affiliations(affiliations):
        ou, aff, aff_status = a
        new_person.populate_affiliation(co.system_fs, ou, aff, aff_status)
        if include_delete:
            key_a = "%s:%s:%s" % (new_person.entity_id,ou,int(aff))
            if old_aff.has_key(key_a):
                old_aff[key_a] = False

    register_cellphone(new_person, person_info)

    op2 = new_person.write_db()
    if op is None and op2 is None:
        logger.info("**** EQUAL ****")
    elif op == True:
        logger.info("**** NEW ****")
    else:
        logger.info("**** UPDATE ****")

    register_fagomrade(new_person, person_info)

    # Reservations
    if gen_groups:
        should_add = False
        if person_info.has_key('nettpubl'):
            for row in person_info['nettpubl']:
                if row.get('akseptansetypekode', "") == "NETTPUBL" and row.get('status_svar', "") == "J":
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


def register_fagomrade(person, person_info):
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

    fagfelt_trait = person.get_trait(trait=co.trait_fagomrade_fagfelt)
    fagfelt = []

    # Extract fagfelt from any fagperson rows
    if 'fagperson' in person_info:
        fagfelt = [data.get('fagfelt') for data in person_info['fagperson']
                   if data.get('fagfelt') is not None]
        # Sort alphabetically as the rows are returned in random order
        fagfelt.sort()

    if fagfelt_trait and not fagfelt:
        logger.debug('Removing fagfelt for %s', fnr)
        person.delete_trait(code=co.trait_fagomrade_fagfelt)
    elif fagfelt:
        logger.debug('Populating fagfelt for %s', fnr)
        person.populate_trait(
            code=co.trait_fagomrade_fagfelt,
            date=mx.DateTime.now(),
            strval=json.dumps(fagfelt))

    person.write_db()


def main():
    global verbose, ou, logger, fnr2person_id, gen_groups, group
    global old_aff, include_delete, no_name
    verbose = 0
    include_delete = False
    logger = Factory.get_logger("cronjob")
    opts, args = getopt.getopt(sys.argv[1:], 'vp:s:e:gdf', [
        'verbose', 'person-file=', 'studieprogram-file=',
        'emne-file=', 'generate-groups', 'include-delete', ])

    personfile = default_personfile
    studieprogramfile = default_studieprogramfile
    emnefile = default_emnefile
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-p', '--person-file'):
            personfile = val
        elif opt in ('-s', '--studieprogram-file'):
            studieprogramfile = val
        elif opt in ('-e', '--emne-file'):
            emnefile = val
        elif opt in ('-g', '--generate-groups'):
            gen_groups = True
        elif opt in ('-d', '--include-delete'):
            include_delete = True
    if "system_fs" not in cereconf.SYSTEM_LOOKUP_ORDER:
        print "Check your config, SYSTEM_LOOKUP_ORDER is wrong!"
        sys.exit(1)
    logger.info("Started")
    ou = Factory.get('OU')(db)

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

    for e in StudentInfo.EmneDefParser(emnefile):
        emne2sko[e['emnekode']] = \
            _get_sko(e, 'faknr_reglement', 'instituttnr_reglement',
                     'gruppenr_reglement')

    # create fnr2person_id mapping, always using fnr from FS when set
    person = Factory.get('Person')(db)
    if include_delete:
        old_aff = _load_cere_aff()
    fnr2person_id = {}
    for p in person.list_external_ids(id_type=co.externalid_fodselsnr):
        if co.system_fs == p['source_system']:
            fnr2person_id[p['external_id']] = p['entity_id']
        elif not fnr2person_id.has_key(p['external_id']):
            fnr2person_id[p['external_id']] = p['entity_id']
    StudentInfo.StudentInfoParser(personfile, process_person_callback, logger)
    if include_delete:
        rem_old_aff()
    db.commit()
    logger.info("Found %r persons without name.", no_name)
    logger.info("Completed")


if __name__ == '__main__':
    main()
