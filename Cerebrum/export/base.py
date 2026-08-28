# -*- coding: utf-8 -*-
#
# Copyright 2019-2026 University of Oslo, Norway
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
Base classes for export utils.

This module provides base classes for fetching and caching entity data. Actual
lookups are implemented in separate modules.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


MISSING = object()
"""
A lookup *miss* singleton object.

This object is returned as a sentinel value in :meth:`EntityFetcher.get_one`,
to indicate that no match exists for this key.
"""


class EntityFetcher(object):
    """
    Abstract database accessor for a specific type of entity data.

    Fetches data for either a single entity or all entities, according to a
    pre-determined set of parameters.
    """

    def get_one(self, entity_id):
        """
        Get the relevant data for a single given entity.

        If no data exists, a special :data:`.MISSING` sentinel value is
        returned.

        The return data format for *hits* is unspecified, and up to each
        individual fetcher subclass to define.

        :param int entity_id: The entity to look up data for
        :returns:
            The matching data on hits, or the special
            :data:`.MISSING` sentinel value on misses.
        """
        raise NotImplementedError("%r does not implement get_one()" %
                                  repr(type(self)))

    def get_all(self):
        """
        Get the relevant data for all matching entities.

        :rtype: dict[int, object]
        :returns:
            All matching data in a mapping.

            The key is the entity id, and the value is the same object that
            :meth:`.get_one` returns for that entity.

            The dict only includes *hits* - it does not include entries for
            entities that returns a *miss* in :meth:`.get_one`.
        """
        raise NotImplementedError("%r does not implement get_all()" %
                                  repr(type(self)))


class EntityCache(object):
    """
    Fetch and cache data on entities.

    This is a generic cache for a :class:`.EntityFetcher`.  To initialize and
    use the generic cache:
    ::

        fetcher = EntityFetcher()  # example only - a fetcher *subclass*
        cache = EntityCache(fetcher)

    Caching behaviour:  Data can be explicitly cached up-front for everyone,
    or for a given entity, or not at all:
    ::

        # optionally cache a given entity
        cache.update_one(entity_id)

        # optionally cache all entities
        cache.update_all()

    When looking up values, only keys that has not been previsouly looked up
    will result in a database query - the cache remembers all previous hits and
    misses.  To look up values:
    ::

        # item lookup - will raise KeyError on miss:
        data = cache[entity_id]

        # item lookup with a default/fallback value on miss:
        data = cache.get(entity_id, default=None)


    .. important::
       Caching should not be used across multiple transactions without a
       *reset*.

    """
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.reset()

    def reset(self):
        """ Reset the cache. """
        self.missing = set()
        self.found = {}
        self.cached_all = False

    def update_all(self):
        self.missing = set()
        self.found = self.fetcher.get_all()
        self.cached_all = True

    def update_one(self, entity_id):
        result = self.fetcher.get_one(entity_id)
        if result is MISSING:
            self.missing.add(entity_id)
            self.found.pop(entity_id, None)
        else:
            self.missing.discard(entity_id)
            self.found[entity_id] = result

    def __getitem__(self, entity_id):
        miss = KeyError(repr(entity_id))
        if entity_id not in self.found:
            if self.cached_all:
                raise miss
            if entity_id in self.missing:
                raise miss
            self.update_one(entity_id)

        if entity_id in self.found:
            return self.found[entity_id]
        raise miss

    def get(self, entity_id, default=None):
        try:
            return self[entity_id]
        except KeyError:
            return default
