#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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

"""Group expansion functions for Exchange."""

from __future__ import unicode_literals

from six import text_type

from Cerebrum.Utils import Factory
from Cerebrum import Errors

from functools import partial


def destination_criterion(db, group_spread):
    return partial(for_exchange, db, group_spread=group_spread)


def member_criterion(db, account_spread):
    return partial(for_exchange, db, account_spread=account_spread)


def remove_operations(db, co, member, dest, group_spread, account_spread):
    """Generate a map of removal operations."""

    # Search downwards, locate candidates for removal
    if member.entity_type == co.entity_person:
        primary_account = get_primary_account(member)
        to_rem = ([(primary_account.entity_id,
                    primary_account.account_name)] if
                  primary_account else [])
    elif member.entity_type == co.entity_account:
        to_rem = [(member.entity_id, member.account_name)]
    elif member.entity_type == co.entity_group:
        to_rem = get_children(db, member)

        to_rem = criteria_sieve(to_rem, member_criterion(db, account_spread))
    else:
        return {}

    # Search updwards, locate group-candidates to remove members from
    destination_groups = dict(map(lambda (gid, gname):
                                  ((gid, gname), get_children(
                                      db, get_entity(db, gid)),),
                              get_destination_groups(dest, group_spread)))

    destination_groups = dict(map(lambda x: (x, destination_groups[x]),
                                  criteria_sieve(destination_groups.keys(),
                                                 destination_criterion(
                                                     db, group_spread))))

    # Calculate if members should be removed from group-candidates or not
    if destination_groups:
        return dict(map(lambda (k, v): (k, filter(lambda e: e not in v,
                                                  to_rem)),
                        destination_groups.items()))
    else:
        {}


def add_operations(db, co, member, dest, group_spread, account_spread):
    """Generate a map of add operations."""
    if dest:
        destination_groups = get_destination_groups(dest, group_spread)
    else:
        destination_groups = []
    if member.entity_type == co.entity_group:
        to_add = get_children(db, member)

    elif member.entity_type == co.entity_person:
        primary_account = get_primary_account(member)
        to_add = ([(primary_account.entity_id,
                    primary_account.account_name)] if
                  primary_account else [])
    elif member.entity_type == co.entity_account:
        to_add = [(member.entity_id, member.account_name)]
    else:
        to_add = []
    return (criteria_sieve(destination_groups,
                           destination_criterion(db, group_spread)),
            criteria_sieve(to_add,
                           member_criterion(db, account_spread)))


def get_destination_groups(gr, group_spread=None):
    """Collect parent groups."""
    return (map(lambda x: (x['group_id'], x['name']),
                gr.search(member_id=gr.entity_id,
                          indirect_members=True,
                          spread=group_spread)) +
            [(gr.entity_id, gr.group_name)])


def get_children(db, ent):
    """Collect children of groups.

    Converts persons to primary accounts."""
    def convert(x):
        if x['member_type'] == ent.const.entity_person:
            primary_account = get_primary_account(get_entity(db,
                                                             x['member_id']))
            if primary_account:
                return (primary_account.entity_id,
                        primary_account.account_name)
            else:
                return (None, None)
        else:
            return (x['member_id'], get_entity_name(db, x['member_id']))
    return set(filter(lambda (x, y): x and y,
                      map(lambda x: convert(x),
                          ent.search_members(group_id=ent.entity_id,
                                             indirect_members=True))))


def get_primary_account(person):
    """Collect a persons primary account object."""
    return get_entity(person._db, person.get_primary_account())


def get_entity(db, entity_id):
    """Get an instantiated object from entity id."""
    entity = Factory.get('Entity')(db)
    try:
        return entity.get_subclassed_object(id=entity_id)
    except (Errors.NotFoundError, TypeError, ValueError):
        return None


def get_entity_name(db, entity_id):
    """Fetch the entity name associated with an id."""
    try:
        ent = get_entity(db, entity_id)
        from cereconf import ENTITY_TYPE_NAMESPACE
        namespace = ent.const.ValueDomain(
            ENTITY_TYPE_NAMESPACE.get(
                text_type(ent.const.EntityType(ent.entity_type)), None))
        return ent.get_name(namespace)
    except (AttributeError, TypeError, Errors.NotFoundError):
        return None


def for_exchange(db, x, group_spread=None, account_spread=None):
    """Selector-function for exchange."""
    e = get_entity(db, x[0])
    if e.entity_type == e.const.entity_group:
        return e.has_spread(group_spread)
    elif e.entity_type == e.const.entity_account:
        return e.has_spread(account_spread)
    else:
        return False


def criteria_sieve(l, criteria):
    """Filter l with criteria."""
    return filter(lambda x: criteria(x), l)
