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
"""
Mapper for SAPUiO.
"""
from __future__ import unicode_literals

import collections
import decimal
import logging

import six

from Cerebrum.modules.hr_import import mapper as _base
from Cerebrum.modules.no.uio.hr_import.models import HRPerson
from Cerebrum.modules.hr_import.models import (HRTitle,
                                               HRAffiliation,
                                               HRExternalID,
                                               HRContactInfo)
from Cerebrum.modules.hr_import.matcher import match_entity
from Cerebrum.modules.no.uio.hr_import.leader_groups import get_leader_group
from Cerebrum.modules.no.uio.sap.utils import parse_date

logger = logging.getLogger(__name__)


def translate_keys(d, mapping):
    """
    Filter and translate keys of a dict-like mapping.

    :param d: A dict-like object to translate
    :param mapping: A dict-like key translation table

    :rtype: dict
    :returns: A modified copy of ``d``.

    >>> translate_keys({'a': 1, 'b': 2, 'c': 3}, {'a': 'A', 'b': 'B'})
    {'A': 1, 'B': 2}
    """
    return {mapping[k]: v for k, v in d.items() if k in mapping}


def filter_elements(d):
    """
    Filter out empty keys and valies from a dict.

    :param d: A dict-like object to filter

    :rtype: dict
    :returns: A modified copy of ``d``.

    >>> filter_elements({'a': None, 'b': 0, 'c': False, '': 3, 'x': 'y'})
    {'x': 'y'}
    """
    return {k: v for k, v in d.items() if k and v}


class MapperConfig(_base.MapperConfig):
    pass


class EmployeeMapper(_base.AbstractMapper):
    """A simple employee mapper class"""

    @property
    def source_system(self):
        return self.const.system_sap

    @classmethod
    def parse_affiliations(cls, assignment_data, role_data):
        """
        Parse data from SAP and return affiliations and account types

        :rtype: set(HRAffiliation)
        """
        assignments = cls.parse_assignments(assignment_data)
        roles = cls.parse_roles(role_data)
        return assignments.union(roles)

    @classmethod
    def parse_assignments(cls, assignment_data):
        """
        Parse data from SAP and return affiliations

        :rtype: set(HRAffiliation)
        """
        affiliations = set()
        sap_assignments_to_affiliation_map = {'administrative': 'tekadm',
                                              'academic': 'vitenskapelig'}

        for x in assignment_data:
            start = parse_date(x.get('effectiveStartDate'), allow_empty=True)
            end = parse_date(x.get('effectiveEndDate'), allow_empty=True)

            status = sap_assignments_to_affiliation_map.get(
                x.get('jobCategory'))
            if not status:
                logger.warning('parse_affiliations: Unknown job category')
                # Unknown job category
                continue
            placecode = x.get('locationCode')
            if placecode is None:
                logger.warning('Placecode does not exist')
                continue
            main = x.get('primaryAssignmentFlag')
            affiliations.add(
                HRAffiliation(**{
                    'ou_id': placecode,
                    'affiliation': 'ANSATT',
                    'status': status,
                    'precedence': ((50, 50) if main else None),
                    'start_date': start,
                    'end_date': end
                })
            )
        logger.info('parsed %i affiliations', len(affiliations))
        return affiliations

    @classmethod
    def parse_contacts(cls, person_data):
        """
        Parse data from SAP and return contact information.

        :type person_data: dict
        :param person_data: Data from SAP

        :rtype: set(HRContactInfo)
        """
        logger.info('parsing contacts')
        # TODO: Validate/clean numbers with phonenumbers?
        key_map = collections.OrderedDict([
            ('workPhone', 'PHONE'),
            ('workMobile', 'MOBILE'),
            ('privateMobile', 'PRIVATEMOBILE'),
            ('publicMobile', 'PRIVMOBVISIBLE')])

        numbers_to_add = filter_elements(translate_keys(person_data, key_map))
        numbers_to_add = sorted(
            [(k, v) for k, v in numbers_to_add.items()],
            key=lambda (k, v): key_map.values().index(k))
        numbers = set()
        for pref, (key, value) in enumerate(numbers_to_add):
            numbers.add(HRContactInfo(contact_type=key,
                                      contact_pref=pref,
                                      contact_value=value))
        return numbers

    @classmethod
    def parse_external_ids(cls, person_data):
        """
        Parse data from SAP and return external ids (i.e. passnr).

        :rtype: set(HRExternalID)
        """
        external_ids = [HRExternalID(
            id_type='NO_SAPNO',
            external_id=six.text_type(person_data.get('personId')))]

        logger.info('parsing %i external ids', len(external_ids))
        if (
                person_data.get('passportIssuingCountry') and
                person_data.get('passportNumber')
        ):
            external_ids.append(
                HRExternalID(id_type='PASSNR',
                             external_id='{}-{}'.format(
                                 person_data.get('passportIssuingCountry'),
                                 person_data.get('passportNumber'))))
        if person_data.get('norwegianIdentificationNumber'):
            external_ids.append(HRExternalID(
                id_type='NO_BIRTHNO',
                external_id=person_data.get('norwegianIdentificationNumber')))
        return set(ext_id for ext_id in external_ids if
                   ext_id.id_type and ext_id.external_id)

    @classmethod
    def parse_roles(cls, role_data):
        """
        Parse data from SAP and return existing roles.

        :rtype: set(HRAffiliation)
        """
        role2aff = collections.OrderedDict(
            [('INNKJØPER', 'innkjoper'),
             ('EF-FORSKER', 'ekst_forsker'),
             ('EMERITUS', 'emeritus'),
             ('BILAGSLØNN', 'bilag'),
             ('GJ-FORSKER', 'gjesteforsker'),
             ('ASSOSIERT', 'assosiert_person'),
             ('EF-STIP', 'ekst_stip'),
             ('GRP-LÆRER', 'grlaerer'),
             ('EKST-KONS', 'ekst_partner'),
             ('PCVAKT', 'pcvakt'),
             ('EKST-PART', 'ekst_partner'),
             ('KOMITEMEDLEM', 'komitemedlem'),
             ('STEDOPPLYS', None),
             ('POLS-ANSAT', None)])
        roles = set()
        for role in role_data:
            placecode = role.get('locationCode')
            if placecode is None:
                logger.warning('Placecode does not exist, '
                               'cannot parse affiliation %r for %r',
                               role2aff.get(role.get('roleName')),
                               role_data.get('personId'))
                continue
            if role2aff.get(role.get('roleName')):
                roles.add(
                    HRAffiliation(**{
                        'placecode': placecode,
                        'affiliation': role2aff.get(
                            role.get('roleName')).affiliation,
                        'status': role2aff.get(role.get('roleName')),
                        'precedence': None})
                )
        logger.info('parsed %i roles', len(roles))
        return roles

    @classmethod
    def parse_titles(cls, person_data, assignment_data):
        """
        Parse data from SAP and return person titles.

        :rtype: set(HRTitle)
        """
        logger.info('parsing titles')
        titles = []
        if person_data.get('personalTitle'):
            titles.extend(
                [HRTitle(
                    name_variant='PERSONALTITLE',
                    name_language='en',
                    name=person_data.get('personalTitle', {}).get('en'))] +
                map(lambda lang: HRTitle(
                    name_variant='PERSONALTITLE',
                    name_language=lang,
                    name=person_data.get('personalTitle', {}).get('nb')),
                    ['nb', 'nn']))
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
            elif (
                    decimal.Decimal(e.get('agreedFTEPercentage')) >
                    decimal.Decimal(assignment.get('agreedFTEPercentage'))
            ):
                assignment = e
        if assignment:
            titles.extend(map(lambda (lang_code, lang_str): HRTitle(
                name_variant='WORKTITLE',
                name_language=lang_code,
                name=assignment.get('jobTitle').get(lang_str)),
                              [('nb', 'nb'),
                               ('nn', 'nb'),
                               ('en', 'en')]))
        return set(filter(lambda hr_title: hr_title.name, titles))

    def find_entity(self, hr_object):
        """Find matching Cerebrum entity for the given HRPerson."""
        return match_entity(hr_object.external_ids,
                            self.source_system,
                            self.db)

    def parse_leader_groups(self, assignment_data):
        """
        Parse leader groups from SAP assignment data

        :param assignment_data: Data from SAP
                                `/employees({personId})/assignments`
        :type assignment_data: list

        :rtype: set(int)
        :return: leader group ids where the person should be a member
        """
        # This method is not Cerebrum independent ...
        leader_group_ids = set()
        for x in assignment_data:
            if x.get('managerFlag'):
                leader_group_ids.add(
                    get_leader_group(self.db, x.get('locationCode')).entity_id)
        logger.info('parsed %i leader groups', len(leader_group_ids))
        return leader_group_ids

    def translate(self, reference, obj):
        """
        Populate a HRPerson object with data fetched from SAP

        :rtype: HRPerson
        """
        person_data = obj
        assignment_data = obj['assignments']
        role_data = obj['roles']

        hr_person = HRPerson(
            hr_id=six.text_type(person_data.get('personId')),
            first_name=person_data.get('firstName'),
            last_name=person_data.get('lastName'),
            birth_date=parse_date(person_data.get('dateOfBirth'),
                                  allow_empty=True),
            gender={'Kvinne': 'F', 'Mann': 'M'}.get(
                person_data.get('gender')
            ),
            reserved=not person_data.get('allowedPublicDirectoryFlag'))
        hr_person.leader_groups = self.parse_leader_groups(assignment_data)
        hr_person.external_ids = self.parse_external_ids(person_data)
        hr_person.contact_infos = self.parse_contacts(person_data)
        hr_person.titles = self.parse_titles(person_data, assignment_data)
        hr_person.affiliations = self.parse_affiliations(assignment_data,
                                                         role_data)
        return hr_person

    def is_active(self, hr_object):
        return hr_object.has_active_affiliations(start_grace=self.start_grace,
                                                 end_grace=self.end_grace)
