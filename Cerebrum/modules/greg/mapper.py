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
    fn = greg_data.get('first_name', '')
    ln = greg_data.get('last_name', '')
    if fn:
        yield ('FIRST', fn)
    if ln:
        yield ('LAST', ln)


class _GregIdentityMapper(object):
    """
    Extract identity values from greg person data.

    Both external ids and contact info is extracted from this dataset.  This is
    the common functionality shared by both.
    """

    # Map of source + type (or just type) to a cerebrum type.  If a `(source,
    # type)` exists in type_map, it will be chosen over just `type`.
    type_map = {
        # # external id examples
        #
        # ('foo', 'migration_id'): 'FOO_ID',
        # 'norwegian_national_id_number': 'NO_BIRTHNO',
        # 'passport_number': 'PASSNR',

        # # contact info examples
        # ('feide', 'email'): 'EMAIL',
        # 'private_mobile': 'PRIVATEMOBILE',
    }

    # Validate and/or normalize values from Greg by type.  To invalidate a
    # value, the callback should simply raise an exception (or return an empty
    # value).
    normalize_map = {
        # # contact info examples
        # ('feide', 'email'): (lambda v: str(v)),
        # 'private_mobile': (lambda v: str(v)),
    }

    # Values of identities.verified to accept.  If empty, identities.verified
    # won't be checked.
    #
    # TODO: We may want to set this by *type* - i.e. maybe we want to accept
    # 'passport_number' regardless of its verified value, and we *only* want to
    # accept 'norwegian_national_id_number' if `verified == 'automatic'`
    verified_values = set()

    # Include the greg object id value as this cerebrum type.
    greg_id_type = None

    def __call__(self, greg_data):
        """
        :param dict greg_data:
            Sanitized greg person data (e.g. from `datasource.parse_person`)

        :returns generator:
            Valid Cerebrum (crb_type, crb_value) pairs
        """
        greg_id = greg_data['id']

        if self.greg_id_type:
            yield self.greg_id_type, greg_id

        for id_obj in greg_data.get('identities', ()):
            id_type = id_obj['type']
            id_source = id_obj['source']
            id_verified = id_obj['verified']
            raw_value = id_obj['value']

            # map and filter id source/type to external id type
            if id_source and (id_source, id_type) in self.type_map:
                crb_type = self.type_map[(id_source, id_type)]
            elif id_type in self.type_map:
                crb_type = self.type_map[id_type]
            else:
                # unknown id type
                continue

            # map and filter verified values
            if (self.verified_values
                    and id_verified not in self.verified_values):
                logger.debug(
                    'ignoring unverified source=%r type=%r for greg_id=%r',
                    id_source, id_type, greg_id)
                continue

            # normalize and filter value
            try:
                if (id_source, id_type) in self.normalize_map:
                    value = self.normalize_map[id_source, id_type](raw_value)
                elif id_type in self.normalize_map:
                    value = self.normalize_map[id_type](raw_value)
                else:
                    value = raw_value
            except Exception as e:
                logger.warning(
                    "invalid source=%r type=%r for greg_id=%r: %s",
                    id_source, id_type, greg_id, str(e))
                continue

            if not value:
                logger.warning(
                    "invalid source=%r type=%r for greg_id=%r: empty value",
                    id_source, id_type, greg_id)
                continue

            # TODO/TBD:
            #   Greg *can* have multiple values of a given type, from different
            #   sources.  How should this be handled?  Should we look for
            #   duplicates, and alternatively raise an error if there are
            #   multiple different values of a given type?
            #
            #   Currently, we'll just crash and burn during import if we
            #   encounter duplicate crb_type with differing values
            yield crb_type, value


class GregPersonIds(_GregIdentityMapper):
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

    type_map = {
        'norwegian_national_id_number': 'NO_BIRTHNO',
        'passport_number': 'PASSNR',
    }

    # TODO/TBD:
    #   Values should already be verified by Greg, so we should be able
    #   to trust them.  Still, we might want to validate/normalize
    #   certain values here as well.
    normalize_map = {}

    # values of identities.verified to accept
    verified_values = set((
        'automatic',
        'manual',
    ))

    greg_id_type = 'GREG_PID'


class GregContactInfo(_GregIdentityMapper):
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

    type_map = {
        'private_mobile': 'PRIVATEMOBILE',
    }

    # TODO/TBD:
    #   Values should already be verified by Greg, so we should be able
    #   to trust them.  Still, we might want to validate/normalize
    #   certain values here as well.
    normalize_map = {}


class GregConsents(object):
    """
    Extract consent data from greg person data.
    """

    # TODO: Is this a generic consent? Or should this be moved to
    # `Cerebrum.modules.no.uio.greg_import`?
    type_map = {
        'publish': 'greg-publish',
    }

    # Consent value (choice) to bool (is-consent)
    #
    # TODO: We may want to map these value by type?
    #       E.g.: {'publish': {'yes': True, 'no': False}}
    value_map = {
        'yes': True,
        'no': False,
    }

    def __call__(self, greg_data):
        """
        :param dict greg_data:
            Sanitized greg person data (e.g. from `datasource.parse_person`)

        :returns set:
            Return a set of consents given.
        """
        greg_id = int(greg_data['id'])
        seen = set()
        consents = set()

        for c_obj in greg_data.get('consents', ()):
            greg_type = c_obj['type']
            greg_value = c_obj['value']

            if greg_type not in self.type_map:
                continue
            crb_type = self.type_map[greg_type]

            if greg_type in seen:
                # if we see a consent type twice, we discard *all* consents of
                # that type
                logger.warning('duplicate consent %s (%s) for greg_id=%s',
                               crb_type, greg_type, greg_id)
                consents.discard(greg_type)
            seen.add(greg_type)

            if greg_value in self.value_map:
                is_consent = self.value_map[greg_value]
                logger.debug('found consent %s=%r (%s=%r) for greg_id=%s',
                             crb_type, is_consent, greg_type, greg_value,
                             greg_id)
            else:
                # invalid consent value (choice), discard consent
                is_consent = False
                logger.warning('invalid consent %s value (%s=%r) for'
                               ' greg_id=%s',
                               crb_type, greg_type, greg_value, greg_id)
            if is_consent:
                consents.add(greg_type)
            else:
                consents.discard(greg_type)

        return tuple(self.type_map[c] for c in sorted(consents))


class GregRoles(object):
    """ Extract affiliations from greg person roles. """

    # Greg role name -> AFFILIATION/status
    type_map = {
        'emeritus': 'TILKNYTTET/emeritus',
        'external-consultant': 'TILKNYTTET/ekst_partner',
        'external-partner': 'TILKNYTTET/ekst_partner',
        'guest-researcher': 'TILKNYTTET/gjesteforsker',
    }

    get_orgunit_ids = GregOrgunitIds()

    def __call__(self, greg_data, filter_active_at=None):
        """
        :param dict greg_data:
            Sanitized greg person data (e.g. from `datasource.parse_person`)

        :param datetime.date filter_active_at:
            Only include roles that are active at the given date.

            If not given, the default behaviour is to include all past and
            future roles.

        :returns generator:
            yields (affiliation, org-ids, start-date, end-date) tuples.

            - affiliation is an AFFILIATION/status string
            - org-ids is a sequence of orgunit (id-type, id-value) pairs
            - start-/end-date are datetime.date objects
        """
        greg_id = int(greg_data['id'])

        for role_obj in greg_data.get('roles', ()):
            if role_obj['type'] not in self.type_map:
                logger.debug(
                    'ignoring unknown role type=%r, id=%r for greg_id=%s',
                    role_obj['type'], role_obj['id'], greg_id)
                continue
            if filter_active_at and filter_active_at < role_obj['start_date']:
                logger.debug(
                    'ignoring future role type=%r, id=%r for greg_id=%s',
                    role_obj['type'], role_obj['id'], greg_id)
                continue
            if filter_active_at and filter_active_at > role_obj['end_date']:
                logger.debug(
                    'ignoring expired role type=%r, id=%r for greg_id=%s',
                    role_obj['type'], role_obj['id'], greg_id)
                continue

            yield (
                self.type_map[role_obj['type']],
                tuple(self.get_orgunit_ids(role_obj['orgunit'])),
                role_obj['start_date'],
                role_obj['end_date'],
            )


class GregMapper(object):
    """ Mapper object for greg person objects. """

    get_contact_info = GregContactInfo()
    get_person_ids = GregPersonIds()
    get_affiliations = GregRoles()
    get_consents = GregConsents()

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

        if not greg_data['date_of_birth']:
            # Some mandatory fields may be missing until the guest has
            # completed the regsitration.
            logger.warning('missing mandatory date_of_birth for greg_id=%s',
                           greg_id)
            return False

        if not list(self.get_affiliations(greg_data, filter_active_at=today)):
            logger.info('no active roles for greg_id=%s', greg_id)
            return False

        # TODO: should we check for certain required consents?
        return True
