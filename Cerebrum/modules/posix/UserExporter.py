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

import six
import logging

from Cerebrum.Utils import Factory, make_timer

logger = logging.getLogger(__name__)


def clock_time(func):
    def wrapper(*args, **kwargs):
        timer = make_timer(logger, 'Starting %s...' % func.__name__)
        result = func(*args, **kwargs)
        timer('... done %s' % func.__name__)
        return result
    return wrapper


class UserExporter(object):
    def __init__(self, db):
        self.db = db
        self.co = Factory.get('Constants')(self.db)
        self.posix_user = Factory.get('PosixUser')(self.db)
        self.posix_group = Factory.get('PosixGroup')(self.db)
        self.person = Factory.get('Person')(self.db)

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
    def make_shells_cache(self):
        shells = dict(
            (int(c), six.text_type(c)) for c in
            self.co.fetch_constants(self.co.PosixShell)
        )
        return shells

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
            home_cache[row['account_id']] = (
                row['home'],
                row['path'],
                row['owner_id'],
                person2fullname.get(row['owner_id'], None),
            )
        return home_cache
