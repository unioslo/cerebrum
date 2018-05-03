#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2018 University of Oslo, Norway
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

"""This file is a DFØ-SAP extension of Cerebrum.

It contains code which imports SAP-specific person/employee information into
Cerebrum.

FIXME: I wonder if the ID lookup/population logic might fail in a subtle
way, should an update process (touching IDs) run concurrently with this
import.
"""

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia.mod_sap_utils import make_person_iterator
from Cerebrum.modules.no import fodselsnr

import io
import argparse


def locate_person(sap_id, fnr):
    """Locate a person who owns both SAP_ID and FNR.

    NB! A situation where both IDs are set, but point to people with different
    person_id's is considered an error.

    @rtype: tuple (boolean, Person proxy)
    @return:
      A tuple, where first item indicates whether id match triggered an error,
      and the second item is the Person associated with the id (or None, if no
      such association exists in Cerebrum)
    """

    person = Factory.get("Person")(database)
    logger.debug(u"Locating person with SAP_id = «%s» and FNR = «%s»",
                 sap_id, fnr)

    person_id_from_sap = None
    person_id_from_fnr = None

    try:
        person.clear()
        person.find_by_external_id(const.externalid_sap_ansattnr,
                                   sap_id, const.system_sap)
        person_id_from_sap = int(person.entity_id)
    except Errors.NotFoundError:
        logger.debug(u"No person matches SAP id «%s»", sap_id)

    try:
        person.clear()
        person.find_by_external_id(const.externalid_fodselsnr,
                                   fnr)
        person_id_from_fnr = int(person.entity_id)
    except Errors.NotFoundError:
        logger.debug(u"No person matches FNR «%s»", fnr)
    except Errors.TooManyRowsError:
        logger.error("Multiple person match FNR <%s>", fnr)
        return True, None

    # Now, we can compare person_id_from_*. If they are both set, they must
    # point to the same person (otherwise, we'd have two IDs in the *same
    # SAP entry* pointing to two different people in Cerebrum). However, we
    # should also allow the possibility of only one ID being set.
    if (person_id_from_sap is not None and
        person_id_from_fnr is not None and
            person_id_from_sap != person_id_from_fnr):
        logger.error("Aiee! IDs for logically the same person differ: "
                     "(SAP id => person_id %s; FNR => person_id %s)",
                     person_id_from_sap, person_id_from_fnr)
        return True, None

    already_exists = (person_id_from_sap is not None or
                      person_id_from_fnr is not None)
    # Make sure, that person is associated with the corresponding db rows
    if already_exists:
        person.clear()
        pid = person_id_from_sap
        if pid is None:
            pid = person_id_from_fnr
        person.find(pid)
        return False, person

    return False, None


def match_external_ids(person, sap_id, fnr):
    """
    Make sure that PERSON's external IDs in Cerebrum match SAP_ID and FNR.
    """

    cerebrum_sap_id = person.get_external_id(const.system_sap,
                                             const.externalid_sap_ansattnr)
    cerebrum_fnr = person.get_external_id(const.system_sap,
                                          const.externalid_fodselsnr)

    # There is at most one such ID, get_external_id returns a sequence, though
    if cerebrum_sap_id:
        cerebrum_sap_id = str(cerebrum_sap_id[0]["external_id"])

    if cerebrum_fnr:
        cerebrum_fnr = str(cerebrum_fnr[0]["external_id"])

    if (cerebrum_sap_id and cerebrum_sap_id != sap_id):
        logger.error("SAP id in Cerebrum != SAP id in datafile "
                     u"«%s» != «%s»", cerebrum_sap_id, sap_id)
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
                    u"«%s» -> «%s»", cerebrum_fnr, fnr)

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
    """

    error, person = locate_person(tpl.sap_ansattnr, tpl.sap_fnr)
    if error:
        logger.error("Lookup for (sap_id; fnr) == (%s; %s) failed",
                     tpl.sap_ansattnr, tpl.sap_fnr)
        return None

    if person is not None:
        logger.debug("A person owning IDs (%s, %s) already exists",
                     tpl.sap_ansattnr, tpl.sap_fnr)
        # Now, we *must* check that the IDs registered in Cerebrum match
        # those in SAP dump. I.e. we select the external IDs from Cerebrum
        # and compare them to SAP_ID and FNR. They must either match
        # exactly or be absent.
        if not match_external_ids(person,
                                  tpl.sap_ansattnr, tpl.sap_fnr):
            return None
    else:
        person = Factory.get("Person")(database)
        logger.debug("New person for IDs (%s, %s)",
                     tpl.sap_ansattnr, tpl.sap_fnr)

    try:
        fodselsnr.personnr_ok(tpl.sap_fnr, accept_00X00=False)
    except fodselsnr.InvalidFnrError:
        # IVR 2007-02-15 It is *wrong* to simply ignore these, but since they
        # do occur, and they may be difficult to get rid of, we'll downgrade
        # the severity to avoid being spammed to death.
        logger.info("No valid checksum for FNR (%s)!", tpl.sap_fnr)
        return None

    gender = const.gender_male
    if fodselsnr.er_kvinne(tpl.sap_fnr):
        gender = const.gender_female

    # This would allow us to update birthdays and gender information for
    # both new and existing people.
    person.populate(tpl.sap_birth_date, gender)
    person.affect_external_id(const.system_sap,
                              const.externalid_fodselsnr,
                              const.externalid_sap_ansattnr)
    person.populate_external_id(const.system_sap,
                                const.externalid_sap_ansattnr,
                                tpl.sap_ansattnr)
    person.populate_external_id(const.system_sap,
                                const.externalid_fodselsnr,
                                tpl.sap_fnr)
    person.write_db()
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
        logger.debug(u"Populated name type %s with «%s»", name_type, name_value)

    person.populate_name(const.name_first, fields.sap_first_name)


def populate_personal_title(person, fields):
    """Register personal title for person."""

    source_title = fields.sap_personal_title
    if source_title:
        person.add_name_with_language(name_variant=const.personal_title,
                                      name_language=const.language_nb,
                                      name=source_title)
        logger.debug("Added %s '%s' for person id=%s",
                     str(const.personal_title), source_title, person.entity_id)
    else:
        person.delete_name_with_language(name_variant=const.personal_title,
                                         name_language=const.language_nb)
        logger.debug("Removed %s for person id=%s",
                     str(const.work_title), person.entity_id)


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
        logger.debug(u"Populated comm type %s with «%s»", comm_type, comm_value)

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
        logger.debug(u"Populated comm type %s with «%s»", comm_type, comm_value)


def _remove_office(person):
    """Remove a person's office address and the corresponding contact info."""
    logger.debug("Removing office address and contact info for person=%s",
                 person.entity_id)
    person.delete_contact_info(source=const.system_sap,
                               contact_type=const.contact_office)
    person.delete_entity_address(const.system_sap, const.address_street)


def populate_office(person, fields):
    """Extract the person's office address from FIELDS and populate the database
    with it, if it is defined. Both a building code and a room number should be
    present to be stored.

    Note that we are not importing the office address if the given building
    codes doesn't exist in cereconf."""
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
            logger.warn(u"Could not find country code for «%s», "
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
    except KeyError, e:
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
            logger.warn(u"Could not find country code for «%s», "
                        "please define country in Constants.py",
                        fields.sap_country)

    postal_number = fields.sap_zip
    if postal_number is not None and len(postal_number) > 32:
        logger.warn("Cannot register zip code for %s (%s): len(%s) > 32",
                    person.entity_id, person.get_all_names(),
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
    except:
        logger.warn("Could not add person %s to group %s" % (
            person.get_name(const.system_cached, const.name_full), group_name))
        return

    logger.info("OK, added %s to group %s" % (
        person.get_name(const.system_cached, const.name_full), group_name))


def process_people(filename, use_fok):
    """Scan filename and perform all the necessary imports.

    Each line in filename contains SAP information about one person.
    """
    processed_persons = set()
    with io.open(filename, 'r', encoding=('latin1')) as f:
        for p in make_person_iterator(
                f, use_fok, logger):
            if not p.valid():
                logger.info("Ignoring person sap_id=%s, fnr=%s (invalid entry)",
                            p.sap_ansattnr, p.sap_fnr)
                # TODO: remove some person data?
                continue

            if p.expired():
                logger.info("Ignoring person sap_id=%s, fnr=%s (expired data)",
                            p.sap_ansattnr, p.sap_fnr)
                # TODO: remove some person data?
                continue

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
    """Removes information from person objects.

    :param set processed_persons: Person ids which information should not be
        removed from."""
    person = Factory.get('Person')(database)
    existing_persons = set(map(lambda x: x['person_id'],
                               person.list_persons()))
    for person_id in existing_persons - processed_persons:
        logger.info('Clearing contact info, addresses and title '
                    'for person_id:{}'.format(person_id))
        person.clear()
        person.find(person_id)
        person.populate_contact_info(const.system_sap)
        person.populate_address(const.system_sap)
        person.delete_name_with_language(name_variant=const.personal_title,
                                         name_language=const.language_nb)
        person.write_db()


def main():
    global logger
    logger = Factory.get_logger('cronjob')

    parser = argparse.ArgumentParser(description=__doc__)
    required_args = parser.add_argument_group('required arguments')
    required_args.add_argument('-p', '--person-file', dest='person_file',
                               required=True,
                               help='File containing person data-export '
                                    'from SAP.')
    parser.add_argument('--without-fok',
                        action='store_false',
                        default=True,
                        dest='use_fok',
                        help='Do not use forretningsområdekode for checking '
                             'if a person should be imported. (default: use.)')
    parser.add_argument('-c', '--commit',
                        dest='commit',
                        default=False,
                        action='store_true',
                        help='Write changes to DB.')
    args = parser.parse_args()

    # Creating this locally costs about 20 seconds out of a 3 minute run.
    global const
    const = Factory.get("Constants")()

    global database
    database = Factory.get("Database")()
    database.cl_init(change_program='import_SAP')

    processed_persons = process_people(args.person_file, args.use_fok)
    clean_person_data(processed_persons)

    if args.commit:
        database.commit()
        logger.info("Committed all changes")
    else:
        database.rollback()
        logger.info("Rolled back all changes")


if __name__ == "__main__":
    main()
