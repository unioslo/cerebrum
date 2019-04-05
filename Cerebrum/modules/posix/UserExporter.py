#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2019 University of Oslo, Norway
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
Cache utilities for exporting posix users.

TODO: Maybe rename this module to user_caches or similar?
"""
import logging

import six

from Cerebrum.Utils import Factory, make_timer

logger = logging.getLogger(__name__)


def make_clock_time(logger_obj):
    def clock_time_decorator(func):
        def wrapper(*args, **kwargs):
            timer = make_timer(logger_obj, 'Starting %s...' % func.__name__)
            result = func(*args, **kwargs)
            timer('... done %s' % func.__name__)
            return result
        return wrapper
    return clock_time_decorator


clock_time = make_clock_time(logger)


class OwnerResolver(object):
    """
    Get full name of an account owner
    """

    def __init__(self, db):
        self.co = Factory.get('Constants')(db)
        self.account = Factory.get('Account')(db)
        self.person = Factory.get('Person')(db)

    @clock_time
    def make_owner_cache(self):
        cache = dict()
        for row in self.account.search():
            cache[row['account_id']] = row['owner_id']
        self.owner_cache = cache
        return cache

    @clock_time
    def make_name_cache(self):
        # TODO: Replace with future pe.list_names()?
        cache = dict()
        for row in self.person.search_person_names(
                name_variant=self.co.name_full,
                source_system=self.co.system_cached):
            cache[row['person_id']] = row['name']
        self.name_cache = cache
        return cache

    def get_owner_id(self, account_id):
        if not hasattr(self, 'owner_cache'):
            # TODO: Implement lazy lookups?
            raise RuntimeError(
                'no owner_cache, did you forget to make_owner_cache()?')
        return self.owner_cache.get(account_id)

    def get_name(self, account_id):
        if not hasattr(self, 'name_cache'):
            # TODO: Implement lazy lookups?
            raise RuntimeError(
                'no name_cache, did you forget to make_name_cache()?')
        owner_id = self.get_owner_id(account_id)
        if owner_id is None:
            return None
        else:
            return self.name_cache.get(owner_id)


class HomedirResolver(object):
    """
    Resolve account homedirs for a given spread.

    TODO: The data model for homedirs is horrible, and the queries are not
          really tailored for the lookups that are done in practice.
    """

    def __init__(self, db, spread):
        if not spread:
            raise ValueError("Cannot look up homedirs without spread")
        self.spread = spread
        self.co = Factory.get('Constants')(db)
        self.account = Factory.get('Account')(db)
        self.disk = Factory.get('Disk')(db)

    @clock_time
    def make_uname_cache(self):
        """
        Cache homedirs upfront.
        """
        cache = dict()
        for row in self.account.list_account_home(home_spread=self.spread):
            cache[row['account_id']] = dict(row)
        self.home_cache = cache
        return cache

    @clock_time
    def make_home_cache(self):
        """
        Cache homedirs upfront.
        """
        cache = dict()
        for row in self.account.list_account_home(home_spread=self.spread):
            cache[row['account_id']] = dict(row)
        self.home_cache = cache
        return cache

    def get_homedir(self, account_id, allow_no_disk=False):
        if not hasattr(self, 'home_cache'):
            # TODO: Implement lazy lookups
            raise RuntimeError('No cache')
        entry = self.home_cache.get(account_id, None)
        if not entry:
            return None
        if entry['disk_id'] is None and not allow_no_disk:
            return None
        return self.account.resolve_homedir(
            account_name=entry['entity_name'],
            disk_path=entry['path'],
            home=entry['home'],
        )


class UserExporter(object):

    def __init__(self, db):
        self.db = db
        self.co = Factory.get('Constants')(self.db)
        self.posix_user = Factory.get('PosixUser')(self.db)
        self.posix_group = Factory.get('PosixGroup')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.disk = Factory.get('Disk')(self.db)

    @clock_time
    def make_quarantine_cache(self, spread):
        quarantines = self.posix_user.list_entity_quarantines(
            entity_types=self.co.entity_account,
            spreads=spread,
            only_active=True
        )
        quarantine_cache = {}
        for row in quarantines:
            ent_id = row['entity_id']
            if ent_id in quarantine_cache:
                quarantine_cache[ent_id].append(row['quarantine_type'])
            else:
                quarantine_cache[ent_id] = [row['quarantine_type']]
        return quarantine_cache

    @clock_time
    def shell_codes(self):
        def _iter_shell_map():
            for c in self.co.fetch_constants(self.co.PosixShell):
                if not c.description:
                    logger.warn('No path for shell %s', repr(c))
                    continue
                yield int(c), six.text_type(c.description)
        return dict(_iter_shell_map())

    @clock_time
    def make_posix_gid_cache(self):
        group_id2posix_gid = {}
        for row in self.posix_group.list_posix_groups():
            group_id2posix_gid[row['group_id']] = row['posix_gid']
        return group_id2posix_gid

    @clock_time
    def make_fullname_cache(self):
        names = self.person.search_person_names(
            name_variant=self.co.name_full,
            source_system=self.co.system_cached
        )

        person2fullname = {}
        for row in names:
            person2fullname[row['person_id']] = row['name']
        return person2fullname

    @clock_time
    def make_auth_cache(self, spread, auth_method):
        accounts = self.posix_user.list_account_authentication(
            spread=spread,
            auth_type=auth_method
        )

        account2auth_data = {}
        for row in accounts:
            account2auth_data[row['account_id']] = (
                row['entity_name'],
                row['auth_data'],
            )
        return account2auth_data

    @clock_time
    def make_home_cache(self):
        person2fullname = self.make_fullname_cache()
        homes = self.posix_user.list_account_home(include_nohome=True)
        home_cache = {}
        for row in homes:
            entry = dict(row)
            entry['fullname'] = person2fullname.get(row['owner_id'], None)
            home_cache.setdefault(row['account_id'], []).append(entry)
            home_cache[row['account_id'], row['spread']] = entry
        return home_cache

    @clock_time
    def make_disk_cache(self, spread):
        disk_cache = {}
        for row in self.disk.list(spread=spread):
            disk_cache[row['disk_id']] = dict(row)
        return disk_cache
