# -*- coding: utf-8 -*-
#
# Copyright 2022-2024 University of Oslo, Norway
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
Abstract org unit mapper and object for import.

TODO
----
The ou import currently requires location codes (stedkode) to work properly, as
most models *require* this id type.  In the future, we should use the
:meth:`.OrgUnitMapper.get_id` and :meth:`.OrgUnitMapper.get_parent_id` as
temporary, in-memory ids when bulding and validating org trees.

See the :mod:`Cerebrum.modules.ou_import` module for more details.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.utils.reprutils import ReprFieldMixin

logger = logging.getLogger(__name__)


def normalize_sko(value):
    """
    Validates and normalizes a location code (stedkode) value.

    >>> normalize_sko(123)
    "000123"
    >>> normalize_sko(" 54321 ")
    "054321"
    """
    try:
        code = int(value)
    except (TypeError, ValueError):
        raise ValueError("location code must be numerical: "
                         + repr(value))
    code = format(code, '06d')
    if len(code) != 6:
        raise ValueError("location code must be a six-digit string: "
                         + repr(value))
    return code


def sko_to_tuple(value):
    """
    location code (stedkode) string to three-part tuple.

    >>> sko_to_tuple("010203")
    (1, 2, 3)
    """
    code = normalize_sko(value)
    return (int(code[0:2]), int(code[2:4]), int(code[4:6]))


def tuple_to_sko(value):
    """
    location code (stedkode) three-part tuple to string.

    >>> tuple_to_sko((1, 2, 3))
    "010203"
    """
    if len(value) != 3:
        raise ValueError("location tuple must contain three items: "
                         + repr(value))
    if any(v < 0 or v > 99 for v in map(int, value)):
        raise ValueError("location tuple values must be in range 0-99: "
                         + repr(value))
    code = ''.join(format(int(v), '02d') for v in value)
    return normalize_sko(code)


class PreparedOrgUnit(ReprFieldMixin):
    """
    Representation of org unit data for import.

    Data in this object will be imported/updated directly into Cerebrum by
    py:class:`.ou_sync.OuWriter`.
    """

    repr_id = True
    repr_module = False
    repr_fields = ('location_code', 'is_valid')

    def __init__(self, location_code, is_valid=False, is_visible=False):
        if isinstance(location_code, tuple):
            self.location_code = tuple_to_sko(location_code)
        else:
            self.location_code = normalize_sko(location_code)

        self.is_valid = is_valid
        self.is_visible = is_visible
        self._addresses = {}
        self._contact_info = {}
        self._external_ids = {}
        self._names = {}
        self.usage_codes = set()

    @property
    def location_t(self):
        """ location code (stedkode) string. """
        return sko_to_tuple(self.location_code)

    def add_address(self, address_type, address_fields):
        field_names = set(('address_text', 'p_o_box', 'postal_number', 'city',
                           'country',))
        self._addresses[address_type] = {
            f: (address_fields.get(f) or None)
            for f in field_names
        }

    @property
    def addresses(self):
        """ sequence of address (type, value-dict) tuples. """
        return tuple(self._addresses.items())

    def add_contact_info(self, c_type, c_value):
        self._contact_info[c_type] = c_value

    @property
    def contact_info(self):
        """ sequence of contact info (type, value) tuples. """
        return tuple(self._contact_info.items())

    def add_external_id(self, id_type, id_value):
        self._external_ids[id_type] = id_value

    @property
    def external_ids(self):
        """ sequence of external id (type, value) tuples. """
        return tuple(self._external_ids.items())

    def add_name(self, name_type, name_lang, name_value):
        name_obj = self._names.setdefault(name_type, {})
        name_obj[name_lang] = name_value

    def _iter_names(self):
        for name_type, localized in self._names.items():
            for lang, value in localized.items():
                yield name_type, lang, value

    @property
    def names(self):
        """ sequence of name (type, lang, value) tuples. """
        return tuple(self._iter_names())

    def add_usage_code(self, code):
        self.usage_codes.add(code)

    def to_dict(self):
        """
        Serialize import object to dict
        """
        data = {
            'location': self.location_code,
            'is_valid': bool(self.is_valid),
            'is_visible': bool(self.is_visible),
        }
        if self._addresses:
            addrs = data['addresses'] = {}
            for addr_type, addr_values in self._addresses.items():
                addrs[addr_type] = dict(addr_values)
        if self._contact_info:
            data['contact_info'] = dict(self._contact_info)
        if self._external_ids:
            data['external_ids'] = dict(self._external_ids)
        if self._names:
            names = data['names'] = {}
            for name_type, name_vals in self._names.items():
                names[name_type] = dict(name_vals)
        if self.usage_codes:
            data['usage_codes'] = tuple(self.usage_codes)
        return data

    @classmethod
    def from_dict(cls, d):
        """
        De-serialize import object from dict
        """
        obj = cls(
            d['location'],
            bool(d['is_valid']),
            bool(d['is_visible']),
        )
        for addr_type, addr_vals in (d.get('addresses') or {}).items():
            obj.add_address(addr_type, addr_vals)

        for c_type, c_val in (d.get('contact_info') or {}).items():
            obj.add_contact_info(c_type, c_val)

        for id_type, id_val in (d.get('external_ids') or {}).items():
            obj.add_external_id(id_type, id_val)

        for name_type, name_vals in (d.get('names') or {}).items():
            for lang, name in (name_vals or {}).items():
                obj.add_name(name_type, lang, name)

        for usage_code in (d.get('usage_codes') or ()):
            obj.add_usage_code(usage_code)

        return obj


class OrgUnitMapper(object):

    def get_id(self, ou_data):
        """ id to use when building org tree. """
        raise NotImplementedError()

    def get_parent_id(self, ou_data):
        """ parent id to use when building org tree. """
        raise NotImplementedError()

    def get_location_code(self, ou_data):
        """ Get stedkode (if present) from ou_data.

        :param dict ou_data: an ou data structure

        :returns str: Returns a location code, or None if no stedkode exists.
        """
        return None

    def get_external_ids(self, ou_data):
        """ Get external_id identifiers from ou_data.

        :param dict ou_data: an ou data structure

        :rtype: generator
        :returns:
            zero or more tuples with (id_type, external_id)
        """
        if False:
            # never-reached yield to make this a generator
            #
            # should yield (id_type strval, external_id) for all valid external
            # ids present in ou_data
            yield (None, None)

    def get_names(self, ou_data):
        """ Get localized names from ou_data.

        :param dict ou_data: an ou data structure

        :rtype: generator
        :returns:
            zero or more tuples with (name_variant, name_lang, name)

        .. note::
           It is an error to return a name type that is not listed by
           `.name_types`.
        """
        if False:
            # never-reached yield to make this a generator
            #
            # should yield (name_variant, name_lang, name) for all valid
            # names present in ou_data
            yield (None, None, None)

    def get_contact_info(self, ou_data):
        """ Get contact info from ou_data.

        :param dict ou_data: an ou data structure

        :rtype: generator
        :returns:
            zero or more tuples with (contact_type strval, contact_value)
        """
        if False:
            # never-reached yield to make this a generator
            #
            # should yield (contact_type, contact_value) for all valid contact
            # types present in ou_data
            yield (None, None)

    def get_addresses(self, ou_data):
        """ Get address info from ou_data.

        :param dict ou_data: an ou data structure

        :rtype: generator
        :returns:
            zero or more tuples with (address_type strval, address_column dict)

            Accepted address columns are:
             - address_text
             - p_o_box
             - postal_number
             - city
             - country
        """
        if False:
            # never-reached yield to make this a generator
            #
            # (addr_type, {<address dict>})
            # see EntityAddress.populate_address for keywords/column names:
            yield (None, {})

    def is_valid(self, ou_data):
        """ If this org unit is an valid/active org unit. """
        return False

    def is_visible(self, ou_data):
        """ If this org unit should be included in public views. """
        if not self.is_valid(ou_data):
            # Expired org units are *soft deleted* and are never published.
            return False
        return False

    def get_usage(self, ou_data):
        """ Usage codes for this org unit.

        Known usage codes are defined in ``cereconf.OU_USAGE_SPREAD``, and are
        used to map various tags and properties from the source system to
        automatic spreads.
        """
        if not self.is_valid(ou_data):
            return ()
        # Example: ('Arkivsted', 'Tillatt Organisasjon')
        return ()

    def prepare(self, ou_data):
        """
        Get a OrgUnit object to import/update

        :param dict ou_data: ou data from source system

        :rtype: OrgUnit
        """
        obj = PreparedOrgUnit(
            location_code=self.get_location_code(ou_data),
            is_valid=self.is_valid(ou_data),
            is_visible=self.is_visible(ou_data),
        )
        for addr_type, addr_values in self.get_addresses(ou_data):
            obj.add_address(addr_type, addr_values)

        for c_type, c_value in self.get_contact_info(ou_data):
            obj.add_contact_info(c_type, c_value)

        for id_type, id_value in self.get_external_ids(ou_data):
            obj.add_external_id(id_type, id_value)

        for name_type, lang, name in self.get_names(ou_data):
            obj.add_name(name_type, lang, name)

        for code in self.get_usage(ou_data):
            obj.add_usage_code(code)

        return obj
