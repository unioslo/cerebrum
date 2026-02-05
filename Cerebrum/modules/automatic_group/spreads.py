# coding: utf-8
#
# Copyright 2020-2026 University of Oslo, Norway
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
Module for applying spreads to a given set of groups.

TODO
====
This module needs revision.  It was built for- and only used for *manager
groups* (see :mod:`Cerebrum.modules.no.uio.hr_import.leader_groups`).

The general idea here with *matching rules* and a list of spreads is OK, but
should probably be formalized a bit more (e.g. a better representation of the
rules).

The rules themselves should probably be moved to an appropriate location (e.g.
:mod:`Cerebrum.modules.no.uio.hr_import.leader_groups`).

Also, see the *TODOs* in :mod:`.structure`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import collections

import six

from . import manager_groups


RULES = {
    manager_groups.GROUP_NAME_PREFIX: (
        ('group@ldap', 'AD_group', 'NIS_ng@uio'),
        {
            'name': 'adm-leder-*',
            'group_type': 'affiliation-group',
            'filter_expired': True,
        },
    ),
    manager_groups.META_GROUP_NAME_PREFIX: (
        ('group@ldap', 'AD_group', 'NIS_ng@uio'),
        {
            'name': 'meta-adm-leder-*',
            'group_type': 'affiliation-group',
            'filter_expired': True,
        },
    ),
}


def load_rules(co, names):
    rules = {}
    for rule_name in names:
        raw_spreads, raw_filters = RULES[rule_name]
        spreads = set(
            co.get_constant(co.Spread, s)
            for s in raw_spreads,
        )
        filters = {
            'name': raw_filters['name'],
            'filter_expired': raw_filters['filter_expired'],
        }
        raw_group_type = raw_filters['group_type']
        if raw_group_type and 'group_type' in raw_filters:
            if isinstance(raw_group_type, six.text_type):
                filters['group_type'] = co.get_constant(raw_group_type,
                                                        co.GroupType)
            elif isinstance(filters['group_type'], collections.Iterable):
                filters['group_type'] = tuple(
                    co.get_constant(co.GroupType, gt)
                    for gt in raw_group_type
                )
        rules[rule_name] = (spreads, filters)
    return rules


def assert_spreads(gr, group_id, needed_spreads):
    gr.clear()
    gr.find(group_id)
    current_spreads = set(s['spread'] for s in gr.get_spread())
    for spread in needed_spreads.difference(current_spreads):
        gr.add_spread(spread)


def select_group_ids(gr, filters):
    return (r['group_id'] for r in gr.search(fetchall=False, **filters))
