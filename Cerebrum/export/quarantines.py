# -*- coding: utf-8 -*-
#
# Copyright 2025-2026 University of Oslo, Norway
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
Fetch, cache, and process quarantines.

This module provides helpers for fetching, caching, selecting and filtering
quarantines by quarantine state.  The cache is useful in any scenario where we
look up quarantines in a single read-only transaction.  The fetching and
selection functionality is useful for selecting and checking quarantines in any
scenario.

The typical use case for this module is to pre-fetch all (relevant) active
quarantines to use when filtering objects for export or reports.

Quarantine objects
-------------------
The quarantine cache finds and returns simplified and normalized quarantine
rows:
::

    {
        'entity_id': int,
        'quarantine_type': _QuarantineCode,
        'start_date': datetime.date,
        'end_date': datetime.date or None,
        'disable_until': datetime.date or None,
        'description': str or None,
    }

Note that ``create_date`` and ``creator_id`` are omitted, at least for now.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.Constants import (_EntityTypeCode, _QuarantineCode)
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.Utils import Factory
from Cerebrum.utils import date_compat
from Cerebrum.utils.descriptors import lazy_property

from . import base

logger = logging.getLogger(__name__)


def get_quarantines(co, values):
    """ Look up a sequence of _QuarantineCode values. """
    for value in values:
        yield co.get_constant(_QuarantineCode, value)


def get_entity_types(co, values):
    """ Look up a sequence of _EntityTypeCode values. """
    for value in values:
        yield co.get_constant(_EntityTypeCode, value)


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


class _QuarantineFetcher(base.EntityFetcher):
    """ Fetch quarantine data. """

    def __init__(self, db, quarantines, entity_types, only_active):
        self._db = db
        self._const = Factory.get("Constants")(db)
        self.quarantines = (
            None if quarantines is None
            else _check_constants(quarantines, _QuarantineCode, "quarantine")
        )
        self.entity_types = (
            None if entity_types is None
            else _check_constants(entity_types, _EntityTypeCode, "entity")
        )
        self.only_active = only_active

    @lazy_property
    def quarantine_map(self):
        return {int(c): c
                for c in self._const.fetch_constants(_QuarantineCode)}

    def _normalize_row(self, row):
        return {
            'entity_id': row['entity_id'],
            'quarantine_type': self.quarantine_map[row['quarantine_type']],
            'start_date': date_compat.get_date(row['start_date']),
            'end_date': date_compat.get_date(row['end_date']),
            'disable_until': date_compat.get_date(row['disable_until']),
            'description': row['description'],
        }

    def _get_results(self, **extra):
        eq = EntityQuarantine(self._db)
        for row in eq.list_entity_quarantines(
                entity_types=self.entity_types,
                quarantine_types=self.quarantines,
                only_active=self.only_active,
                **extra):
            data = self._normalize_row(row)
            yield (data['entity_id'], data['quarantine_type'], data)

    def get_one(self, entity_id):
        """ Fetch quarantine data for one entity. """
        entity_data = {}
        for _, q_type, q_data in self._get_results(
                entity_ids=int(entity_id)):
            entity_data[q_type] = q_data
        return entity_data or base.MISSING

    def get_all(self):
        """ Fetch quarantine data for all entities. """
        results = {}
        for entity_id, q_type, q_data in self._get_results():
            entity_data = results.setdefault(int(entity_id), {})
            entity_data[q_type] = q_data
        return results


class QuarantineCache(base.EntityCache):
    """
    Quarantine data cache.

    The cache can optionally limit results to specific quarantine types,
    quarantines for specific entity types, and/or only active quarantines.

    The cache returns matching `quarantine objects`_ as specified in the module
    docstring.
    """

    def __init__(self, db, quarantines=None, entity_types=None,
                 only_active=True):
        """
        :type quarantines: collection of _QuarantineCode, or None
        :type entity_types: collection of _EntityTypeCode, or None
        :type only_active: bool
        """
        fetcher = _QuarantineFetcher(db, quarantines, entity_types,
                                     only_active)
        super(QuarantineCache, self).__init__(fetcher)
