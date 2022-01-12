# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Parsing, mapping and filtering of Greg values

This module contains utils for extracting Cerebrum data from Greg objects.

Import/update utils should use a py:class:`.GregMapper` to extract relevant
Cerebrum data from a (sanitized) Greg object.

Future changes
--------------
The Greg mappers are not configurable.  If diverging business logic is required
in the future, we may opt to either:

- Subclass GregMapper
- Add a mapper config, which we feed to the GregMapper on init.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging


logger = logging.getLogger(__name__)


class GregOrgunitIds(object):
    """
    Extract external ids from greg org unit data.

    >>> orgunit = {
    ...     'id': '1',
    ...     'identifiers': [{
    ...        'source': 'orgreg',
    ...        'name': 'orgreg_id',
    ...        'value': '1234',
    ...     }]}
    >>> get_org_ids = GregOrgunitIds()
    >>> list(get_org_ids(orgunit))
    [('ORGREG_OU_ID', '1234')]
    """

    # (identifiers.source, identifiers.name) -> cerebrum external_id
    type_map = {
        ('orgreg', 'orgreg_id'): 'ORGREG_OU_ID',
    }

    # id -> cerebrum external_id
    greg_id_type = 'GREG_OU_ID'

    def __call__(self, greg_data):
        """
        :param dict greg_data:
            Sanitized org unit data (e.g. from `datasource.parse_orgunit`)

        :returns generator:
            Valid Cerebrum (id_type, id_value) pairs
        """
        greg_id = greg_data['id']

        if self.greg_id_type:
            yield self.greg_id_type, greg_id

        for id_obj in greg_data.get('identifiers', ()):
            (source, name, value) = (id_obj['source'], id_obj['name'],
                                     id_obj['value'])
            if (source, name) in self.type_map:
                yield self.type_map[source, name], value
            else:
                logger.debug('ignoring unknown org unit id (%s, %s) '
                             'for greg_id=%s', source, name, greg_id)


def get_names(greg_data):
    """
    Get names for a given person.

    :param dict greg_data:
        Sanitized greg person data (e.g. from `datasource.parse_person`)

    :returns generator:
        Valid Cerebrum (name_type, name_value) pairs
    """
    fn = greg_data['first_name']
    ln = greg_data['last_name']
    if fn:
        yield ('FIRST', fn)
    if ln:
        yield ('LAST', ln)


class GregPersonIds(object):
    """ Extract external ids from greg person data.

    >>> person = {
    ...     'id': '1',
    ...     'identities': [{
    ...         'type': 'passport_number',
    ...         'verified': 'automatic',
    ...         'value': 'NO-123',
    ...     }]}
    >>> get_ids = GregPersonIds()
    >>> list(get_ids(person))
    [('GREG_PID', '1'), ('PASSNR', 'NO-123')]
    """

    # identities.type value -> cerebrum external_id
    type_map = {
        'norwegian_national_id_number': 'NO_BIRTHNO',
        'passport_number': 'PASSNR',
    }

    # known identities.type that shouldn't be considered
    ignore_types = set((
        'feide_id',
        'feide_email',
        'private_email',
        'private_mobile',
    ))

    # values of identities.verified to accept
    verified_values = set((
        'automatic',
        'manual',
    ))

    # id -> cerebrum external_id
    greg_id_type = 'GREG_PID'

    def __call__(self, greg_data):
        """
        :param dict greg_data:
            Sanitized greg person data (e.g. from `datasource.parse_person`)

        :returns generator:
            Valid Cerebrum (id_type, id_value) pairs
        """
        greg_id = greg_data['id']

        if self.greg_id_type:
            yield self.greg_id_type, greg_id

        for id_obj in greg_data.get('identities', ()):
            if id_obj['type'] in self.ignore_types:
                continue
            if id_obj['type'] not in self.type_map:
                logger.debug('ignoring unknown id_type=%r for greg_id=%s',
                             id_obj['type'], greg_id)
                continue
            crb_type = self.type_map[id_obj['type']]
            if id_obj['verified'] not in self.verified_values:
                logger.debug('ignoring unverified id_type=%r for greg_id=%s',
                             id_obj['type'], greg_id)
                continue

            value = id_obj['value']
            # TODO/TBD: Validate values (e.g. valid fnr), or should this be
            # done by the import?
            yield crb_type, value


class GregContactInfo(object):
    """ Extract contanct info from greg person data.

    >>> person = {
    ...     'id': '1',
    ...     'identities': [{
    ...         'type': 'private_mobile',
    ...         'verified': 'automatic',
    ...         'value': '20123456',
    ...     }]}
    >>> get_contacts = GregContactInfo()
    >>> list(get_contacts(person))
    [('PRIVATEMOBILE', '20123456')]
    """

    # identities.type value -> cerebrum contact_info_type
    type_map = {
        'private_mobile': 'PRIVATEMOBILE',
    }

    # known identities.type that shouldn't be considered
    ignore_types = set((
        'feide_id',
        'feide_email',
        'norwegian_national_id_number',
        'passport_number',
        'private_email',
    ))

    # values of identities.verified to accept
    verified_values = set((
        'automatic',
        'manual',
    ))

    def __call__(self, greg_data):
        """
        :param dict greg_data:
            Sanitized greg person data (e.g. from `datasource.parse_person`)

        :returns generator:
            Valid Cerebrum (contact_info_type, contact_info_value) pairs
        """
        greg_id = int(greg_data['id'])
        for id_obj in greg_data.get('identities', ()):
            if id_obj['type'] in self.ignore_types:
                continue
            if id_obj['type'] not in self.type_map:
                logger.debug('ignoring unknown id_type=%r for greg_id=%s',
                             id_obj['type'], greg_id)
                continue
            crb_type = self.type_map[id_obj['type']]
            if id_obj['verified'] not in self.verified_values:
                logger.debug('ignoring unverified id_type=%r for greg_id=%s',
                             id_obj['type'], greg_id)
                continue

            value = id_obj['value']
            # TODO/TBD: Validate values (e.g. valid email, phone), or should
            # this be done by the import?
            yield crb_type, value


class GregConsents(object):
    """ Extract consent data from greg person data. """

    def __call__(self, greg_data):
        """
        :param dict greg_data:
            Sanitized greg person data (e.g. from `datasource.parse_person`)

        :returns generator:
            TODO/TBD: Return value depends on how consents are actually
            represented in Greg, and how they will be represented in Cerebrum.
        """
        greg_id = int(greg_data['id'])
        for c_obj in greg_data.get('consents', ()):
            consent_type = c_obj['consent_type']
            given_at = c_obj['consent_given_at']
            # TODO/TBD: what constitutes a consent?  Is it enough that it
            # exists in the consents tuple, or does consent_given_at need to be
            # set as well?
            if False:
                # TODO: never reached 'yield' to make this a generator
                yield (greg_id, consent_type, given_at)


class GregRoles(object):
    """ Extract affiliations from greg person roles. """

    type_map = {
        'emeritus': 'TILKNYTTET/emeritus',
        'external-consultant': 'TILKNYTTET/ekst_partner',
        'external-partner': 'TILKNYTTET/ekst_partner',
        'guest-researcher': 'TILKNYTTET/gjesteforsker',
    }

    def __call__(self, greg_data, _today=None):
        """
        :param dict greg_data:
            Sanitized greg person data (e.g. from `datasource.parse_person`)

        :returns generator:
            yields (affiliation, orgunit) tuples.

            - Affiliation is an AFFILIATION/status string
            - orgunit is the role orgunit value.
        """
        greg_id = int(greg_data['id'])

        # TODO: We may want to allow expired roles here, and filter them out in
        # the is_active check, and ignore them when updating person affs.
        today = _today or datetime.date.today()

        for role_obj in greg_data.get('roles', ()):
            if role_obj['type'] not in self.type_map:
                logger.debug(
                    'ignoring unknown role type=%r, id=%r for greg_id=%s',
                    role_obj['type'], role_obj['id'], greg_id)
                continue
            if role_obj['start_date'] > today:
                logger.debug(
                    'ignoring future role type=%r, id=%r for greg_id=%s',
                    role_obj['type'], role_obj['id'], greg_id)
                continue
            if role_obj['end_date'] < today:
                logger.debug(
                    'ignoring expired role type=%r id=%r for greg_id=%s',
                    role_obj['type'], role_obj['id'], greg_id)
                continue

            crb_type = self.type_map[role_obj['type']]
            orgunit = role_obj['orgunit']
            yield crb_type, orgunit


class GregMapper(object):
    """ Mapper object for greg person objects. """

    get_contact_info = GregContactInfo()
    get_person_ids = GregPersonIds()
    get_affiliations = GregRoles()
    get_consents = GregConsents()
    get_orgunit_ids = GregOrgunitIds()

    @classmethod
    def get_names(cls, greg_data):
        return tuple(get_names(greg_data))

    def is_active(self, greg_data, _today=None):
        """ Check if a guest is active from the provided greg data. """
        greg_id = int(greg_data['id'])
        today = _today or datetime.date.today()

        if len(greg_data) == 1:
            # We only have {'id': ...} - which means that the person does
            # not exist in greg
            logger.info('no greg-data for greg_id=%s', greg_id)
            return False

        if (not greg_data['registration_completed_date']
                or greg_data['registration_completed_date'] > today):
            logger.info('incomplete registration for greg_id=%s', greg_id)
            return False

        if not list(self.get_affiliations(greg_data, _today=today)):
            logger.info('no active roles for greg_id=%s', greg_id)
            return False

        # TODO: should we check for certain required consents?
        return True
