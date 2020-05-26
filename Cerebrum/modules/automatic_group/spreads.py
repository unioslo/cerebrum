# coding: utf-8
#
# Copyright 2020 University of Oslo, Norway
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
from __future__ import unicode_literals
import collections
import six

RULES = {
    'adm-leder-':
        (('group@ldap', 'AD_group', 'NIS_ng@uio'),
         {'name': 'adm-leder-*',
          'group_type': 'affiliation-group',
          'filter_expired': True}),
    'meta-adm-leder-':
        (('group@ldap', 'AD_group', 'NIS_ng@uio'),
         {'name': 'meta-adm-leder-*',
          'group_type': 'affiliation-group',
          'filter_expired': True})
}


def load_rules(co, names):
    rules = {}
    for name in names:
        spreads, filters = RULES[name]
        spreads = set(co.Spread(s) for s in spreads)
        if 'group_type' in filters:
            if isinstance(filters['group_type'], six.text_type):
                filters['group_type'] = co.GroupType(filters['group_type'])
            elif isinstance(filters['group_type'], collections.Iterable):
                filters['group_type'] = tuple(
                    co.GroupType(gt) for gt in filters['group_type']
                )
        rules[name] = (spreads, filters)
    return rules


def assert_spreads(gr, group_id, needed_spreads):
    gr.clear()
    gr.find(group_id)
    current_spreads = set(s['spread'] for s in gr.get_spread())
    for spread in needed_spreads.difference(current_spreads):
        gr.add_spread(spread)


def select_group_ids(gr, filters):
    return (r['group_id'] for r in gr.search(fetchall=False, **filters))
