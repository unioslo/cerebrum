# -*- coding: utf-8 -*-
#
# Copyright 2021-2026 University of Oslo, Norway
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
OTP LDAP export utils.

This module implements utils for fetching, caching and formatting otp payloads
for LDAP.

It implements two LDAP export mixins:

:class:`.NorEduOtpMixin`
    Mixin for the Feide export.

    If enabled (present in ``cereconf.CLASS_ORGLDIF``), this mixin will fetch
    and export otp payloads of type *feide-ga* as a ``norEduPersonAuthnMethod``
    attribute.

:class:`.RadiusOtpMixin`
    Mixin for the generic Posix export.

    If enabled (present in ``cereconf.CLASS_POSIXLDIF``), this mixin will fetch
    and export otp payloads of type 'radius-otp'.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging

import six
from six.moves.urllib.parse import quote

from Cerebrum.Utils import make_timer
from Cerebrum.export.base import EntityCache, EntityFetcher, MISSING
from Cerebrum.modules.LDIFutils import attr_unique, normalize_string
from Cerebrum.modules.PosixLDIF import PosixLDIFRadius
from Cerebrum.modules.no.OrgLDIF import NorEduOrgLdifMixin

from .otp_db import sql_search


logger = logging.getLogger(__name__)


class _OtpFetcher(EntityFetcher):
    """
    Fetch otp payload for persons.
    """

    def __init__(self, db, otp_types=None):
        """
        :type db: Cerebrum.database.Database
        :type otp_types: str or list[str]
        :param otp_types:
            One or more otp types to cache.

            If omitted, all otp types will be cached.
        """
        self.otp_types = None if otp_types is None else tuple(otp_types)
        self._db = db

    def _get_results(self, **extra):
        for row in sql_search(self._db, otp_type=self.otp_types, **extra):
            yield row['person_id'], row['otp_type'], row['otp_payload']

    def get_one(self, entity_id):
        """ Fetch personal otp data for a given person. """
        person_otp = {}
        for _, otp_type, otp_payload in self._get_results(
                person_id=int(entity_id)):
            person_otp[otp_type] = otp_payload
        return person_otp or MISSING

    def get_all(self):
        """ Fetch personal otp data for all persons. """
        results = {}
        for entity_id, otp_type, otp_payload in self._get_results():
            person_otp = results.setdefault(int(entity_id), {})
            person_otp[otp_type] = otp_payload
        return results


class OtpCache(EntityCache):
    """
    A cache of personal otp types/values.

    Example usage:
    ::

        # Configure and initialize cache for otp type *feide-ga*.
        otp_cache = OtpCache(db, 'feide-ga')

        # Optionally, cache all relevant data up front
        otp_cache.update_all()

        # Get payload for person_id=3
        secret = otp_cache.get_payload(3)
    """

    def __init__(self, db, otp_type):
        """
        :type db: Cerebrum.database.Database
        :param str otp_type: A named otp secret to get
        """
        self.otp_type = otp_type
        super(OtpCache, self).__init__(_OtpFetcher(db, (otp_type,)))

    def get_payload(self, person_id):
        """
        Get otp payload for a given person.

        :param person_id: The person to get an OTP payload for.

        :rtype: str
        :return: The OTP payload for this person.

        :raises LookupError: If no OTP payload exists for this person.
        """
        otp_payloads = self.get(person_id, {})
        if self.otp_type in otp_payloads:
            return otp_payloads[self.otp_type]
        raise LookupError('No otp value for person_id=%r' %
                          (person_id, ))


def _get_cache(db, otp_type, ldap_attr=''):
    logger.info('Getting otp data with otp_type=%s (%s)', otp_type, ldap_attr)
    cache = OtpCache(db, otp_type)
    timer = make_timer(logger, 'Fetching otp data ...')
    cache.update_all()
    timer('... done fetching otp data.')
    return cache


class NorEduOtpMixin(NorEduOrgLdifMixin):
    """
    Mixin to provide encrypted OTP secrets in OrgLDIF/NorEduOrgLdifMixin.

    This mixin adds or extends the *norEduPersonAuthnMethod* attribute with
    data from otp_type='feide-ga'.
    """

    feide_otp_type = 'feide-ga'
    """ OTP type and payload to fetch and use. """

    feide_authn_method_ga_fmt = (
        'urn:mace:feide.no:auth:method:ga {value} label={label}')
    """
    Format for the norEduPersonAuthnMethod ldap attribute.

    The secret (value) and label is percent-encoded according to RFC-3986.
    """

    feide_authn_method_ga_label = 'OTP'
    """ Label for the norEduPersonAuthnMethod format. """

    @property
    def feide_otp_cache(self):
        """ A cache of otp payloads for all persons. """
        if hasattr(self, '_feide_otp_cache'):
            cache = self._feide_otp_cache
        else:
            cache = self._feide_otp_cache = _get_cache(
                self.db, self.feide_otp_type, 'norEduPersonAuthnMethod')
        return cache

    def _get_otp_authn_methods(self, person_id):
        try:
            secret = self.feide_otp_cache.get_payload(person_id)
        except LookupError:
            return []

        value = self.feide_authn_method_ga_fmt.format(
            value=quote(secret),
            label=quote(self.feide_authn_method_ga_label),
        )
        return attr_unique([value], normalize=normalize_string)

    def update_person_entry(self, entry, row, person_id):
        """ Add norEduPersonAuthnMethod to a valid Feide object. """
        super(NorEduOtpMixin, self).update_person_entry(entry, row, person_id)

        # norEdu 1.6 introduces two-factor auth:
        if self.FEIDE_schema_version < '1.6':
            return

        # If parent didn't add norEduPerson, we can't add norEduPerson
        # attributes
        if 'norEduPerson' not in entry['objectClass']:
            return

        # there *shouldn't* be any value collisions here, as encrypted TOTP
        # values use a distinct urn - if we ever make a new mixin that *also*
        # produce norEduPersonAuthnMethod values with the same urn this should
        # be re-done
        ga_values = self._get_otp_authn_methods(person_id)
        if ga_values and entry.get('norEduPersonAuthnMethod'):
            entry['norEduPersonAuthnMethod'].extend(ga_values)
        elif ga_values:
            entry['norEduPersonAuthnMethod'] = ga_values


class RadiusOtpMixin(PosixLDIFRadius):
    """
    Mixin to provide encrypted OTP secrets in PosixLDIF.

    This mixin adds a given OTP payload a given account attribute for owners
    with the given otp type.
    """

    radius_otp_type = 'radius-otp'
    """ OTP type and payload to fetch and use. """

    # TODO: If anyone else ever needs this - change
    # radius_otp_attr/radius_otp_class and implement a subclass in
    # Cerebrum.modules.no.uio with these values.
    #
    # Also, we should probably have the option to both
    #  - omit the attribute if the class is not present
    #  - add the objectClass if not present
    radius_otp_attr = 'uioRadiusOtpSecret'
    """
    Attribute for the otp payload.
    """

    radius_otp_class = 'uioAccountObject'
    """
    objectClass to add for accounts with this attribute.
    """

    @property
    def radius_otp_cache(self):
        """ A cache of otp payloads for all persons. """
        if hasattr(self, '_radius_otp_cache'):
            cache = self._radius_otp_cache
        else:
            cache = self._radius_otp_cache = _get_cache(
                self.db, self.radius_otp_type, self.radius_otp_attr)
        return cache

    def update_user_entry(self, account_id, entry, owner_id):
        """ Add otp attribute and object class to a valid account object. """
        super(RadiusOtpMixin, self).update_user_entry(account_id, entry,
                                                      owner_id)

        try:
            entry[self.radius_otp_attr] = quote(
                self.radius_otp_cache.get_payload(owner_id))
        except LookupError:
            pass
        else:
            entry['objectClass'] = attr_unique(
                entry.get('objectClass', []) + [self.radius_otp_class],
                six.text_type.lower)
