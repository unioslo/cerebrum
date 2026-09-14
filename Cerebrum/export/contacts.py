# -*- coding: utf-8 -*-
#
# Copyright 2026 University of Oslo, Norway
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
Fetch, cache, and process contact info.

This module provides abstractions for fetching, selecting, and filtering
contact info by *entity type*, *source system*, and *contact type*.


Contact objects
----------------
Each contact value returned by :class:`.ContactInfoCache`
is a normalized contact info row.  This is a :class:`dict` with:
::

    {
        'entity_id': int,
        'source_system': _AuthoritativeSystemCode,
        'contact_type': _ContactInfoCode,
        'contact_pref': int,
        'contact_value': str,
        'contact_alias': str or None,
        'description': str or None,
        'last_modified': datetime.date,
    }

``contact_pref``
    This is a legacy feature used to prioritize contact info.

    It is currently only used to prioritize values with the same *source
    system* and *contact type* (i.e. a tie-breaker).  These duplicate values
    should generally not exist in the database.

    See :mod:`Cerebrum.entity.contact_info` for more details.

``contact_value``
    Our cache fixes some legacy issues in contact info values.  These fixes are
    likely in place to deal with bad source data, mainly from fields with
    *multiple* values separated by a delimiter.

    - If the value contains multiple ``$``-separated values, we use the
      first value.

    - This is repeated for phone/mobile like contact types, but with a
      ``/``-delimiter.

``contact_alias``
    This value is a legacy field, and is *only* used for the UiO
    VoIP ``EXTENSION`` contact type.

    See :mod:`Cerebrum.entity.contact_info` for more details.

``description``
    This value is a legacy field, and has never been used in Cerebrum.  All
    objects should return ``None`` here.

    See :mod:`Cerebrum.entity.contact_info` for more details.

``last_modified``
    This value is normalized to a *date*, although it is a TIMESTAMP in the
    database.  This is likely a bug, and might be changed.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import six

from Cerebrum import Constants
from Cerebrum.entity import contact_info
from Cerebrum.Utils import Factory
from Cerebrum.utils import aggregate
from Cerebrum.utils import date_compat
from Cerebrum.utils.descriptors import lazy_property
from . import base


logger = logging.getLogger(__name__)


def get_source_system_types(co, values):
    """ Helper to look up a sequence of _AuthoritativeSystemCode values. """
    for value in values:
        yield co.get_constant(Constants._AuthoritativeSystemCode, value)


def get_contact_types(co, values):
    """ Helper to look up a sequence of _ContactInfoCode values. """
    for value in values:
        yield co.get_constant(Constants._ContactInfoCode, value)


def get_entity_types(co, values):
    """ Helper to look up a sequence of _EntityTypeCode values. """
    for value in values:
        yield co.get_constant(Constants._EntityTypeCode, value)


def _check_constants(codes, code_type, code_hint,
                     unique=True, allow_empty=False):
    """ Check a sequence of _CerebrumCode values of a specific type. """
    codes = tuple(codes)
    if not (allow_empty or codes):
        raise ValueError("No %s types given" % (code_hint,))
    for code in codes:
        if not isinstance(code, code_type):
            raise ValueError("Invalid %s type: %s" % (code_hint, repr(code)))
    if unique and len(codes) != len(set(codes)):
        raise ValueError("Duplicate %s type given: %s"
                         % (code_hint, repr(codes)))
    return codes


class _ContactInfoFetcher(base.EntityFetcher):
    """ Fetch contact info. """
    def __init__(self, db, contact_types, source_systems, entity_types):
        self._db = db
        self._const = Factory.get("Constants")(db)
        self.contact_types = (
            None if contact_types is None
            else _check_constants(contact_types, Constants._ContactInfoCode,
                                  "contact")
        )
        self.source_systems = (
            None if source_systems is None
            else _check_constants(source_systems,
                                  Constants._AuthoritativeSystemCode,
                                  "source system")
        )
        self.entity_types = (
            None if entity_types is None
            else _check_constants(entity_types, Constants._EntityTypeCode,
                                  "entity")
        )

    @lazy_property
    def contact_type_map(self):
        const_type = Constants._ContactInfoCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    @lazy_property
    def source_system_map(self):
        const_type = Constants._AuthoritativeSystemCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    def _normalize_row(self, row):
        return {
            'entity_id': row['entity_id'],
            'source_system': self.source_system_map[row['source_system']],
            'contact_type': self.contact_type_map[row['contact_type']],
            'contact_pref': row['contact_pref'],
            'contact_value': row['contact_value'],
            'contact_alias': row['contact_alias'],
            'description': row['description'],
            'last_modified': date_compat.get_date(row['last_modified']),
        }

    def _get_results(self, **extra):
        for row in contact_info.search_contact_info(
                self._db,
                source_system=self.source_systems,
                contact_type=self.contact_types,
                entity_type=self.entity_types,
                **extra):
            data = self._normalize_row(row)
            if not data:
                continue
            yield (data['entity_id'], data)

    def get_one(self, entity_id):
        """ Fetch contact info for one entity. """
        results = [
            row_like
            for _, row_like in self._get_results(entity_id=int(entity_id))
        ]
        return results or base.MISSING

    def get_all(self):
        """ Fetch contact info for all entities. """
        return aggregate.dict_collect_lists(self._get_results())


class _LegacyDataMixin(_ContactInfoFetcher):
    """
    A mixin to _ContactInfoFetcher that normalizes contact info values.

    This legacy cleanup is from Cerebrum.modules.OrgLDIF.  The data should
    probably be sanitized going into the database, rather than here.

    .. todo::
       Is this still a problem?
    """
    def _normalize_row(self, row):
        row = super(_LegacyDataMixin, self)._normalize_row(row)

        c_type = row['contact_type']
        c_type_str = six.text_type(c_type)
        c_value = row['contact_value']

        if "$" in c_value:
            # Special contact info value lists with '$' as separator
            logger.warning("bad data for id=%d: %d '$' separated values",
                           row['entity_id'], len(c_value.split("$")))
            values = [part for part in c_value.split("$") if part.strip()]
            if not values:
                return None
            c_value = values[0]

        if ("/" in c_value
                and ("PHONE" in c_type_str or "MOBILE" in c_type_str)):
            # Multiple phone numbers separated by '/'
            logger.warning("bad data for id=%d: %d '/' separated numbers",
                           row['entity_id'], len(c_value.split("/")))
            values = [part for part in c_value.split("/") if part.strip()]
            if not values:
                return None
            c_value = values[0]

        row.update({'contact_value': c_value})
        return row


class ContactInfoCache(base.EntityCache):
    """
    ContactInfo data cache.

    Fetches and caches `Contact objects`_, optionally limited to specific
    contact types, source systems, or entity types.
    """

    fetcher_cls = _LegacyDataMixin

    def __init__(self, db, contact_types=None, source_systems=None,
                 entity_types=None):
        """
        :type db: Cerebrum.database.Database
        :type contact_types: collection of _ContactInfoCode, or None
        :type source_systems: collection of _AuthoritativeSystemCode, or None
        :type entity_types: collection of _EntityTypeCode, or None
        """
        fetcher = self.fetcher_cls(db, contact_types, source_systems,
                                   entity_types)
        super(ContactInfoCache, self).__init__(fetcher)

    @classmethod
    def from_selector(cls, db, selector, *selectors):
        """
        Create a cache with values for the given selector(s).

        :type db: Cerebrum.database.Database
        :type selector: ContactInfoSelector

        :rtype: ContactInfoCache
        :returns:
            A cache with contact types and source systems from the selector(s).
        """
        contact_types = set()
        source_systems = set()
        for sel in (selector,) + selectors:
            contact_types.update(t for _, t in sel.specification)
            source_systems.update(sys for sys, _ in sel.specification)

        if None in contact_types:
            contact_types = None
        if None in source_systems:
            source_systems = None

        return cls(db, contact_types=contact_types,
                   source_systems=source_systems)


def _get_source_systems(specification):
    """ extract source system values from a selector spec """
    items = [
        source_system for source_system, _ in specification
        if source_system is not None
    ]
    return _check_constants(items, Constants._AuthoritativeSystemCode,
                            "source system", allow_empty=True, unique=False)


def _get_contact_types(specification):
    """ extract contact type values from a selector spec """
    items = [
        contact_type for _, contact_type in specification
        if contact_type is not None
    ]
    return _check_constants(items, Constants._ContactInfoCode,
                            "contact", allow_empty=True, unique=False)


class ContactInfoSelector(object):
    """
    Filter and sort contact info by priority.

    This callable object can be used to prioritize `Contact objects`_ from a
    :class:`.ContactInfoCache`.

    This will filter out unwanted results (e.g. when the cache contains
    multiple contact types), and select the most appropriate value (e.g. when
    the cache contains data from all available sources).

    Use this to get the best matching contact info value for a given
    entity.
    """

    def __init__(self, specification):
        """
        :type specification: list or tuple
        :param specification:
            An ordered sequence of (source system, contact type) pairs.

            Each value must be its corresponding constant type, or ``None`` to
            indicate a wildcard value.  E.g.:
            ::

                [
                    (<fs>, <mobile>),
                    (<greg>, <privatemobile>),
                    (None, <mobile>),
                ]
        """
        # Sanity check our specification
        _get_source_systems(specification)
        _get_contact_types(specification)

        spec_set = set(specification)
        if len(spec_set) != len(specification):
            dups = list(aggregate.duplicates(spec_set))
            raise ValueError("Duplicate selector entries:" + repr(dups))

        self.specification = specification
        self.default_pri = len(specification)

    def _sort_key(self, contact_row):
        s = contact_row['source_system']
        t = contact_row['contact_type']
        for key in ((s, t), (s, None), (None, t), (None, None)):
            if key in self.specification:
                pri = self.specification.index(key)
                break
        else:
            pri = self.default_pri

        # - sort *primarily* by source system
        # - sort by source + type, so that we get consistent sorting for
        #   wildcard values.  Should generally not use this, but rather
        #   generate pairs from e.g. system_lookup_order.
        # - sort by contact_pref, to get consistent sorting for any contacts of
        #   the same source + type (shouldn't exist - we try to avoid using
        #   pref)
        #
        # This is essentially `EntityContactInfo.sort_contact_info`, but this
        # implementation relies less on contact_pref
        return (pri, s, t, contact_row['contact_pref'])

    def _is_match(self, contact_row):
        s = contact_row['source_system']
        t = contact_row['contact_type']
        keys = [(s, t), (s, None), (None, t), (None, None)]
        return any(key in self.specification for key in keys)

    def __call__(self, contact_list):
        """
        Filter and sort a contact info.

        :type contact_list: iterable[dict]
        :param contact_list: An iterable of contact info dicts to filter and sort

        :rtype: list[dict]
        :returns: A sorted list of matching Contact info objects.
        """
        return sorted(
            (row_like for row_like in contact_list
             if self._is_match(row_like)),
            key=self._sort_key
        )

    def get_best_value(self, contact_list):
        """
        Select a single match from a list of contact info.

        The result does not include the source system or id type.  This only
        makes sense for selectors that include contact types in the same
        category (e.g. phone numbers).

        :type contact_list: iterable[dict]
        :param contact_list: An iterable of Contact objects to select from

        :rtype: str or None
        :returns: The best (first) match according to this selector
        """
        for row in self(contact_list):
            return row['contact_value']


def parse_selector(const, specification):
    """
    Parse and normalize selector pairs.

    This can be used to translate selector pairs with scalar values
    (e.g.  from a config) into a selector pairs that can be used with
    :class:`.ContactInfoSelector`:
    ::

        config = [("FS", "MOBILE"), (None, "MOBILE")]
        selector_pairs = list(parse_selector(config))
        select_mobile = ContactInfoSelector(selector_pairs)

    :type const: Cerebrum.Constants.Constants
    :type specification: iterable
    :param specification:
        An ordered sequence of (source system, contact type) values.

    :rtype: generator
    :returns:
        Tuples of (source system, contact type) pairs, where all values are
        its corresponding constant (or None for wildcards).
    """
    for ss_value, ct_value in specification:
        if ss_value is None:
            source_system = None
        else:
            source_system = const.get_constant(
                Constants._AuthoritativeSystemCode,
                ss_value,
            )
        if ct_value is None:
            contact_type = None
        else:
            contact_type = const.get_constant(
                Constants._ContactInfoCode,
                ct_value
            )
        yield source_system, contact_type
