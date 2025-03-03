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
Utilities for building group memberships derived from other group memberships.

Examples:

- group intersections
- group unions
- flattened groups from group hierarchies
- person memberships to primary account memberships
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)


def get_current_members(group):
    """
    Get current members of a *group*.

    Expired entities are included.  Use this to find the current membership
    state of a group.  This is typically used to calculate required membership
    changes.

    :type group: Cerebrum.Group.Group
    :param group: The group to list members from

    :returns set: A set of current member entity-ids
    """
    return set(
        m['member_id']
        for m in group.search_members(group_id=int(group.entity_id),
                                      indirect_members=False,
                                      member_filter_expired=False)
    )


def find_effective_members(group):
    """
    Recursively list entities that are considered active members of a *group*.

    Expired entities are excluded.  This is typically used to build a
    permission cache from a permission group, or to simply flatten a group
    hierarchy.

    :type group: Cerebrum.Group.Group
    :param group: The group to list members from

    :returns set:
        Returns a set of (entity_id, entity_type) tuples.

        By including `entity_type`, callers can easily do some filtering to
        only get the member types that they want.  Note that groups are always
        omitted, as their members are included due to the recursive nature of
        this function.
    """
    return set(
        (r['member_id'], r['member_type'])
        for r in group.search_members(
            group_id=int(group.entity_id),
            indirect_members=True,
            member_filter_expired=True,
        )
        # don't need the group ids, as we're searching recursively
        if r['member_type'] != group.const.entity_group
    )


def get_member_ids(iterable):
    """
    Get a set of entity-id values from an iterable of member tuples.

    This is typically done to get a set of entity ids from the result of e.g.
    :func:`.find_members`.

    :param iterable: An iterable of (entity-id, entity-type) tuples.

    :returns set: a set of entity ids
    """
    return set(entity_id for entity_id, entity_type in iterable)


def set_group_members(group, member_ids):
    """
    Sync group members for a given group.

    This simply sets the memberships of a given *group* to a set of *member_id*
    values.

    :type group: Cerebrum.Group.Group
    :param group: The group to update memberships for

    :type member_ids: set
    :param member_ids: A set of member ids for the group.
    """
    group_repr = "%s (%d)" % (group.group_name, group.entity_id)
    wanted = set(member_ids)
    current = get_current_members(group)
    logger.debug("%s has %d current members",
                 group_repr, len(current))

    to_add = wanted - current
    to_remove = current - wanted

    logger.debug("Updating %s members: adding %d, removing %d",
                 group_repr, len(to_add), len(to_remove))
    for member_id in to_add:
        group.add_member(member_id)
        logger.info('Added member id=%d to %s', member_id, group_repr)

    for member_id in to_remove:
        group.remove_member(member_id)
        logger.info('Removed member id=%d from group %s',
                    member_id, group_repr)


def transform_noop(value):
    """
    Identity function - return value as-is.

    Useful as a replacement for e.g. :meth:`.AccountOwnerCache.only_persons`
    when no re-mapping is needed.
    """
    return value


class AccountOwnerCache(object):
    """
    Utility to re-map account-id to person-id and vice versa.

    This helper is intended to filter the results of :func:`.get_members`.
    """
    def __init__(self, db):
        self.db = db
        self.const = Factory.get("Constants")(db)

    #
    # Caches
    #
    # TODO: Improve and move these using Cerebrum.export?
    #

    def _cache_primary_accounts(self):
        ac = Factory.get('Account')(self.db)
        person_type = int(self.const.entity_person)
        account_type = int(self.const.entity_account)
        self._person_to_pri = {}
        self._pri_to_person = {}
        logger.debug("caching primary accounts...")
        for row in ac.list_accounts_by_type(primary_only=True):
            person_t = (row['person_id'], person_type)
            account_t = (row['account_id'], account_type)
            self._person_to_pri[person_t] = account_t
            self._pri_to_person[account_t] = person_t
        logger.info("Found %d primary accounts", len(self._pri_to_person))

    @property
    def person_to_primary(self):
        """ owner-id to primary account-id for personal accounts. """
        if not hasattr(self, "_person_to_pri"):
            self._cache_primary_accounts()
        return self._person_to_pri

    @property
    def primary_to_person(self):
        """ primary account-id to owner-id for personal accounts. """
        if not hasattr(self, "_pri_to_person"):
            self._cache_primary_accounts()
        return self._pri_to_person

    def _cache_accounts(self):
        ac = Factory.get('Account')(self.db)
        person_type = int(self.const.entity_person)
        account_type = int(self.const.entity_account)
        accounts = list(ac.search())
        self._account_to_owner = {}
        self._account_to_person = {}
        self._owner_to_accounts = {}
        logger.debug("caching all active accounts...")
        for row in accounts:
            account_t = (row['account_id'], account_type)
            owner_t = (row['owner_id'], row['owner_type'])
            if row['owner_type'] == person_type:
                self._account_to_person[account_t] = owner_t
            self._account_to_owner[account_t] = owner_t
            owner = self._owner_to_accounts.setdefault(owner_t, set())
            owner.add(account_t)
        logger.info("Found %d active accounts (%d personal accounts)",
                    len(self._account_to_owner), len(self._account_to_person))

    @property
    def account_owners(self):
        """ account-id to owner-id (personal and non-personal accounts). """
        if not hasattr(self, "_account_to_owner"):
            self._cache_accounts()
        return self._account_to_owner

    @property
    def account_to_person(self):
        """ account-id to owner-id (only personal accounts). """
        if not hasattr(self, "_account_to_person"):
            self._cache_accounts()
        return self._account_to_person

    @property
    def owner_to_accounts(self):
        """ owner-id to account-id (personal and non-personal accounts). """
        if not hasattr(self, "_owner_to_accounts"):
            self._cache_accounts()
        return self._owner_to_accounts

    def _cache_account_quarantines(self):
        ac = Factory.get('Account')(self.db)
        account_type = int(ac.const.entity_account)
        self._account_to_quarantines = {}
        logger.debug("caching account quarantines...")
        for row in ac.list_entity_quarantines(entity_types=account_type,
                                              only_active=True):
            account_t = (row['entity_id'], account_type)
            quarantines = self._account_to_quarantines.setdefault(account_t,
                                                                  set())
            quarantines.add(row['quarantine_type'])

        logger.info("Found %d quarantined accounts",
                    len(self._account_to_quarantines))

    @property
    def account_quarantines(self):
        """ account-id to list of (active) quarantine types. """
        if not hasattr(self, "_account_to_quarantines"):
            self._cache_account_quarantines()
        return self._account_to_quarantines

    #
    # Filtering functions
    #

    def only_primary_accounts(self, iterable):
        """
        Map persons and personal accounts to primary account.

        This helper tries really hard to map members to a primary account:

        - Person members are mapped to their primary account
        - Personal accounts are mapped to the primary account of their owner
        """
        for member_t in iterable:
            member_id, member_type = member_t

            if member_t in self.primary_to_person:
                # already a primary account
                yield member_t
                continue

            # May be a non-primary personal account - try mapping to owner,
            # so we can look up the primary account
            # This may not be what we want in all cases - if a non-primary
            # personal account is a member of a given group, that doesn't
            # neccessarily mean that the primary account *should* be a member.
            if member_t in self.account_owners:
                member_t = self.account_owners[member_t]

            # may be a person - look up primary account
            if member_t in self.person_to_primary:
                yield self.person_to_primary[member_t]
                continue

            logger.info("omitting %s - not mappable to a primary account",
                        member_t)

    def only_accounts(self, iterable, all_accounts=False):
        """
        Map persons to their primary account (or all accounts).

        This helper only yield account entities.  If a person is encountered,
        their primary account is used in stead.  If *all_accounts* is set, all
        then all accounts that belongs to the person is included.
        """
        const = Factory.get("Constants")(self.db)
        person_type = int(const.entity_person)
        account_type = int(const.entity_account)

        for member_t in iterable:
            member_id, member_type = member_t

            if member_type == account_type:
                # already an account
                yield member_t
                continue

            if member_type == person_type:
                if all_accounts and member_t in self.owner_to_accounts:
                    # yield all owned accounts
                    for acc_t in self.owner_to_accounts[member_t]:
                        yield acc_t
                    continue

                if not all_accounts and member_t in self.person_to_primary:
                    # yield primary account, if it exists
                    yield self.person_to_primary[member_t]
                    continue

            logger.info("omitting %s - not mappable to an account", member_t)

    def only_persons(self, iterable):
        const = Factory.get("Constants")(self.db)
        person_type = int(const.entity_person)

        for member_t in iterable:
            member_id, member_type = member_t

            if member_type == person_type:
                # Already a person
                yield member_t
                continue

            if member_t in self.account_to_person:
                # Get personal account owner
                yield self.account_to_person[member_t]
                continue

            logger.info("omitting %s - not a person or personal account",
                        member_t)

    def exclude_quarantined(self, iterable, exclude_persons=False):
        """
        Filter out member tuples that aren't quarantined *accounts*.

        :param iterable: an iterable of (entity-id, entity-type) tuples
        :param bool exclude_persons:
            Also exclude persons when their primary account is quarantined
        """
        for member_t in iterable:
            member_id, member_type = member_t

            if member_t in self.account_quarantines:
                # quarantined account
                continue

            if exclude_persons and member_t in self.person_to_primary:
                # use primary account for personal members
                pri_t = self.person_to_primary[member_t]
                if pri_t in self.account_quarantines:
                    # quarantined primary account
                    continue

            yield member_t


if __name__ == "__main__":
    def _main():
        logging.basicConfig(level=logging.DEBUG)
        db = Factory.get("Database")()
        aoc = AccountOwnerCache(db)
        aoc._cache_accounts()
        aoc._cache_primary_accounts()
        aoc._cache_account_quarantines()

    _main()
