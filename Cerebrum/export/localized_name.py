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
Fetch and process localized names.

This module provides abstractions for fetching, selecting and filtering
entity name by *name type* and *language*.

The caching functionality is useful in any scenario where we look up names
in a single read-only transaction.  The selection functionality is useful for
selecting a single name value in any scenario.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum import Constants
from Cerebrum.Entity import EntityNameWithLanguage
from Cerebrum.Utils import Factory
from Cerebrum.utils import reprutils
from Cerebrum.utils.aggregate import dict_collect_lists
from Cerebrum.utils.descriptors import lazy_property
from Cerebrum.utils.sorting import make_priority_lookup
from . import base


logger = logging.getLogger(__name__)


def get_name_types(co, values):
    """ Helper to look up a sequence of _EntityNameCode values. """
    for value in values:
        # TODO: Fix
        yield co.get_constant(Constants._EntityNameCode, value)


def get_name_languages(co, values):
    """ Helper to look up a sequence of _LanguageCode values. """
    for value in values:
        # TODO: Fix
        yield co.get_constant(Constants._LanguageCode, value)


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


class NameFetcher(base.EntityFetcher):
    """
    Fetch name data.

    :type name_types: collection of _EntityNameCode, or None
    :type languages: collection of _LanguageCode, or None
    :type entity_types: collection of _EntityTypeCode, or None
    """
    def __init__(self, db, name_types, languages, entity_types):
        self._db = db
        self._const = Factory.get("Constants")(db)
        self.name_types = (
            None if name_types is None
            else _check_constants(name_types, Constants._EntityNameCode,
                                  "name")
        )
        self.languages = (
            None if languages is None
            else _check_constants(languages,
                                  Constants._LanguageCode,
                                  "language")
        )
        self.entity_types = (
            None if entity_types is None
            else _check_constants(entity_types, Constants._EntityTypeCode,
                                  "entity")
        )

    @lazy_property
    def entity_type_map(self):
        const_type = Constants._EntityTypeCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    @lazy_property
    def name_type_map(self):
        const_type = Constants._EntityNameCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    @lazy_property
    def language_type_map(self):
        const_type = Constants._LanguageCode
        return {int(c): c for c in self._const.fetch_constants(const_type)}

    def _normalize_row(self, row):
        if not row['name'] or not row['name'].strip():
            # Sanity check
            return {}
        return {
            'entity_id': row['entity_id'],
            'entity_type': self.entity_type_map[row['entity_type']],
            'name_variant': self.name_type_map[row['name_variant']],
            'name_language': self.language_type_map[row['name_language']],
            'name': row['name'],
        }

    def _get_results(self, entity_id=None):
        name_db = EntityNameWithLanguage(self._db)
        for row in name_db.search_name_with_language(
                entity_type=self.entity_types,
                name_variant=self.name_types,
                name_language=self.languages,
                entity_id=entity_id):
            data = self._normalize_row(row)
            if not data:
                continue
            yield (data['entity_id'], data)

    def get_one(self, entity_id):
        """ Fetch name data for one matching entity. """
        entity_data = [
            name_data
            for _, name_data in self._get_results(entity_id=int(entity_id))
        ]
        return entity_data or base.MISSING

    def get_all(self):
        """ Fetch name data for all matching entities. """
        return dict_collect_lists(self._get_results())


class NameCache(base.EntityCache):
    """
    Localized name data cache.

    The cache can optionally limit results to specific name types,
    languages, and/or entity_types.

    :type name_types: collection of _EntityNameCode, or None
    :type languages: collection of _LanguageCode, or None
    :type entity_types: collection of _EntityTypeCode, or None
    """
    def __init__(self, db, name_types=None, languages=None, entity_types=None):
        fetcher = NameFetcher(db, name_types, languages, entity_types)
        super(NameCache, self).__init__(fetcher)


class NameSelector(reprutils.ReprFieldMixin):
    """
    Helper to select a prioritized list of names from a cached name result.

    Use this to get the best matching name of a given type for a given
    entity.
    """
    repr_id = False
    repr_module = False
    repr_fields = ("priority",)

    def __init__(self, priority):
        """
        Filter and select the best matching name of a given type

        :param priority:
            A prioritized list of (name_type, name_language) tuples.
        """
        name_types = _check_constants(
            [t[0] for t in priority],
            Constants._EntityNameCode,
            "name",
            unique=False,
        )
        lang_types = _check_constants(
            [t[1] for t in priority],
            Constants._LanguageCode,
            "language",
            unique=False,
        )
        priority = self.priority = tuple(zip(name_types, lang_types))
        self._filter = set((int(name), int(lang)) for name, lang in priority)
        self.pri_key = make_priority_lookup([(int(name), int(lang))
                                             for name, lang in priority])

    def _get_key(self, name_data):
        return (int(name_data['name_variant']),
                int(name_data['name_language']))

    def __call__(self, name_list):
        matching_types = [
            name_data
            for name_data in name_list
            if self._get_key(name_data) in self._filter
        ]
        return sorted(matching_types,
                      key=lambda d: self.pri_key(self._get_key(d)))


class NameGetter(reprutils.ReprFieldMixin):
    """ Select matching names from cache, according to a given selector. """
    repr_id = False
    repr_module = False
    repr_fields = ("cache", "selector")

    def __init__(self, cache, selector):
        """
        :param NameCache cache:
            A cache to look up names from

        :param NameSelector selector:
            A selector to filter and prioritize names
        """
        self.cache = cache
        self.selector = selector

    def get_names(self, entity_id):
        names = self.cache.get(entity_id) or []
        for result in self.selector(names):
            name = result['name'].strip()
            yield (
                result['name_variant'],
                result['name_language'],
                name,
            )


def _group_tuple(iterable, key=0):
    group_order = []
    groups = {}
    for t in iterable:
        group_id = t[key]
        group_item = t[0:key] + t[key+1:]
        if group_id not in group_order:
            group_order.append(group_id)
        if group_id not in groups:
            groups[group_id] = []
        groups[group_id].append(group_item)

    for group_id in group_order:
        yield group_id, groups[group_id]


def group_names_by_type(iterable):
    """
    Group names by name type.

    Group the output from NameGetter by name type.

    >>> list(group_names_by_type([
    ...     ("acronym", "en", "foo"),
    ...     ("acronym", "nb", "bar"),
    ...     ("short", "en", "baz"),
    ... ]))
    [("acronym", [("en", "foo"), ("nb", "bar")]), ("short", [("en", "baz")])]

    """
    return _group_tuple(iterable, 0)


def group_names_by_language(iterable):
    """
    Group names by name language.

    Group the output from NameGetter by language.
    """
    return _group_tuple(iterable, 1)
