# -*- coding: utf-8 -*-
#
# Copyright 2025 University of Oslo, Norway
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
Fetch and process external ids.

This module provides abstractions for fetching, caching, and selecting external
ids.

:class:`.ExternalIdCache`
    Cache all external ids, or a subset of all external ids.  Useful in any
    scenario where we look up external ids in a single read-only transaction.

:class:`.ExternalIdFetcher`
    Source for the ExternalIdCache - can be used to implement specific id-type
    and/or source-system lookups when caching is explicitly not wanted.

:class:`.ExternalIdSelector`
    Used to priotitize results from an :class:`.EntityCache` (or
    :class:`.EntityFetcher`).  This will filter out unwanted results (e.g. when
    the cache contains multiple id-types), and select the most appropriate
    value (e.g. when the cache contains ids from all available sources).

Things to consider when looking up external ids:

- Which id types and sources should be considered?
- How should the values be prioritized when there are multiple matches?
- Should the results be sanitized?  Should invalid values be ignored?  And if
  so, should secondary values be considered?

Example use
============
A typical use case for this module is to look up given id-types for persons
using the default system lookup order:
::

    # Define id types to look up, and source system priority
    lookup_order = const.get_system_lookup_order()
    select_nin = ExternalIdSelector((sys, const.externalid_fodselsnr)
                                    for sys in lookup_order)
    select_passport = ExternalIdSelector((sys, const.externalid_pass_number)
                                         for sys in lookup_order)

    # Create a cache with all relevant values for select_nin + select_passport
    id_cache = ExternalIdCache.from_selector(db, select_nin, select_passport)
    id_cache.cache_all()

    def get_ldap_object(account):
        ids = id_cache.get(account.owner_id)
        return {
            'norEduPersonNIN': select_nin.get_best_value(ids),
            'uioPassportNumber': select_passport.get_best_value(ids),
            ...
        }

Alternate exmaple use case - create cache with all personal identifiers, and
use it to select system specific identifiers:

    id_cache = ExternalIdCache(db, entity_types=(co.entity_person,))
    id_cache.cache_all()

    select_system_ids = ExternalIdSelector([
        (const.externalid_dfo_pid, const.system_dfo_sap),
        (const.externalid_greg_pid, const.system_greg),
        (const.externalid_studentnr, const.system_fs),
    ])

    def get_system_ids(person):
        return [
            (six.text_type(r['id_type']), r['id_value'])
            for r in select_system_ids(id_cache.get(person.entity_id))
        ]

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
from Cerebrum.entity import external_id
from Cerebrum.Utils import Factory
from Cerebrum.utils import aggregate
from Cerebrum.utils import sorting
from Cerebrum.utils.descriptors import lazy_property

from . import base

logger = logging.getLogger(__name__)

#
# Some helpers to make sure we have the right constants
#


def get_source_system_types(co, values):
    """ Look up a sequence of _AuthoritativeSystemCode values. """
    for value in values:
        yield co.get_constant(Constants._AuthoritativeSystemCode, value)


def get_id_types(co, values):
    """ Look up a sequence of _EntityExternalIdCode values. """
    for value in values:
        yield co.get_constant(Constants._EntityExternalIdCode, value)


def get_entity_types(co, values):
    """ Look up a sequence of _EntityTypeCode values. """
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


#
# Fetch rows from the database
#


class ExternalIdFetcher(base.EntityFetcher):
    """
    Fetch external id data.

    :type id_types: collection of _EntityExternalIdCode, or None
    :type source_systems: collection of _AuthoritativeSystemCode, or None
    :type entity_types: collection of _EntityTypeCode, or None
    """
    def __init__(self, db, id_types, source_systems, entity_types):
        self._db = db
        self._const = Factory.get("Constants")(db)
        self.id_types = (
            None if id_types is None
            else _check_constants(id_types, Constants._EntityExternalIdCode,
                                  "external id")
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
    def id_type_map(self):
        const_type = Constants._EntityExternalIdCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    @lazy_property
    def entity_type_map(self):
        const_type = Constants._EntityTypeCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    @lazy_property
    def source_system_map(self):
        const_type = Constants._AuthoritativeSystemCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    def _normalize_row(self, row):
        # Hacky fixes for bad legacy data
        id_type = self.id_type_map[row['id_type']]
        id_value = six.text_type(row['id_value'])
        entity_type = self.entity_type_map[row['entity_type']]

        return {
            'entity_id': row['entity_id'],
            'entity_type': entity_type,
            'source_system': self.source_system_map[row['source_system']],
            'id_type': id_type,
            'id_value': id_value,
        }

    def _get_results(self, **extra):
        for row in external_id.search_external_ids(
                self._db,
                source_system=self.source_systems,
                id_type=self.id_types,
                entity_type=self.entity_types,
                **extra):
            data = self._normalize_row(row)
            yield (data['entity_id'], data)

    def get_one(self, entity_id):
        """ Fetch authentication data for one account. """
        entity_data = []
        for _, id_data in self._get_results(entity_id=int(entity_id)):
            entity_data.append(id_data)
        return entity_data or base.MISSING

    def get_all(self):
        """ Fetch authentication data for all accounts. """
        results = {}
        for entity_id, id_data in self._get_results():
            values = results.setdefault(int(entity_id), [])
            values.append(id_data)
        return results


#
# Select relevant rows for a given entity from an ExternalIdFetcher
#


class ExternalIdSelector(object):
    """ Filter and sort external id data by priority.  """

    def __init__(self, selector_pairs):
        selector_pairs = tuple(selector_pairs)
        _check_constants(
            set(sys for sys, _ in selector_pairs),
            Constants._AuthoritativeSystemCode,
            code_hint="source system",
        )
        _check_constants(
            set(t for _, t in selector_pairs),
            Constants._EntityExternalIdCode,
            code_hint="external id",
        )

        # Only include these combinatinos
        self._include_pairs = include_pairs = set(selector_pairs)

        # Sanity check for duplicates
        if len(selector_pairs) != len(include_pairs):
            dups = list(aggregate.duplicates(selector_pairs))
            raise ValueError("Duplicate selector entries:" + repr(dups))

        # ... and prioritize by the given order
        self._priority_value = sorting.make_priority_lookup(selector_pairs)

    def _sort_key(self, values):
        return self._priority_value((
            values['source_system'],
            values['id_type'],
        ))

    def __call__(self, results):
        """ Sort and filter a sequence of results """
        matches = [
            m for m in results
            if (m['source_system'], m['id_type']) in self._include_pairs
        ]
        matches.sort(key=self._sort_key)
        return matches

    def get_best_value(self, values):
        """
        Select a single match from a set of values.

        The result does not include the source system or id type.  This only
        makes sense for selectors with a single id_type.
        """
        for match in self(values):
            return match['id_value']
        return None


#
# External id cache
#


class ExternalIdCache(base.EntityCache):
    """
    External id data cache.

    The cache can optionally limit results to specific id types,
    source systems, and/or entity_types.

    :type id_types: collection of _EntityExternalIdCode, or None
    :type source_systems: collection of _AuthoritativeSystemCode, or None
    :type entity_types: collection of _EntityTypeCode, or None
    """
    def __init__(self, db, id_types=None, source_systems=None,
                 entity_types=None):
        fetcher = ExternalIdFetcher(db, id_types, source_systems,
                                    entity_types)
        super(ExternalIdCache, self).__init__(fetcher)

    @classmethod
    def from_selector(cls, db, selector, *selectors):
        """ Create a cache with values from the given selector(s). """
        id_types = set()
        source_systems = set()
        for sel in (selector,) + selectors:
            id_types.update(id_t for _, id_t in sel._include_pairs)
            source_systems.update(sys for sys, _ in sel._include_pairs)
        return cls(db, id_types=id_types, source_systems=source_systems)
