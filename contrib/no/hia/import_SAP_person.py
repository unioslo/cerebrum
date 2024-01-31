#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2023 University of Oslo, Norway
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
This file is a DFØ-SAP extension of Cerebrum.

It contains code which imports SAP-specific person/employee information into
Cerebrum.

FIXME: I wonder if the ID lookup/population logic might fail in a subtle
way, should an update process (touching IDs) run concurrently with this
import.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import io
import logging

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.import_utils.matcher import PersonMatcher
from Cerebrum.modules.import_utils.syncs import (
    ExternalIdSync,
)
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.hia.mod_sap_utils import (make_person_iterator,
                                                   make_passnr_iterator)
from Cerebrum.utils import argutils


logger = logging.getLogger(__name__)


def locate_person(sap_id, fnr, passnr):
    """
    Locate a person from SAP-data.

    :param str sap_id: employee id
    :param str fnr: national id number, if available
    :param str passnr: passport number, if available

    :rtype: tuple <boolean, Person>
    :returns:
      A tuple, where first item indicates whether id match triggered an error,
      and the second item is the Person associated with the id (or None, if no
      such association exists in Cerebrum)
    """
    # A person-matcher with primary id set to sap_ansattnr.  If a duplicates
    # are found, but one of the duplicates has *this* id, we'll use that person
    # object...
    search = PersonMatcher()

    criterias = [(const.externalid_sap_ansattnr, sap_id)]
    if fnr:
        criterias.append((const.externalid_fodselsnr, fnr))
    if passnr:
        criterias.append((const.externalid_pass_number, passnr))

    try:
        person = search(database, criterias, required=True)
        return False, person
    except Errors.NotFoundError:
        return False, None
    except Errors.TooManyRowsError:
        return True, None


def match_external_ids(person, sap_id, fnr, passnr):
    """
    Make sure that PERSON's external IDs in Cerebrum match SAP_ID and FNR.
    """
    # TODO: We should change this slightly:
    #
    # Don't really need to check if the ids differ, however the extid syncer
    # should validate if other person objects already owns any new/updated
    # external ids...

    def get_id(id_type):
        rows = person.get_external_id(const.system_sap, id_type)
        if rows:
            return rows[0]["external_id"]
        return None

    cerebrum_sap_id = get_id(const.externalid_sap_ansattnr)
    cerebrum_fnr = get_id(const.externalid_fodselsnr)
    cerebrum_passnr = get_id(const.externalid_pass_number)

    if (cerebrum_sap_id and cerebrum_sap_id != sap_id):
        logger.error("SAP id in Cerebrum != SAP id in datafile "
                     "«%s» != «%s»", cerebrum_sap_id, sap_id)
        return False

    # A mismatch in fnr only means that Cerebrum's data has to be updated.
    if (cerebrum_fnr and cerebrum_fnr != fnr):
        person_id_cerebrum = fnr2person_id(fnr)

        # *IF* there is a person in cerebrum that already holds fnr, AND
        # it's a different person than the one we've associated with sap_id,
        # then we cannot update fnrs, because then two different people would
        # share the same fnr. However, if the fnr did not exist in cerebrum
        # before, person_id_cerebrum would be None (and different from
        # person.entity_id). Both branches of the test are necessary.
        if ((person_id_cerebrum is not None) and
                person.entity_id != person_id_cerebrum):
            logger.error(
                "Should update FNR for %s, but another person (%s) with FNR "
                "(%s) exists in Cerebrum",
                person_id_cerebrum,
                sap_id,
                fnr)
            return False
        logger.info("FNR in Cerebrum != FNR in datafile. Updating "
                    "«%s» -> «%s»", cerebrum_fnr, fnr)

    # A mismatch in passnr only means that Cerebrum's data has to be updated.
    if (cerebrum_passnr and cerebrum_passnr != passnr):
        person_id_cerebrum = passnr2person_id(passnr)

        # *IF* there is a person in cerebrum that already holds passnr, AND
        # it's a different person than the one we've associated with sap_id,
        # then we cannot update passnr, because then two different people would
        # share the same passnr. However, if the passnr did not exist in
        # cerebrum before, person_id_cerebrum would be None (and different from
        # person.entity_id). Both branches of the test are necessary.
        if ((person_id_cerebrum is not None) and
                person.entity_id != person_id_cerebrum):
            logger.error(
                "Should update PASSNR for %s, but another person (%s) with "
                "PASSNR (%s) exists in Cerebrum",
                person_id_cerebrum,
                sap_id,
                passnr)
            return False
        logger.info("PASSNR in Cerebrum != PASSNR in datafile. Updating "
                    "«%s» -> «%s»", cerebrum_passnr, passnr)
    return True


def fnr2person_id(fnr):
    """Locate person_id owning fnr, if any.

    We need to be able to remap a fnr (from file) to a person_id.
    """

    person = Factory.get("Person")(database)
    try:
        person.find_by_external_id(const.externalid_fodselsnr, fnr)
        return person.entity_id
    except Errors.NotFoundError:
        return None

    # NOTREACHED
    assert False


def passnr2person_id(passnr):
    """Locate person_id owning passnr, if any.

    We need to be able to remap a passnr (from file) to a person_id.
    """

    person = Factory.get("Person")(database)
    try:
        person.find_by_external_id(const.externalid_pass_number, passnr)
        return person.entity_id
    except Errors.NotFoundError:
        return None

    # NOTREACHED
    assert False


def populate_external_ids(tpl):
    """
    Locate (or create) a person holding the IDs contained in FIELDS and
    register these external IDs if necessary.

    This function both alters the PERSON object and retuns a boolean value
    (True means the ID update/lookup was successful, False means the
    update/lookup failed and nothing can be ascertained about the PERSON's
    state).

    There are two external IDs in SAP -- the Norwegian social security number
    (11-siffret personnummer, fnr) and the SAP employee id (sap_id). SAP IDs
    are (allegedly) permanent and unique, fnr can change.

    Sometimes a third is also present, passport number.
    """

    error, person = locate_person(tpl.sap_ansattnr,
                                  tpl.sap_fnr,
                                  tpl.sap_passnr)
    if error:
        logger.error("Lookup for (sap_id; fnr; passnr) == (%s; %s; %s) failed",
                     tpl.sap_ansattnr, tpl.sap_fnr, tpl.sap_passnr)
        return None

    if person is not None:
        logger.debug("A person owning IDs (%s, %s, %s) already exists",
                     tpl.sap_ansattnr, tpl.sap_fnr, tpl.sap_passnr)
        # Now, we *must* check that the IDs registered in Cerebrum match
        # those in SAP dump. I.e. we select the external IDs from Cerebrum
        # and compare them to SAP_ID and FNR. They must either match
        # exactly or be absent.
        if not match_external_ids(person, tpl.sap_ansattnr, tpl.sap_fnr,
                                  tpl.sap_passnr):
            return None
    else:
        person = Factory.get("Person")(database)
        logger.debug("New person for IDs (%s, %s, %s)",
                     tpl.sap_ansattnr, tpl.sap_fnr, tpl.sap_passnr)

    try:
        fodselsnr.personnr_ok(tpl.sap_fnr, accept_00x00=False)
    except fodselsnr.InvalidFnrError:
        # IVR 2007-02-15 It is *wrong* to simply ignore these, but since they
        # do occur, and they may be difficult to get rid of, we'll downgrade
        # the severity to avoid being spammed to death.
        if not tpl.sap_passnr:
            logger.info("No valid checksum for FNR (%s)! "
                        "And not PASSNR as backup", tpl.sap_fnr)
            return None
        logger.info("No valid checksum for FNR (%s)! "
                    "using PASSNR instead", tpl.sap_fnr)
        tpl.sap_fnr = None
        gender = const.gender_unknown
    else:
        gender = const.gender_male
        if fodselsnr.er_kvinne(tpl.sap_fnr):
            gender = const.gender_female

    # This would allow us to update birthdays and gender information for
    # both new and existing people.
    person.populate(tpl.sap_birth_date, gender)
    person.write_db()

    extid_sync = ExternalIdSync(database, const.system_sap)
    extid_values = [(const.externalid_sap_ansattnr, tpl.sap_ansattnr)]

    if tpl.sap_fnr:
        extid_values.append((const.externalid_fodselsnr, tpl.sap_fnr))
    if tpl.sap_passnr:
        extid_values.append((const.externalid_pass_number, tpl.sap_passnr))

    extid_sync(person, extid_values)
    return person


def populate_names(person, fields):
    """
    Extract all name forms from FIELDS and populate PERSON with these.
    """

    name_types = ((const.name_first, fields.sap_first_name),
                  (const.name_last, fields.sap_last_name),
                  (const.name_initials, fields.sap_initials),)

    person.affect_names(const.system_sap,
                        *[x[0] for x in name_types])

    for name_type, name_value in name_types:
        if (not name_value) or (name_type in (const.name_first,)):
            continue

        person.populate_name(name_type, name_value)
        logger.debug("Populated name type %s with «%s»", name_type,
                     name_value)

    person.populate_name(const.name_first, fields.sap_first_name)


def populate_personal_title(person, fields):
    """Register personal title for person."""

    source_title = fields.sap_personal_title
    if source_title:
        person.add_name_with_language(name_variant=const.personal_title,
                                      name_language=const.language_nb,
                                      name=source_title)
        logger.debug("Added %s '%s' for person id=%s",
                     const.personal_title, source_title, person.entity_id)
    else:
        person.delete_name_with_language(name_variant=const.personal_title,
                                         name_language=const.language_nb)
        logger.debug("Removed %s for person id=%s",
                     const.personal_title, person.entity_id)


def _remove_communication(person, comm_type):
    """Delete a person's given communication type."""
    logger.debug("Removing comm type %s", comm_type)
    person.delete_contact_info(const.system_sap, comm_type)


def populate_communication(person, fields):
    """
    Extract all communication forms from FIELDS and populate PERSON with
    these.
    """

    comm_types = ((const.contact_phone_private, fields.sap_phone_private),
                  (const.contact_phone, fields.sap_phone),
                  (const.contact_fax, fields.sap_fax))
    for comm_type, comm_value in comm_types:
        if not comm_value:
            continue

        person.populate_contact_info(const.system_sap, comm_type, comm_value)
        logger.debug("Populated comm type %s with «%s»", comm_type,
                     comm_value)

    # some communication types need extra care
    comm_types = ((const.contact_mobile_phone,
                   fields.sap_phone_mobile),
                  (const.contact_private_mobile,
                   fields.sap_phone_mobile_private))
    for comm_type, comm_value in comm_types:
        if not comm_value:
            _remove_communication(person, comm_type)
            continue
        person.populate_contact_info(const.system_sap, comm_type, comm_value)
        logger.debug("Populated comm type %s with «%s»", comm_type,
                     comm_value)


def _remove_office(person):
    """Remove a person's office address and the corresponding contact info."""
    logger.debug("Removing office address and contact info for person=%s",
                 person.entity_id)
    person.delete_contact_info(source=const.system_sap,
                               contact_type=const.contact_office)
    person.delete_entity_address(const.system_sap, const.address_street)


def populate_office(person, fields):
    """Populate person with office address

    Extract the person's office address from FIELDS and populate the
    database with it, if it is defined. Both a building code and a room number
    should be present to be stored.

    Note that we are not importing the office address if the given building
    codes doesn't exist in cereconf.

    """
    if not fields.sap_building_code or not fields.sap_roomnumber:
        # both building and room has to be defined

        # debug for counting half registrations:
        if fields.sap_building_code or fields.sap_roomnumber:
            logger.debug('Office address not fully registered, skipping %s',
                         person.entity_id)
        _remove_office(person)
        return

    address = cereconf.BUILDING_CODES.get(fields.sap_building_code, None)
    if not address:
        logger.debug('Office building code invalid for %s: "%s"',
                     person.entity_id, fields.sap_building_code)
        _remove_office(person)
        return

    person.populate_contact_info(source_system=const.system_sap,
                                 type=const.contact_office,
                                 value=fields.sap_building_code,
                                 alias=fields.sap_roomnumber or None)

    country = None
    if 'country_street' in address:
        try:
            country = int(const.Country(address['country_street']))
        except Errors.NotFoundError:
            logger.warn("Could not find country code for «%s», "
                        "please define country in Constants.py",
                        address['country_street'])
        # TBD: should we return here if country is not correct, or is it okay
        # to just set it to None?
    try:
        person.populate_address(source_system=const.system_sap,
                                type=const.address_street,
                                address_text=address['street'],
                                postal_number=address['postnr_street'],
                                city=address['city_street'],
                                country=country)
    except KeyError as e:
        logger.warn('Building code translation error for code %s: %s',
                    fields.sap_building_code, e)
        return
    logger.debug('Populated office address for %s: building="%s", room="%s"',
                 person.entity_id,
                 fields.sap_building_code,
                 fields.sap_roomnumber)


def populate_address(person, fields):
    """Extract the person's address from FIELDS and populate the database with
    it.

    Unfortunately, there is no direct mapping between the way SAP represents
    addresses and the way Cerebrum models them, so we hack away one pretty
    godawful mess.
    """

    country = None
    if fields.sap_country:
        try:
            country = int(const.Country(fields.sap_country))
        except Errors.NotFoundError:
            logger.warn("Could not find country code for «%s», "
                        "please define country in Constants.py",
                        fields.sap_country)

    postal_number = fields.sap_zip
    if postal_number is not None and len(postal_number) > 32:
        logger.warn("Cannot register zip code for %s (%s): len(%s) > 32",
                    person.entity_id, person.get_names(),
                    postal_number)
        postal_number = None

    person.populate_address(const.system_sap,
                            const.address_post,
                            address_text=fields.sap_address,
                            postal_number=postal_number,
                            city=fields.sap_city,
                            country=country)


def add_person_to_group(person, fields):
    """
    Check if person should be visible in catalogs like LDAP or not. If
    latter, add the person to a group specified in cereconf.
    """
    # Test if person should be visible in catalogs like LDAP
    if not fields.reserved_for_export():
        return

    # TODO: This function never *removes* persons.  Should we not always sync
    # this attribute based on the `fields.reserved_for_export()` result?
    group = Factory.get("Group")(database)
    # person should not be visible. Add person to group
    try:
        group_name = cereconf.HIDDEN_PERSONS_GROUP
        group.find_by_name(group_name)
    except AttributeError:
        logger.warn("Cannot add person to group. " +
                    "Group name not set in cereconf.")
        return
    except Errors.NotFoundError:
        logger.warn("Could not find group with name %s" % group_name)
        return

    if group.has_member(person.entity_id):
        logger.info("Person %s is already member of group %s" % (
            person.get_name(const.system_cached, const.name_full), group_name))
        return
    try:
        group.add_member(person.entity_id)
    except Exception:
        logger.warn("Could not add person %s to group %s" % (
            person.get_name(const.system_cached, const.name_full), group_name))
        return

    logger.info("OK, added %s to group %s" % (
        person.get_name(const.system_cached, const.name_full), group_name))


def process_people(filename, use_fok, passnr_mapping):
    """Scan filename and perform all the necessary imports.

    Each line in filename contains SAP information about one person.
    """
    processed_persons = set()
    with io.open(filename, 'r', encoding=('latin1')) as f:
        for p in make_person_iterator(
                f, use_fok, logger):
            if not p.valid():
                logger.debug(
                    "Ignoring person sap_id=%s, fnr=%s (invalid entry)",
                    p.sap_ansattnr, p.sap_fnr)
                # TODO: remove some person data?
                continue

            if p.expired():
                logger.info("Ignoring person sap_id=%s, fnr=%s (expired data)",
                            p.sap_ansattnr, p.sap_fnr)
                # TODO: remove some person data?
                continue

            try:
                p.sap_passnr = passnr_mapping[p.sap_ansattnr]
            except KeyError:
                p.sap_passnr = None

            # If the IDs are inconsistence with Cerebrum, skip the record
            person = populate_external_ids(p)
            if person is None:
                logger.info(
                    "Ignoring person sap_id=%s, fnr=%s "
                    "(inconsistent IDs in Cerebrum)",
                    p.sap_ansattnr, p.sap_fnr)
                continue

            populate_names(person, p)

            populate_communication(person, p)

            if hasattr(const, 'contact_office'):
                populate_office(person, p)

            populate_address(person, p)

            add_person_to_group(person, p)

            populate_personal_title(person, p)

            # Sync person object with the database
            person.write_db()
            processed_persons.add(person.entity_id)
    return processed_persons


def clean_person_data(processed_persons):
    """
    Removes information from unprocessed person objects.

    :param set processed_persons:
        A set of persons to *not* clear data from.

        This should be all the persons that have been processed/identified from
        the source files.
    """
    person = Factory.get('Person')(database)
    source_system = person.const.system_sap
    title_type = person.const.personal_title
    title_lang = person.const.language_nb

    clear_contact_info = set(
        row['entity_id']
        for row in person.list_contact_info(source_system=source_system)
    ) - processed_persons

    clear_addr_info = set(
        row['entity_id']
        for row in person.list_entity_addresses(source_system=source_system)
    ) - processed_persons

    clear_name_with_lang = set(
        row['entity_id']
        for row in person.search_name_with_language(name_variant=title_type,
                                                    name_language=title_lang)
    ) - processed_persons

    # We join together and process person by person in order to reduce the
    # number of person.find()/person.clear() to do
    persons_to_clear = (clear_contact_info
                        | clear_addr_info
                        | clear_name_with_lang)

    for person_id in persons_to_clear:
        logger.info('Clearing contact info, addresses and title '
                    'for person_id:{}'.format(person_id))
        person.clear()
        person.find(person_id)
        if person_id in clear_contact_info:
            person.populate_contact_info(source_system)
        if person_id in clear_addr_info:
            person.populate_address(source_system)

        if person_id in clear_name_with_lang:
            person.delete_name_with_language(name_variant=title_type,
                                             name_language=title_lang)
        person.write_db()


def create_passnr_mapping(passnr_file):
    """
    Make a mapping between SAP ID and PASSNR

    :return: dictionary mapping with SAP ID as key and PASSNR as value
    """
    passnr_map = {}
    with io.open(passnr_file, 'r', encoding='utf-8') as f:
        for p in make_passnr_iterator(f, logger):
            if p.sap_passnr and p.sap_passcountry:
                pass_id = p.sap_passcountry + '-' + p.sap_passnr
                passnr_map[p.sap_ansattnr] = pass_id
    return passnr_map


def main():
    global database, const

    parser = argparse.ArgumentParser(description=__doc__)
    required_args = parser.add_argument_group('required arguments')
    required_args.add_argument(
        '-p', '--person-file',
        dest='person_file',
        required=True,
        help='File containing person data-export from SAP.',
    )
    parser.add_argument(
        '--without-fok',
        action='store_false',
        default=True,
        dest='use_fok',
        help=(
            'Do not use forretningsområdekode for checking '
            'if a person should be imported. (default: use.)'
        ),
    )
    parser.add_argument(
        '--passnr-file',
        help=(
            'Additional file with SAP ID -> PASSNR mapping '
            'that will be used if fnr is missing.'
        ),
    )
    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    database = Factory.get("Database")()
    database.cl_init(change_program='import_SAP')
    const = Factory.get("Constants")(database)

    passport_mapping = {}
    if args.passnr_file:
        passport_mapping = create_passnr_mapping(args.passnr_file)

    processed_persons = process_people(args.person_file,
                                       args.use_fok,
                                       passport_mapping)

    clean_person_data(processed_persons)

    if args.commit:
        database.commit()
        logger.info("Committed all changes")
    else:
        database.rollback()
        logger.info("Rolled back all changes")


if __name__ == "__main__":
    main()
