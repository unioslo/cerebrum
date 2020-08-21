# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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

"""Module for populating a HRPerson based on data from sap

Usage:
>>> hr_id = event_to_hr_id(event)
>>> person_data = sap_client.get_employee(hr_id)
>>> assert person_data
>>> assignment_data = sap_client.get_assignments(hr_id) or []
>>> assignment_data = sap_client.get_assignments(hr_id) or []
>>> hr_person = populate_hr_person(person_data,
                                   assignment_data,
                                   role_data,
                                   database)
"""

import logging
import six

import cereconf

from collections import OrderedDict

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.hr_import.models import (HRPerson,
                                               HRAddress,
                                               HRTitle,
                                               HRAffiliation,
                                               HRExternalID,
                                               HRAccountType,
                                               HRContactInfo)
from Cerebrum.modules.automatic_group.structure import get_automatic_group

logger = logging.getLogger(__name__)

LEADER_GROUP_PREFIX = 'adm-leder-'


def populate_hr_person(person_data, assignment_data, role_data, database):
    """Populate a HRPerson object with data fetched from SAP

    :param person_data: Data from SAP `/employees`
    :param assignment_data: Data from SAP `/employees({personId})/assignments`
    :param role_data: Data from SAP `/employees({personId})/roles`
    :param database: Cerebrum database

    :rtype: HRPerson
    """

    co = Factory.get('Constants')(database)

    hr_person = HRPerson(
        hr_id=six.text_type(person_data.get('personId')),
        first_name=person_data.get('firstName'),
        last_name=person_data.get('lastName'),
        birth_date=person_data.get('dateOfBirth'),
        gender={'Kvinne': 'F', 'Mann': 'M'}.get(
            person_data.get('gender'), None
        ),
        reserved=not person_data.get('allowedPublicDirectoryFlag'),
        source_system=co.system_sap
    )
    hr_person.leader_groups = parse_leader_groups(assignment_data, database)
    hr_person.external_ids = parse_external_ids(person_data)
    hr_person.contact_infos = parse_contacts(person_data)
    hr_person.adddresses = parse_addresses(person_data, database)
    hr_person.titles = parse_titles(person_data, assignment_data)
    hr_person.affiliations, hr_person.account_types = parse_affiliations(
        assignment_data,
        role_data,
        database
    )
    return hr_person


def translate_keys(dict_, mapping):
    return {mapping[k]: v for k, v in six.iteritems(dict_) if k in mapping}


def filter_elements(dict_):
    return {k: v for k, v in six.iteritems(dict_) if k and v}


def parse_leader_groups(assignment_data, database):
    """Parse leader groups from SAP assignment data

    :rtype: set(int)
    :return: leader group ids where the person should be a member"""
    leader_group_ids = set()
    for x in assignment_data:
        if x.get('managerFlag'):
            leader_group_ids.add(
                get_automatic_group(database,
                                    six.text_type(x.get('locationId')),
                                    LEADER_GROUP_PREFIX).entity_id
            )
    logger.info('parsed %i leader groups', len(leader_group_ids))
    return leader_group_ids


def parse_addresses(person_data, database):
    """Parse addresses from `person_data`

    :rtype: set(HRAddress)"""

    co = Factory.get('Constants')(database)
    address_types = {'legalAddress': co.address_post_private,
                     'workMailingAddress': co.address_post,
                     'workVisitingAddress': co.address_street}
    key_map = {'city': 'city',
               'postalCode': 'postal_code',
               'streetAndHouseNumber': 'address_text'}
    addresses = set()
    for raw_address_type, crb_address_type in six.iteritems(address_types):
        address_dict = person_data.get(raw_address_type, None)
        if address_dict:
            if raw_address_type == 'workVisitingAddress':
                # Visiting address should be a concoction of real address and a
                # meta-location
                address_dict['streetAndHouseNumber'] = '{}\n{}'.format(
                    address_dict.get('streetAndHouseNumber'),
                    address_dict.get('location')
                )
            address_dict = translate_keys(address_dict, key_map)
            addresses.add(
                HRAddress(address_type=crb_address_type, **address_dict)
            )
    return addresses


def _sap_assignments_to_affiliation_map():
    co = Factory.get('Constants')
    return {'administrative': co.affiliation_status_ansatt_tekadm,
            'academic': co.affiliation_status_ansatt_vitenskapelig}


def _get_ou(database, placecode=None):
    """Populate a Cerebrum-OU-object from the DB."""
    if not placecode:
        return None
    ou = Factory.get('OU')(database)
    ou.clear()
    try:
        ou.find_stedkode(
            *map(''.join,
                 zip(*[iter(str(
                     placecode))] * 2)) + [cereconf.DEFAULT_INSTITUSJONSNR]
        )
        return ou
    except Errors.NotFoundError:
        return None


def _sap_roles_to_affiliation_map():
    co = Factory.get('Constants')
    return OrderedDict(
        [('INNKJØPER', co.affiliation_tilknyttet_innkjoper),
         ('EF-FORSKER', co.affiliation_tilknyttet_ekst_forsker),
         ('EMERITUS', co.affiliation_tilknyttet_emeritus),
         ('BILAGSLØNN', co.affiliation_tilknyttet_bilag),
         ('GJ-FORSKER', co.affiliation_tilknyttet_gjesteforsker),
         ('ASSOSIERT', co.affiliation_tilknyttet_assosiert_person),
         ('EF-STIP', co.affiliation_tilknyttet_ekst_stip),
         ('GRP-LÆRER', co.affiliation_tilknyttet_grlaerer),
         ('EKST-KONS', co.affiliation_tilknyttet_ekst_partner),
         ('PCVAKT', co.affiliation_tilknyttet_pcvakt),
         ('EKST-PART', co.affiliation_tilknyttet_ekst_partner),
         ('KOMITEMEDLEM', co.affiliation_tilknyttet_komitemedlem),
         ('STEDOPPLYS', None),
         ('POLS-ANSAT', None)])


def parse_roles(role_data, database):
    """Parse data from SAP and return existing roles.

    :rtype: set(HRAffiliation)"""

    role2aff = _sap_roles_to_affiliation_map()
    roles = set()
    for role in role_data:
        ou = _get_ou(database, placecode=role.get('locationId'))
        if not ou:
            logger.warn('OU %r does not exist, '
                        'cannot parse affiliation %r for %r',
                        role.get('locationId'),
                        role2aff.get(role.get('roleName')),
                        role_data.get('personId'))
        elif role2aff.get(role.get('roleName')):
            roles.add(
                HRAffiliation(**{
                    'ou_id': ou.entity_id,
                    'affiliation': role2aff.get(
                        role.get('roleName')).affiliation,
                    'status': role2aff.get(role.get('roleName')),
                    'precedence': None})
            )
        logger.info('parsed %i roles', len(roles))
        # TODO: These used to be sorted, but that did not seem to affect
        #   anything!
        return roles


def parse_assignments(assignment_data, database):
    """Parse data from SAP and return affiliations

    :rtype: set(HRAffiliation)"""

    co = Factory.get('Constants')
    affiliations = set()
    for x in assignment_data:
        status = _sap_assignments_to_affiliation_map().get(
            x.get('jobCategory'))
        if not status:
            logger.warn('parse_affiliations: Unknown job category')
            # Unknown job category
            continue
        ou = _get_ou(database, placecode=x.get('locationId'))
        if not ou:
            logger.warn(
                'OU {} does not exist, '
                'cannot parse affiliation {} for {}'.format(
                    x.get('locationId'), status, x.get('personId')))
            continue
        main = x.get('primaryAssignmentFlag')
        affiliations.add(
            HRAffiliation(**{
                'ou_id': ou.entity_id,
                'affiliation': co.affiliation_ansatt,
                'status': status,
                'precedence': (
                    (50, 50) if main else None)
            })
        )
    logger.info('parsed %i affiliations', len(affiliations))
    return affiliations


def parse_affiliations(assignment_data, role_data, database):
    """Parse data from SAP and return affiliations and account types

    :rtype: tuple(set(HRAffiliation), set(HRAccountType))"""

    assignments = parse_assignments(assignment_data, database)
    account_types = set(
        HRAccountType(ou_id=a.ou_id, affiliation=a.affiliation) for a in
        assignments
    )
    roles = parse_roles(role_data, database)
    return assignments.union(roles), account_types


def parse_titles(person_data, assignment_data):
    """Parse data from SAP and return person titles.

    :rtype: set(HRTitle)"""

    co = Factory.get('Constants')
    logger.info('parsing titles')
    titles = []
    # TODO: find person with title for testing
    if person_data.get('personalTitle'):
        titles.extend(
            [HRTitle(name_variant=co.personal_title,
                     name_language=co.language_en,
                     name=person_data.get('personalTitle', {}).get('en'))] +
            map(lambda lang: HRTitle(
                name_variant=co.personal_title,
                name_language=lang,
                name=person_data.get('personalTitle', {}).get('nb')),
                [co.language_nb, co.language_nn]))
    # Select appropriate work title.
    assignment = None
    for e in assignment_data:
        if not e.get('jobTitle'):
            continue
        if e.get('primaryAssignmentFlag'):
            assignment = e
            break
        if not assignment:
            assignment = e
        elif (float(e.get('agreedFTEPercentage')) >
              float(assignment.get('agreedFTEPercentage'))):
            assignment = e
    if assignment:
        titles.extend(map(lambda (lang_code, lang_str): HRTitle(
            name_variant=co.work_title,
            name_language=lang_code,
            name=assignment.get('jobTitle').get(lang_str)),
                          [(co.language_nb, 'nb'),
                           (co.language_nn, 'nb'),
                           (co.language_en, 'en')]))
    return set(filter(lambda hr_title: hr_title.name, titles))


def parse_external_ids(person_data):
    """Parse data from SAP and return external ids (i.e. passnr).

    :rtype: set(HRExternalID)"""
    co = Factory.get('Constants')
    external_ids = [
        HRExternalID(id_type=co.externalid_sap_ansattnr,
                     external_id=six.text_type(person_data.get('personId')))
    ]
    logger.info('parsing %i external ids', len(external_ids))
    if (person_data.get('passportIssuingCountry') and
            person_data.get('passportNumber')):
        external_ids.append(
            HRExternalID(id_type=co.externalid_pass_number,
                         external_id=co.make_passport_number(
                             person_data.get('passportIssuingCountry'),
                             person_data.get('passportNumber')))
        )
    if person_data.get('norwegianIdentificationNumber'):
        external_ids.append(HRExternalID(
            id_type=co.externalid_fodselsnr,
            external_id=person_data.get('norwegianIdentificationNumber')
        ))
    return set(ext_id for ext_id in external_ids if
               ext_id.id_type and ext_id.external_id)


def parse_contacts(person_data):
    """Parse data from SAP and return contact information.

    :type person_data: dict
    :param person_data: Data from SAP

    :rtype: set(HRContactInfo)"""
    logger.info('parsing contacts')
    co = Factory.get('Constants')
    # TODO: Validate/clean numbers with phonenumbers?
    key_map = OrderedDict([
        ('workPhone', co.contact_phone),
        ('workMobile', co.contact_mobile_phone),
        ('privateMobile', co.contact_private_mobile),
        ('publicMobile', co.contact_private_mobile_visible)
    ])

    numbers_to_add = filter_elements(translate_keys(person_data, key_map))
    numbers_to_add = sorted(((k, v) for k, v in six.iteritems(numbers_to_add)),
                            cmp=lambda (k, v): key_map.values().index(k))
    numbers = set()
    for pref, (key, value) in enumerate(numbers_to_add):
        numbers.add(HRContactInfo(contact_type=key,
                                  contact_pref=pref,
                                  contact_value=value))
    return numbers
