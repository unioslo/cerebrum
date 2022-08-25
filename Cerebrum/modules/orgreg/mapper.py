# -*- coding: utf-8 -*-
#
# Copyright 2022 University of Oslo, Norway
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
Utils for extracting Cerebrum-data from Orgreg objects.

Import/update utils should use a py:class:`.OrgregMapper` to extract relevant
Cerebrum data from a (sanitized) Orgreg org unit.
"""
import datetime
import logging

import six

from Cerebrum.modules.ou_import.ou_model import OrgUnitMapper, normalize_sko

logger = logging.getLogger(__name__)


def get_external_key(ou_data, source, id_type):
    """
    Get a given external key value from an orgreg ou dict

    :param ou_data: normalized data from ``parse_org_unit``
    :param source: source value in external_keys
    :param type: type value in external_keys

    :returns: matching value

    >>> get_external_key(
    ...     {'externalKeys': ['sourceSystem': 'a': 'type': 'b', 'value': 'c']},
    ...     'a', 'b')
    'c'
    """
    what = ('external key %r %r for orgreg_id=%r'
            % (source, id_type, ou_data['ouId']))
    values = [
        kobj['value']
        for kobj in ou_data['externalKeys']
        if kobj['sourceSystem'] == source and kobj['type'] == id_type]
    # We should probably raise a LookupError, but we only use this from
    # OrgRegMapper anyway, and want to raise a ValueError if we're missing
    # required fields.
    if len(values) > 1:
        raise ValueError('duplicate ' + what)
    if len(values) < 1:
        raise ValueError('no ' + what)
    return values[0]


class OrgregMapper(OrgUnitMapper):
    """
    Get import values from an abstract ou dict.

    All functions takes a normalized (see py:func:`.datasource.parse_org_unit`)
    org unit dict as input.
    """

    def get_id(self, ou_data):
        """
        Get a unique org unit key.

        :returns:
            A key to uniquely identify this org unit in e.g. a tree structure.
        """
        return 'orgreg-id:{}'.format(ou_data['ouId'])

    def get_parent_id(self, ou_data):
        """
        Get a unique org unit key for parent.

        :returns:
            A key to uniquely identify the parent in e.g. a tree structure, or
            `None` if no parent is set.
        """
        p_id = ou_data.get('parent')
        if p_id:
            return 'orgreg-id:{}'.format(p_id)
        return None

    def get_location_code(self, ou_data):
        """
        Get location code (sko/stedkode).

        :returns: Six-digit location code string (or None if no code is set).
        """
        try:
            raw_sko = get_external_key(ou_data, 'sapuio', 'legacy_stedkode')
        except ValueError:
            return None
        else:
            return normalize_sko(raw_sko)

    def get_addresses(self, ou_data):
        """
        Get addresses from org unit.

        :rtype: generator
        :returns:
            Pairs with (<address type>, <address dict>).  The address dict
            contains all the keys/columns to use with entity_address.
        """
        orgreg_id = ou_data['ouId']

        def _get_address_dict(addr_type):
            addr = ou_data.get(addr_type)
            if not addr:
                return {}
            address_text = "\n".join(
                line for line in (addr.get('street'), addr.get('extended'))
                if line)
            if not address_text:
                # If we ever get p_o_box values from Orgreg, we may want to
                # allow empty address_texts.  For now, any address without an
                # address text is of no use in Cerebrum.
                return {}
            if not addr.get('country') == "NO":
                # TODO: Should we skip these addresses?  It makes little sense
                # to import non-norwegian addresses into Cerebrum when we don't
                # include country.
                logger.debug('invalid country for orgreg_id=%r: %r - %r',
                             orgreg_id, addr.get('country'), addr)
            return {
                'address_text': address_text,
                'p_o_box': None,
                'postal_number': addr.get('postalCode') or None,
                'city': addr.get('city') or None,
                'country': None,
            }

        post = _get_address_dict('postalAddress')
        if post:
            yield 'POST', post

        visit = _get_address_dict('visitAddress')
        if visit:
            yield 'STREET', visit

    def get_contact_info(self, ou_data):
        """
        Get contact info from org unit.

        :rtype: generator
        :returns: Pairs with (<contact type>, <contact value>).
        """
        url = ou_data.get('homepage', {})
        candidates = (
            ('EMAIL', ou_data.get('email')),
            ('FAX', ou_data.get('fax')),
            ('PHONE', ou_data.get('phone')),
            ('URL', url.get('nb') or url.get('en')),
        )
        for c_type, c_value in candidates:
            if c_value:
                yield (c_type, c_value)

    def get_external_ids(self, ou_data):
        """
        Get external ids from org unit.

        :rtype: generator
        :returns: Pairs with (<id type>, <id value>).
        """
        yield ('ORGREG_OU_ID', six.text_type(ou_data['ouId']))
        yield ('DFO_OU_ID', get_external_key(ou_data, 'dfo_sap', 'dfo_org_id'))

    def get_names(self, ou_data):
        """
        Get names from org unit.

        :rtype: generator
        :returns: Tuples with (<name variant>, <language>, <name value>).
        """
        orgreg_id = ou_data['ouId']

        # TODO: Figure out acronym usage (ref CRB-3701): Shouldn't the
        # shortName and acronym termonology be reversed?
        #
        # For now - /short/OU short/shortName/ is a globally unique acronym,
        # and is required for all org units
        if not ou_data['shortName']['nb']:
            raise ValueError('missing shortName (globally unique acronym)'
                             'for orgreg_id=%r' % (orgreg_id,))

        short = {
            # short name is only set in nb, and should not be different in
            # various languages -- so we set the nb value for all languages in
            # use
            'nb': ou_data['shortName']['nb'],
            'en': ou_data['shortName']['nb'],
        }

        # For now - /acronym/OU acronym/ is a contextual acronym, not
        # guaranteed to be unique
        acronym = ou_data['acronym']

        name = ou_data['name']
        long = ou_data['longName']
        display = name or long

        # dump all results
        candidates = (
            ('OU acronym', acronym),
            ('OU short', short),
            ('OU name', name),
            ('OU display', display),
            # ('OU long', long),
        )
        for (name_type, name_source) in candidates:
            for lang, value in (name_source or {}).items():
                if value:
                    yield (name_type, lang, value)

    def is_valid(self, ou_data, _today=None):
        """
        Check if org unit is valid *now*.

        :rtype: bool
        """
        today = _today or datetime.date.today()
        valid_from = ou_data['validFrom']
        valid_to = ou_data.get('validTo')
        return (today > valid_from and (valid_to is None or today < valid_to))

    def is_visible(self, ou_data):
        """
        Check if org unit should be visible (published in catalogs, etc...)

        :rtype: bool
        """
        if not self.is_valid(ou_data):
            # expired org units are *soft deleted* and are never published.
            return False
        return "elektronisk_katalog" in (ou_data.get('tags') or ())

    def get_usage(self, ou_data):
        """
        Get org unit usage.

        Usage are keywords that typically describes where and how the org unit
        should be used.  In Orgreg this is controlled by various *tags*.

        :rtype: tuple
        :returns: A sequence of usage strings.
        """
        if not self.is_valid(ou_data):
            # only valid org units can have usages
            return tuple()

        # TODO: should we maybe just update the OU_USAGE_SPREAD to include the
        # Orgreg tags, rather than do this extra step?
        tag_to_usage = {
            "arkivsted": "Arkivsted",
            "tillatt_organisasjon": "Tillatt Organisasjon",
        }

        def translate_tags(tags):
            for tag in tags:
                usage = tag_to_usage.get(tag)
                if usage:
                    yield usage
        return tuple(translate_tags(ou_data['tags']))
