#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2019 University of Oslo, Norway
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
import_sito.py can import person and/or ou data into BAS.

The person and ou files are xml files generated by SITO HR systems.
"""
from __future__ import print_function, unicode_literals

import argparse
import datetime
import logging
import os
import xml.etree.ElementTree

import mx.DateTime

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.entity_expire.entity_expire import EntityExpiredError
from Cerebrum.modules.no import fodselsnr
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.modules.no.uit import OU

logger = logging.getLogger(__name__)


# SITO OUs does not have a Stedkode - we'll need to populate and use the raw
# OU-class without Stedkode mixin.
OU_Class = OU.OUMixin


class SkipPerson(Exception):
    pass


def parse_date(date_str):
    """
    Parse a date on the strfdate format "%Y-%m-%d".

    :rtype: datetime.date
    :return: Returns the date object, or ``None`` if an invalid date is given.
    """
    if not date_str:
        raise ValueError('Invalid date %r' % (date_str, ))
    args = (int(date_str[0:4]),
            int(date_str[5:7]),
            int(date_str[8:10]))
    return datetime.date(*args)


def date_in_range(date, from_date=None, to_date=None):
    """
    Checks if a given date is within a date range.

    If any of the thresholds (from_date, to_date) is ``None``, that threshold
    will not be checked. I.e. ``date_in_range(<some date>)`` will *always* be
    ``True``.

    :param date: The date or datetime to check
    :param from_date: lower threshold, inclusive, if this needs to be checked.
    :param to_date: upper threshold, if this needs to be checked

    :rtype: bool
    :return: True if date is within the given range.
    """
    if from_date is not None and date < from_date:
        return False
    if to_date is not None and date >= to_date:
        return False
    return True


# XML-Type to contact info code
phone_mapping = {
    'CellPhone': 'contact_mobile_phone',
    'Home': 'contact_phone_private',
    'DirectNumber': 'contact_phone',
}


def parse_person_phones(person):
    """
    Parse person phone numbers.

    :param person: A //Persons/Person element

    :rtype: generator
    :return: A generator that yield (phone_type, phone_number) pairs
    """
    for phone in person.findall('./Phones/Phone'):
        try:
            p_type = (phone.find('./Type').text or '').strip()
            p_number = (phone.find('./Number').text or '').strip()
        except AttributeError as e:
            logger.debug('Skipping phone=%r: %s', phone, e)

        if p_number and p_type in phone_mapping.keys():
            yield phone_mapping[p_type], p_number


def parse_person_employments(person):
    """
    Parse a single employment value.

    :param person: A //Persons/Person element

    :rtype: generator
    :return:
        A generator that yields (employment_title, employment_unit) pairs
    """
    today = datetime.date.today()
    # We know this exists from parse_person
    employee_id = person.find('EmploymentInfo/Employee/EmployeeNumber').text

    for employment in person.findall('EmploymentInfo/Employee/'
                                     'Employment/Employment'):

        unit = employment.find('EmploymentDistributionList/'
                               'EmploymentDistribution/Unit/Value').text

        try:
            from_date = parse_date(employment.find('FromDate').text)
        except ValueError:
            from_date = None
        try:
            to_date = parse_date(employment.find('ToDate').text)
        except ValueError:
            to_date = None

        if not date_in_range(today, from_date, to_date):
            logger.debug('Skipping non-current employment for employee_id=%r '
                         'at unit=%r', employee_id, unit)
            continue

        try:
            title = employment.find('Position/Name').text
        except Exception:
            logger.info('Unable to get employment title for employee_id=%r '
                        'at unit=%r', employee_id, unit)
            title = None

        yield title, unit


def parse_person(person):
    """
    Parse a Person xml element.

    :param person: A //Persons/Person element

    :rtype: dict
    :return: A dictionary with normalized values.
    """
    required = object()
    employee_id = None

    def get(xpath, default=None):
        elem = person.find(xpath)
        if elem is None or not elem.text:
            logger.warning('Missing element %r for employee_id=%r',
                           xpath, employee_id)
            if default is required:
                raise SkipPerson(
                    'Missing required element %r, employee_id=%r'
                    % (xpath, employee_id))
            else:
                return default
        else:
            return (elem.text or '').strip()

    # Mandatory params
    employee_id = get('EmploymentInfo/Employee/EmployeeNumber', required)
    deactivated = get('IsDeactivated', required) != 'false'

    person_dict = {
        'employee_id': employee_id,
        'ssn': get('SocialSecurityNumber', ''),
        'gender': get('Gender'),
        'birthdate': get('BirthDate', ''),
        'first_name': get('FirstName', required),
        'middle_name': get('MiddleName'),
        'last_name': get('LastName', required),
        'title': None,
        'Email': get('EMailAddresses/EMailAddress/Address'),
        'is_deactivated': deactivated,
    }

    # Affiliation and title
    #
    afflist = list()
    for title, unit in parse_person_employments(person):
        if title and unit not in afflist:
            person_dict['title'] = title
        if unit not in afflist:
            afflist.append(unit)

    if len(afflist) > 0:
        logger.debug('Got %d affiliations for employee_id=%r',
                     len(afflist), employee_id)
    person_dict['Affiliation'] = tuple(afflist)

    # Phone
    #
    person_dict['phone'] = dict(parse_person_phones(person))
    logger.debug('Got %d phone numbers for employee_id=%r',
                 len(person_dict['phone']), employee_id)
    return person_dict


def generate_persons(filename):
    """
    Find and parse employee data from an xml file.
    """
    if not os.path.isfile(filename):
        raise OSError('No file %r' % (filename, ))

    tree = xml.etree.ElementTree.parse(filename)
    root = tree.getroot()

    for i, person in enumerate(root.findall(".//Persons/Person"), 1):
        try:
            person_dict = parse_person(person)
        except SkipPerson as e:
            logger.warning('Skipping person #%d (element=%r): %s',
                           i, person, e)
            continue
        except Exception:
            logger.error('Skipping person #%d (element=%r), invalid data',
                         i, person, exc_info=True)
            continue

        if person_dict['is_deactivated']:
            logger.info('Skipping person #%d (employee_id=%r), deactivated',
                        i, person_dict['employee_id'])
            continue

        if not person_dict['Affiliation']:
            logger.info('Skipping person #%d (employee_id=%r), '
                        'no affiliations',
                        i, person_dict['employee_id'])
            continue

        yield person_dict


def parse_unit(unit):
    """
    Parse an ElementTree 'Unit' element.

    :param unit: A 'Unit' element

    :return: A dict-representation of the unit.
    """
    ou_dict = {
        'unit_id': unit.find('InternalInfo/Guid').text,
        'name': unit.find('Name').text,
        'is_deactivated': unit.find('IsDeactivated').text != 'false',
    }

    parent_id = unit.find('ParentUnitIdentifier/Value')
    if parent_id is not None:
        ou_dict['parent_id'] = parent_id.text

    return ou_dict


def generate_ous(filename):
    """
    Find and parse org unit data from an xml file.
    """
    if not os.path.isfile(filename):
        raise OSError('No file %r' % (filename, ))

    tree = xml.etree.ElementTree.parse(filename)
    root = tree.getroot()

    for i, unit in enumerate(root.findall(".//Units/Unit"), 1):
        try:
            ou_dict = parse_unit(unit)
        except Exception:
            logger.error('Unable to parse unit #%d, unit=%r', i, unit)
            raise

        if ou_dict['is_deactivated']:
            logger.info('Skipping unit #%d, disabled', i)
            continue

        yield ou_dict


def load_sito_affiliations(db):
    person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)
    affi_list = set()
    for row in person.list_affiliations(source_system=const.system_sito):
        key_l = "%s:%s:%s" % (row['person_id'], row['ou_id'],
                              row['affiliation'])
        affi_list.add(key_l)
    return affi_list


def remove_old_affiliations(db, affiliations):
    new_person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)

    for aff_key in affiliations:
        [ent_id, ou, affi] = [int(x) for x in aff_key.split(':')]
        new_person.clear()
        new_person.entity_id = int(ent_id)
        affs = new_person.list_affiliations(
            ent_id,
            affiliation=affi,
            ou_id=ou,
            source_system=const.system_sito)
        for aff in affs:
            last_date = datetime.datetime.fromtimestamp(aff['last_date'])
            end_grace_period = (
                last_date +
                datetime.timedelta(
                    days=cereconf.GRACEPERIOD_EMPLOYEE_SITO))
            if datetime.datetime.today() > end_grace_period:
                logger.warn(
                    "Deleting system_sito affiliation for "
                    "person_id=%s,ou=%s,affi=%s last_date=%s,grace=%s",
                    ent_id, ou, affi, last_date,
                    cereconf.GRACEPERIOD_EMPLOYEE_SITO)
                new_person.delete_affiliation(ou, affi, const.system_sito)


def import_person(db, person, update_affs=None):
    """
    Import a single person.

    :param person:
        A dict from py:func:`parse_person`
    :param update_affs:
        A set of affiliations from py:func:`load_sito_affiliations`.
        Affiliations imported by this function will be removed from the set.
    """
    new_person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)

    if update_affs is None:
        update_affs = set()

    employee_id = person['employee_id']
    logger.info("Processing employee_id=%r", employee_id)

    #
    # Validate person data
    #

    # Birthdate
    try:
        birthdate = parse_date(person['birthdate'])
        valid_birthdate = True
    except ValueError:
        logger.warning('Invalid birth date for employee_id=%r (%r)',
                       person['employee_id'], person['birthdate'])
        valid_birthdate = False
        birthdate = None

    # SSN
    try:
        fodselsnr.personnr_ok(person['ssn'])
        valid_ssn = True
    except fodselsnr.InvalidFnrError:
        logger.warning("Empty SSN for employee_id=%r",
                       person['employee_id'])
        valid_ssn = False

    # set person gender (checking both SSN and gender from sito input file)
    if valid_ssn:
        if fodselsnr.er_kvinne(person['ssn']):
            gender = const.gender_female
        else:
            gender = const.gender_male
    elif person['gender'] == 'Female':
        gender = const.gender_female
    elif person['gender'] == 'Male':
        gender = const.gender_male
    else:
        logger.warning('Unknown gender value for employee_id=%r (%r)',
                       employee_id, person['gender'])
        gender = const.gender_unknown

    # Validate Birthdate against SSN
    if valid_ssn and valid_birthdate:
        ssndate = datetime.date(*fodselsnr.fodt_dato(person['ssn']))
        if birthdate != ssndate:
            raise SkipPerson('inconsistent birth date and ssn (%r, %r)',
                             birthdate, ssndate)
    elif valid_ssn and not valid_birthdate:
        logger.warning('Missing birth date for employee_id=%r, using date'
                       ' from ssn', person['employee_id'])
        birthdate = datetime.date(*fodselsnr.fodt_dato(person['ssn']))
    elif not valid_ssn and valid_birthdate:
        # person have birthdate but NOT ssn. Nothing to do here
        pass
    elif not valid_ssn and not valid_birthdate:
        # person does not have birthdate nor ssn. This person cannot be
        # built.  SSN or Birthdate required. Return error message and
        # continue with NEXT person
        raise SkipPerson('missing ssn and birth date')

    # Check names
    if not person['first_name']:
        raise SkipPerson('Missing first name')
    if not person['last_name']:
        raise SkipPerson('Missing last name')

    if person['middle_name']:
        fname = person['first_name'] + ' ' + person['middle_name']
    else:
        fname = person['first_name']
    lname = person['last_name']

    #
    # Get person object som DB if it exists
    #

    found = False
    new_person.clear()
    try:
        new_person.find_by_external_id(const.externalid_sito_ansattnr,
                                       employee_id)
        found = True
    except Errors.NotFoundError:
        # could not find person in DB based on ansattnr.
        if valid_ssn:
            # try to find person using ssn if ssn is valid
            try:
                new_person.clear()
                new_person.find_by_external_id(const.externalid_fodselsnr,
                                               person['ssn'])
                found = True
            except Errors.NotFoundError:
                pass
    if found:
        logger.info('Updating person object for employee_id=%r', employee_id)
    else:
        logger.info('Creating person object for employee_id=%r', employee_id)

    #
    # Populate the person object
    #

    new_person.populate(mx.DateTime.DateFrom(birthdate), gender)
    new_person.affect_names(const.system_sito, const.name_first,
                            const.name_last, const.name_work_title)
    new_person.affect_external_id(const.system_sito,
                                  const.externalid_fodselsnr,
                                  const.externalid_sito_ansattnr)
    new_person.populate_name(const.name_first, fname)
    new_person.populate_name(const.name_last, lname)

    if person['title']:
        new_person.populate_name(const.name_work_title,
                                 person['title'])
    if valid_ssn:
        new_person.populate_external_id(const.system_sito,
                                        const.externalid_fodselsnr,
                                        person['ssn'])
    new_person.populate_external_id(const.system_sito,
                                    const.externalid_sito_ansattnr,
                                    employee_id)

    # intermediary write to get an entity_id if this is a new person.
    new_person.write_db()

    new_person.populate_affiliation(const.system_sito)
    new_person.populate_contact_info(const.system_sito)

    # set person affiliation
    for key, ou_id, aff, status in determine_affiliations(
            db, new_person.entity_id, person):
        logger.info("affiliation for employee_id=%r to ou_id=%r",
                    employee_id, ou_id)
        new_person.populate_affiliation(const.system_sito, ou_id,
                                        int(aff), int(status))

        # set this persons affiliation entry to False
        # this ensures that this persons affiliations will not be removed
        # when the clean_affiliation function is called after import person
        update_affs.discard(key)

    # get person work, cellular and home phone numbers
    c_prefs = {}
    for con, number in person['phone'].items():
        c_type = int(const.human2constant(con, const.ContactInfo))
        if c_type in c_prefs:
            pref = c_prefs[c_type]
        else:
            pref = 0
            c_prefs[c_type] = 1
        new_person.populate_contact_info(const.system_sito,
                                         c_type, number, pref)
        logger.debug("contact for employee_id=%r, system=%s, "
                     "c_type=%s, number=%s, pref=%s",
                     employee_id, const.system_sito, c_type, number, pref)
    new_person.write_db()
    return not found


#
# import SITO persons into BAS
#
def import_persons(db, person_list, affiliations):
    """
    Import persons.
    """
    stats = {'added': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
    for person_dict in person_list:
        employee_id = person_dict['employee_id']
        try:
            if import_person(db, person_dict, affiliations):
                stats['added'] += 1
            else:
                stats['updated'] += 1
        except SkipPerson as e:
            logger.warning('Skipping employee_id=%r: %s', employee_id, e)
            stats['skipped'] += 1
        except Exception as e:
            logger.error('Skipping employee_id=%r: unhandled exception',
                         employee_id, exc_info=True)
            stats['import-person-error'] += 1

    logger.info("Processed %d persons: imported: %d, skipped: %d",
                sum(stats.values()),
                stats['added'] + stats['updated'],
                stats['skipped'] + stats['failed'])


#
# Get ou_id based on external_id
#
def get_ou(db, a, person):
    ou = OU_Class(db)
    const = Factory.get('Constants')(db)
    external_id = a.split(",")

    for single_id in external_id:
        ou.clear()
        try:
            ou.find_by_external_id(id_type=const.externalid_sito_ou,
                                   external_id=single_id,
                                   source_system=const.system_sito,
                                   entity_type=const.entity_ou)
        except EntityExpiredError:
            # person registered to expired OU. return error message.
            logger.error("person:%s is registered to expired OU "
                         "with external_id:%s", person['ssn'], single_id)
            return -1
        except Errors.NotFoundError:
            logger.error("WARNING - person:%s %s is registered to a "
                         "nonexisting OU with external id:%s",
                         person['first_name'], person['last_name'], single_id)
            return -1

        if single_id == cereconf.DEFAULT_SITO_ROOT_HASH:
            logger.info("person:%s has affiliation to SITO root node",
                        person['ssn'])
        return ou.entity_id


def determine_affiliations(db, entity_id, person):
    """
    Determine affiliations for a given person dict:

    :param entity_id: The person entity_id in cerebrum
    :param person: A dict with person info

    :rtype: generator
    :return:
        Returns a generator that yield tuples with:

        - key (string of "<person_id>:<ou_id>:<aff>")
        - ou_id
        - affiliation (Ansatt)
        - affiliation status (tekadn,adm)
    """
    const = Factory.get('Constants')(db)
    seen = set()
    aff = const.affiliation_ansatt_sito
    status = const.affiliation_status_ansatt_sito
    for a in person['Affiliation']:
        ou_id = get_ou(db, a, person)
        if ou_id == -1:
            # unable to find OU.
            logger.error("Got -1 from get_ou %s" % a)
            continue
        else:
            # valid ou id found. continue processing
            key = "%s:%s:%s" % (entity_id, ou_id, int(aff))
            if key not in seen:
                seen.add(key)
                yield key, ou_id, aff, status


def import_ous(db, ou_list):
    """
    Import OUs.

    :param ou_list: list of dicts with sito ou data (from py:func:`parse_unit`)
    """
    ou = OU_Class(db)
    const = Factory.get('Constants')(db)

    stats = {'added': 0, 'updated': 0, 'skipped': 0, 'failed': 0}

    # get sito ou's from BAS
    parent_list = []

    def populate_names(name, acronym, short_name, display_name, sort_name):
        lang = const.language_nb
        ou.add_name_with_language(const.ou_name, lang, name)
        ou.add_name_with_language(const.ou_name_acronym, lang, acronym)
        ou.add_name_with_language(const.ou_name_short, lang, short_name)
        ou.add_name_with_language(const.ou_name_display, lang, display_name)
        # TODO: don't know what to do with sort_name, ignoring it for now.

    #
    # insert or update SITO ou's in BAS
    #
    for sito_ou in ou_list:
        unit_id = sito_ou['unit_id']

        if sito_ou['is_deactivated']:
            logger.debug('Ignoring deactivated sito unit=%r', unit_id)
            continue
        else:
            logger.info("Processing sito unit=%r", unit_id)

        # clear ou structure
        ou.clear()

        # find ou in database if it already exists
        try:
            ou.find_by_external_id(id_type=const.externalid_sito_ou,
                                   external_id=unit_id,
                                   source_system=const.system_sito,
                                   entity_type=const.externalid_sito_ou)
        except Errors.NotFoundError:
            # New ou.
            logger.info("Creating OU for unit_id=%r (%s)", unit_id,
                        sito_ou['name'])
            ou.populate()
            ou.write_db()
            ou.affect_external_id(const.system_sito,
                                  const.externalid_sito_ou)
            ou.populate_external_id(source_system=const.system_sito,
                                    id_type=const.externalid_sito_ou,
                                    external_id=unit_id)
            ou.write_db()
            new_ou = True
        else:
            logger.info('Updating OU for unit_id=%r, entity_id=%r',
                        unit_id, ou.entity_id)
            new_ou = False

        #
        # Update OU names.
        #
        populate_names(sito_ou['name'], sito_ou['name'],
                       sito_ou['name'], sito_ou['name'], None)

        #
        # Create ou structure
        #
        found_parent = False
        for i in ou_list:
            parentid = {}
            try:
                # TODO: What if i['unit_id'] Is i['is_deactivated']?
                if sito_ou['parent_id'] == i['unit_id']:
                    parentid = {
                        'child': sito_ou['unit_id'],
                        'parent': i['unit_id'],
                    }
                    parent_list.append(parentid)
                    found_parent = True
                    break
            except Exception:
                pass

        if not found_parent:
            # ou has no parent, set parentID to 0 (root node)
            parentid = {
                'child': sito_ou['unit_id'],
                'parent': '0',
            }
            parent_list.append(parentid)

        if new_ou:
            stats['added'] += 1
        else:
            stats['updated'] += 1

    # Set parent for all ou's
    for parent in parent_list:
        if parent['parent'] == '0':
            parent_entity_id = None
        else:
            ou.clear()
            try:
                ou.find_by_external_id(id_type=const.externalid_sito_ou,
                                       external_id=parent['parent'],
                                       source_system=const.system_sito,
                                       entity_type=const.entity_ou)
                parent_entity_id = ou.entity_id
                ou.clear()
            except Errors.NotFoundError:
                # unable to find parent ou. Lets hope this is the root node.
                continue
        try:
            ou.clear()
            ou.find_by_external_id(id_type=const.externalid_sito_ou,
                                   external_id=parent['child'],
                                   source_system=const.system_sito,
                                   entity_type=const.externalid_sito_ou)

        except Errors.NotFoundError:
            # Unable to find child ou. This should be impossible, we've just
            # seen it when we build the parent_list...
            logger.error("Unable to find child ou with unit_id=%r",
                         parent['child'])

        #
        # At this point parent entity_id is stored in parent_entity_id  (if it
        # exists) ou class should contain a child of mentioned parent_entity_id
        #
        ou.set_parent(const.perspective_sito, parent_entity_id)
        ou.write_db()

    logger.info("Processed %d OUs: added: %d, updated: %d",
                sum(stats.values()),
                stats['added'], stats['updated'])


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Import SITO XML files into the Cerebrum database")

    parser.add_argument(
        '-p', '--person-file',
        help='Read and import persons from %(metavar)s',
        metavar='xml-file',
    )
    parser.add_argument(
        '-o', '--ou-file',
        help='Read and import org units from %(metavar)s',
        metavar='xml-file',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    if args.ou_file:
        logger.info('Fetching OUs from %r', args.ou_file)
        ou_list = list(generate_ous(args.ou_file))
        logger.info('Importing %d OUs', len(ou_list))
        import_ous(db, ou_list)
        logger.info('OU import done')

    if args.person_file:
        logger.info('Loading existing affiliations')
        aff_set = load_sito_affiliations(db)
        logger.info('Fetching persons from %r', args.person_file)
        person_list = list(generate_persons(args.person_file))
        logger.info('Importing %d persons', len(person_list))
        # Note: import_person updates the aff_set
        import_persons(db, person_list, aff_set)
        logger.info('Cleaning old affiliations')
        remove_old_affiliations(db, aff_set)
        logger.info('Person import done')

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        db.rollback()
        logger.info('Rolling back changes')
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
