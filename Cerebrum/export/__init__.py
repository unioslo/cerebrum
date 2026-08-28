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
Batch export utilities.

A typical batch export usually looks something like:

1. Fetch and validate configuration and/or input parameters.
2. Build caches of all relevant data.
3. Select and format relevant data.

This module and its submodules add helpers for fetching, caching, selecting,
and formatting various entity data.  While mostly useful in batch exports,
some of these utilities can also be used for *generic* lookups.

The submodules only relate to core Cerebrum data.  Export utilities for
optional features should be implemented in the relevant
``Cerebrum.modules.<module>``.


Helper types
-------------
Some basic functionality can be expected in most export modules:

Fetcher
    The fetcher implements lookups for *one entity* or *all entities*.  It can
    be used as a standalone lookup, or it can be passed to a Cache for cached
    lookups.

    All fetchers should be subclasses of the abstract
    :class:`~base.EntityFetcher`.  Fetchers may be parametrized to only include
    results that match some criteria.

    The output from fetchers is usually *normalized* database rows.
    Normalization usually involves replacing constant values with
    constant objects, empty columns with ``None``, and so forth.

Cache
    The cache wraps a fetcher and ensures that a given entity only needs to be
    looked up once.

    It also provides functionality for caching entities up-front, which is
    useful in batch exports.

    A basic cache is implemented in :class:`~base.EntityCache`.  This cache
    should work with all fetchers that follow the implementation details from
    :class:`~base.EntityFetcher`.  This cache, and subclasses of this cache,
    should produce the same result as its *fetcher* for cache hits.

Selector (optional)
    Selectors typically work on fetcher output, and can be used to filter,
    prioritize and/or select a single match for multivalued fetcher results.

    This can be used to e.g. get a single result with *fallback* values.

    Some exports will need to fetch a given information type for multiple
    entity types.  In these exports, it can be useful to cache *all* values for
    *all* entities, and only select relevant results for a given entity type in
    a selector.

    No common Selector exists, as there is little in common between values from
    a given fetcher implementation.  Also, not every fetcher will return a
    multivalued result, or need additional filtering or ordering.

    It is noted here as it is a common feature in batch export modules.

Formatter (optional)
    The formatter is typically used to modify a single value from a fetcher or
    selector.

    No common Formatter exists, as there is little in common between fetcher or
    selector results.  It is noted here as it is a common feature in batch
    export modules.
"""
