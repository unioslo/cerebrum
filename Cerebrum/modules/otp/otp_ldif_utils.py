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
OTP LDAP export utils.

This module implements utils for fetching, caching and formatting otp payloads
for LDAP.

It implements two LDAP export mixins:

- py:class:`NorEduOtpMixin` for otp_type='feide-ga'
- py:class:`RadiusOtpMixin` for otp_type='radius-otp'

These mixins must be present in CLASS_ORGLDIF/CLASS_POSIXLDIF to include OTP
data in their respective LDAP exports.
"""
from __future__ import unicode_literals

import logging

from six.moves.urllib.parse import quote

from Cerebrum.Utils import make_timer
from Cerebrum.export.base import EntityCache, EntityFetcher, MISSING
from Cerebrum.modules.LDIFutils import attr_unique, normalize_string
from Cerebrum.modules.PosixLDIF import PosixLDIFRadius
from Cerebrum.modules.no.OrgLDIF import norEduLDIFMixin

from .otp_db import sql_search


logger = logging.getLogger(__name__)


class _OtpFetcher(EntityFetcher):
    """
    Fetch otp_payload for persons.

    Example usage:

        # fetch cache
        otp_fetcher = _OtpFetcher(db, ('type-foo', 'type-bar'))

        # fetch relevant otp data for person_id=3
        otp_data = otp_fetcher.get_one(3)
        # get payload for otp_type='type-foo'
        payload = otp_data['type-foo']

        # fetch all relevant otp data
        all_otp_data = otp_fetcher.get_all()
        # get payload for otp_type='type-foo' for person_id=3
        payload = all_otp_data[3]['type-foo']
    """

    def __init__(self, db, otp_types=None):
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
    A cache of personal otp values.

    Example usage:

        # Configure and initialize cache for otp_type='type-foo'
        otp_cache = OtpCache(db, 'type-foo')

        # Optionally, cache all relevant data up front
        otp_cache.update_all()

        # Get otp_payload value for person_id=3
        secret = otp_cache.get_payload(3)
    """

    def __init__(self, db, otp_type):
        """
        :param auth_types:
            An ordered sequence of preferred authentication codes
        """
        self.otp_type = otp_type
        super(OtpCache, self).__init__(_OtpFetcher(db, (otp_type,)))

    def get_payload(self, person_id):
        """
        Get otp payload for a given person.

        :param account_id:
            The account to look up

        :rtype: tuple
        :return: A tuple with the authentication code and data
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


def format_ldap_value(fmt, secret, label='OTP'):
    """ Format ldap otp secret from pre-defined formatstring. """
    return fmt.format(
        secret=quote(secret),
        label=quote(label))


class NorEduOtpMixin(norEduLDIFMixin):
    """
    Mixin to provide encrypted OTP secrets in OrgLDIF/norEduLDIFMixin

    This mixin adds or extends the *norEduPersonAuthnMethod* attribute with
    data from otp_type='feide-ga'.
    """

    feide_otp_type = 'feide-ga'

    # Format for the ldap attribute value.
    # secret and label should be percent-encoded according to rfc3986.
    feide_ldap_fmt = 'urn:mace:feide.no:auth:method:ga {secret} label={label}'

    @property
    def feide_otp_cache(self):
        if hasattr(self, '_feide_otp_cache'):
            cache = self._feide_otp_cache
        else:
            cache = self._feide_otp_cache = _get_cache(
                self.db, self.feide_otp_type, 'norEduPersonAuthnMethod')
        return cache

    def update_person_authn(self, entry, person_id):
        super(NorEduOtpMixin, self).update_person_authn(entry, person_id)

        try:
            secret = format_ldap_value(
                self.feide_ldap_fmt,
                self.feide_otp_cache.get_payload(person_id)
            )
        except LookupError:
            return

        # there *shouldn't* be any value collisions here, as encrypted TOTP
        # values use a distinct urn - if we ever make a new mixin that *also*
        # produce norEduPersonAuthnMethod values with the same urn this should
        # be re-done
        to_add = attr_unique([secret], normalize=normalize_string)

        # update entry attr with totp values
        if entry.get('norEduPersonAuthnMethod'):
            entry['norEduPersonAuthnMethod'].extend(to_add)
        else:
            entry['norEduPersonAuthnMethod'] = to_add


class RadiusOtpMixin(PosixLDIFRadius):
    """
    Mixin to provide encrypted OTP secrets in PosixLDIF.

    This mixin adds data OTP-data from otp_type=*radius_otp_type* to the LDAP
    attribute *radius_otp_attr* for users, if available.
    """

    radius_otp_type = 'radius-otp'
    radius_otp_attr = 'uioRadiusOtpSecret'
    radius_otp_fmt = '{secret}'

    @property
    def radius_otp_cache(self):
        if hasattr(self, '_radius_otp_cache'):
            cache = self._radius_otp_cache
        else:
            cache = self._radius_otp_cache = _get_cache(
                self.db, self.radius_otp_type, self.radius_otp_attr)
        return cache

    def update_user_entry(self, account_id, entry, owner_id):
        try:
            entry[self.radius_otp_attr] = format_ldap_value(
                self.radius_otp_fmt,
                self.radius_otp_cache.get_payload(owner_id)
            )
        except LookupError:
            pass

        return super(RadiusOtpMixin, self).update_user_entry(account_id,
                                                             entry, owner_id)
