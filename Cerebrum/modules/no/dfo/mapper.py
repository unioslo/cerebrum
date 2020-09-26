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
Mapper for DFØ-SAP.
"""
from __future__ import unicode_literals

import collections
import datetime
import logging

import six

from Cerebrum.modules.hr_import import mapper as _base
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.hr_import.models import (HRPerson,
                                               HRTitle,
                                               HRAffiliation,
                                               HRExternalID,
                                               HRAccountType,
                                               HRContactInfo)
from Cerebrum.modules.hr_import.matcher import match_entity

from .leader_groups import get_leader_group

logger = logging.getLogger(__name__)


def parse_date(value, fmt='%Y-%m-%d', allow_empty=True):
    if value:
        return datetime.datetime.strptime(value, fmt).date()
    elif allow_empty:
        return None
    else:
        raise ValueError('No date: %r' % (value,))


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


def get_additional_assignment(person_data, assignment_id):
    """Extract data about an additional assignment from ``person_data``

    :type person_data: dict
    :param person_data: Data from SAP
    :type assignment_id: int
    """
    for assignment in person_data.get('tilleggsstilling') or []:
        if assignment['stillingId'] == assignment_id:
            return assignment
    return None


def parse_leader_ous(person_data, assignment_data):
    """
    Parse leader OUs from DFØ-SAP data

    :param person_data: Data from DFØ-SAP
                        `/ansatte/{id}`
    :type person_data: dict
    :param assignment_data: Assignment data from DFØ-SAP
    :type assignment_data: dict

    :rtype: set(int)
    :return OU ids where the person is a leader
    """
    if person_data.get('lederflagg'):
        leader_assignment_id = person_data['stillingId']
        # TODO:
        #  DFØ-SAP will probably fix naming of
        #  organisasjonsId/organisasjonId, so that they are equal at some
        #  point.
        return [assignment_data[leader_assignment_id]['organisasjonsId']]
    return []


class EmployeeMapper(_base.AbstractMapper):
    """A simple employee mapper class"""

    # TODO:
    #  Should be config. We also probably don't need to consider this until
    #  after a HRPerson has been constructed. Is it up to the mapper or the
    #  import to decide this?
    start_grace = datetime.timedelta(days=-6)
    end_grace = datetime.timedelta(days=0)

    def __init__(self, db):
        """
        :param db: Database object
        :type db: Cerebrum.Database
        """
        self.db = db
        self.const = Factory.get('Constants')(db)

    @property
    def source_system(self):
        return self.const.system_dfo_sap

    @classmethod
    def parse_affiliations(cls, person_data, assignment_data, stedkode_cache):
        """
        Parse data from SAP and return affiliations and account types

        :rtype: tuple(set(HRAffiliation), set(HRAccountType))
        """
        assignments = cls.parse_assignments(person_data,
                                            assignment_data,
                                            stedkode_cache)
        account_types = set(
            HRAccountType(placecode=a.placecode,
                          affiliation=a.affiliation) for a in
            assignments
        )
        roles = cls.parse_roles(person_data)
        return assignments.union(roles), account_types

    @classmethod
    def parse_assignments(cls, person_data, assignment_data, stedkode_cache):
        """
        Parse data from SAP and return affiliations

        :rtype: set(HRAffiliation)
        """
        affiliations = set()
        category_2_status = {
            '50001597': 'tekadm',
            # TODO:
            #  academic id ?
            'academic': 'vitenskapelig'
        }

        today = datetime.date.today()
        # TODO:
        #  Rewrite this once orgreg is ready.
        for assignment_id, assignment in assignment_data.items():
            status = category_2_status.get(
                assignment.get('stillingskat', {}).get(
                    'stillingskatId')
            )
            if not status:
                logger.warning('parse_affiliations: Unknown job category')
                continue

            is_main_assignment = assignment_id == person_data['stillingId']
            if is_main_assignment:
                precedence = (50, 50)
                start_date = parse_date(person_data['startdato'])
                end_date = parse_date(person_data['sluttdato'])
            else:
                precedence = None
                additional_assignment = get_additional_assignment(
                    person_data,
                    assignment_id
                )
                start_date = parse_date(additional_assignment.get('startdato'),
                                        allow_empty=True)
                end_date = parse_date(additional_assignment.get('sluttdato'),
                                      allow_empty=True)

            if start_date and start_date > today + cls.start_grace:
                logger.debug('Ignoring pending %r (start_date=%r)',
                             assignment,
                             start_date)
                continue

            if end_date and end_date < today + cls.end_grace:
                logger.debug('Ignoring expired %r (end=%r)',
                             assignment,
                             end_date)
                continue

            placecode = stedkode_cache.get(assignment_id)
            if placecode is None:
                logger.warning('Placecode does not exist')
                continue

            affiliations.add(
                HRAffiliation(**{
                    'placecode': placecode,
                    'affiliation': 'ANSATT',
                    'status': status,
                    'precedence': precedence,
                    'start_date': start_date,
                    'end_date': end_date
                })
            )

        logger.info('parsed %i affiliations', len(affiliations))
        return affiliations

    @classmethod
    def parse_contacts(cls, person_data):
        """
        Parse data from SAP and return contact information.

        :type person_data: dict
        :param person_data: Data from DFØ-SAP

        :rtype: set(HRContactInfo)
        """
        logger.info('parsing contacts')
        all_source_phone_types = ['tjenestetelefon',
                                  'privatTelefonnummer',
                                  'telefonnummer',
                                  'mobilnummer',
                                  'mobilPrivat',
                                  'privatTlfUtland']
        key_map = collections.OrderedDict([
            # TODO:
            #  It is tricky to find out the correct mapping here. Do we need
            #  more constants for this? This is pretty much wild guessing..
            ('tjenestetelefon', 'PHONE'),
            ('mobilnummer', 'MOBILE'),
            ('mobilPrivat', 'PRIVATEMOBILE'),
            ('telefonnummer', 'PRIVMOBVISIBLE')])

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
        Parse data from DFØ-SAP and return external ids (i.e. passnr).

        :rtype: set(HRExternalID)
        """
        external_ids = set()
        external_ids.add(
            HRExternalID(id_type='DFO_PID',
                         external_id=six.text_type(person_data['id']))
        )

        # TODO:
        #  Also handle eksternIdent?
        fnr = person_data.get('fnr')
        if fnr:
            external_ids.add(
                HRExternalID(id_type='NO_BIRTHNO',
                             external_id=fnr)
            )

        dfo_2_cerebrum = {
            '02': 'PASSNR',
            # TODO:
            #  Are there other id-types?
        }

        for external_id in person_data.get('annenId') or []:
            id_type = dfo_2_cerebrum.get(external_id['idType'])
            if id_type:
                if id_type == 'PASSNR':
                    id_value = '{}-{}'.format(
                        external_id['idLand'][:2],
                        external_id['idNr']
                    )
                else:
                    id_value = external_id['idNr']
                external_ids.add(
                    HRExternalID(id_type=id_type, external_id=id_value)
                )
        logger.info('parsed %i external ids', len(external_ids))
        return external_ids

    @classmethod
    def parse_roles(cls, role_data):
        """
        Parse data from SAP and return existing roles.

        :rtype: set(HRAffiliation)
        """
        # TODO:
        #  Tests are not dependent on this, fix it later
        # role2aff = collections.OrderedDict(
        #     [('INNKJØPER', 'innkjoper'),
        #      ('EF-FORSKER', 'ekst_forsker'),
        #      ('EMERITUS', 'emeritus'),
        #      ('BILAGSLØNN', 'bilag'),
        #      ('GJ-FORSKER', 'gjesteforsker'),
        #      ('ASSOSIERT', 'assosiert_person'),
        #      ('EF-STIP', 'ekst_stip'),
        #      ('GRP-LÆRER', 'grlaerer'),
        #      ('EKST-KONS', 'ekst_partner'),
        #      ('PCVAKT', 'pcvakt'),
        #      ('EKST-PART', 'ekst_partner'),
        #      ('KOMITEMEDLEM', 'komitemedlem'),
        #      ('STEDOPPLYS', None),
        #      ('POLS-ANSAT', None)])
        # roles = set()
        # for role in role_data:
        #     placecode = role.get('locationCode')
        #     if placecode is None:
        #         logger.warning('Placecode does not exist, '
        #                        'cannot parse affiliation %r for %r',
        #                        role2aff.get(role.get('roleName')),
        #                        role_data.get('personId'))
        #         continue
        #     if role2aff.get(role.get('roleName')):
        #         roles.add(
        #             HRAffiliation(**{
        #                 'placecode': placecode,
        #                 'affiliation': role2aff.get(
        #                     role.get('roleName')).affiliation,
        #                 'status': role2aff.get(role.get('roleName')),
        #                 'precedence': None})
        #         )
        # logger.info('parsed %i roles', len(roles))
        # return roles
        return set()

    @classmethod
    def parse_titles(cls, person_data, assignment_data):
        """
        Parse data from DFØ-SAP and return person titles.

        :rtype: set(HRTitle)
        """
        logger.info('parsing titles')
        titles = set()

        main_assignment = assignment_data[person_data['stillingId']]
        titles.add(
            HRTitle(name_variant='WORKTITLE',
                    name_language='no',
                    name=main_assignment['stillingstittel'])
        )
        return titles

    def find_entity(self, hr_object):
        """Find matching Cerebrum entity for the given HRPerson."""
        return match_entity(hr_object.external_ids,
                            self.source_system,
                            self.db)

    def parse_leader_groups(self, person_data, assignment_data,
                            stedkode_cache):
        """
        Parse leader groups from SAP assignment data

        :param person_data: Data from DFØ-SAP
                            `/ansatte/{id}`
        :type person_data: dict
        :param assignment_data: Assignment data from DFØ-SAP
        :type assignment_data: dict

        :rtype: set(int)
        :return: leader group ids where the person should be a member
        """
        leader_dfo_ou_ids = parse_leader_ous(person_data, assignment_data)

        leader_group_ids = set()
        for dfo_ou_id in leader_dfo_ou_ids:
            stedkode = stedkode_cache.get(dfo_ou_id)
            if stedkode:
                leader_group_ids.add(get_leader_group(self.db,
                                                      stedkode).entity_id)
            else:
                logger.warning('No matching stedkode for OU: %r', dfo_ou_id)

        logger.info('parsed %i leader groups', len(leader_group_ids))
        return leader_group_ids

    def cache_stedkoder(self, assignment_data):
        # TODO:
        #  Remove this once orgreg is ready
        cache = {}
        ou = Factory.get('OU')(self.db)
        co = Factory.get('Constants')(self.db)
        for dfo_ou_id in (a['organisasjonsId'] for a in assignment_data):
            ou.clear()
            try:
                ou.find_by_external_id(co.externalid_dfo_ou_id, dfo_ou_id)
            except Errors.NotFoundError:
                logger.warning('OU not found in Cerebrum %r', dfo_ou_id)
            else:
                cache[dfo_ou_id] = ou.get_stedkode()
        return cache

    def translate(self, reference, obj):
        """
        Populate a HRPerson object with data fetched from SAP

        :type reference: str
        :type obj: RemoteObject
        :rtype: HRPerson
        """
        person_data = obj
        assignment_data = obj['assignments']

        hr_person = HRPerson(
            hr_id=person_data.get('id'),
            first_name=person_data.get('fornavn'),
            last_name=person_data.get('etternavn'),
            birth_date=person_data.get('fdato'),
            gender=person_data.get('kjonn'),
            # TODO:
            #  There does not seem to be any way to determine this in DFO-SAP
            reserved=False
        )

        # TODO:
        #  This should be fetched from orgreg by ``datasource.py`` sometime in
        #  the future.
        stedkode_cache = self.cache_stedkoder(assignment_data)

        hr_person.leader_groups = self.parse_leader_groups(person_data,
                                                           assignment_data,
                                                           stedkode_cache)
        hr_person.external_ids = self.parse_external_ids(person_data)
        hr_person.contact_infos = self.parse_contacts(person_data)
        hr_person.titles = self.parse_titles(person_data, assignment_data)
        hr_person.affiliations, hr_person.account_types = (
            self.parse_affiliations(person_data,
                                    assignment_data,
                                    stedkode_cache)
        )
        return hr_person

    def is_active(self, hr_object, is_active=None):
        if is_active is not None:
            return is_active
        return bool(hr_object.affiliations)
