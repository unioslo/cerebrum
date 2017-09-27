#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2017 University of Oslo, Norway
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
import cereconf
from Cerebrum import Errors
from Cerebrum.modules.synctools.data_fetcher import CerebrumDataFetcher


def merge(d1, d2):
    r = d1
    for k, v in d2.iteritems():
        if k not in r:
            r[k] = v
        if isinstance(r[k], list):
            r[k].extend(v)
        elif isinstance(r[k], dict):
            r[k] = merge(r[k], v)
    return r


class ADLDAPSyncGroupDataFetcher(CerebrumDataFetcher):
    def __init__(self, **kwargs):
        super(ADLDAPSyncGroupDataFetcher, self).__init__(**kwargs)
        self.group_spread = self.co.Spread(cereconf.AD_GROUP_SPREAD)
        self.account_spread = self.co.Spread(cereconf.AD_ACCOUNT_SPREAD)

    def get_all_groups(self, indirect_memberships=True):
        all_group_rows = self.get_all_groups_data(
            key_attr='name',
            keys=['name', 'description', 'group_id'],
            spread=self.group_spread)
        all_posix_group_rows = self.get_all_posix_group_rows(
                    key_attr='name',
                    keys=['posix_gid'],
                    spread=self.group_spread)

        groups = merge(all_group_rows, all_posix_group_rows)

        for k in groups:
            groups[k]['member'] = self.get_all_group_members(
                    groups[k]['group_id'],
                    key_attr='group_name',
                    keys=['member_name'],
                    spread=self.group_spread,
                    member_spread=[self.group_spread, self.account_spread],
                    indirect_memberships=indirect_memberships)
        return dict(map(lambda (k, v): (k, filter(lambda (k2, v2): k2 !=
                                                  'group_id', v.iteritems())),
                        groups))


class ADLDAPSyncDataFetcher(CerebrumDataFetcher):
    def __init__(self, **kwargs):
        super(ADLDAPSyncDataFetcher, self).__init__(**kwargs)
        self.account_spread = self.co.Spread(cereconf.AD_ACCOUNT_SPREAD)

    def get_person_basic_info(self, person_id):
        self.pe.clear()
        try:
            self.pe.find(person_id)
        except Errors.NotFoundError:
            return None
        return {'first_name': self.pe.get_name(self.co.system_cached,
                                               self.co.name_first),
                'last_name': self.pe.get_name(self.co.system_cached,
                                              self.co.name_last)}

    def get_all_persons_names(self):
        """Returns a dict person_id -> first_name & last_name using
        system_cached as source_system."""
        names = {}
        for row in self.pe.search_person_names(
                name_variant=[self.co.name_first,
                              self.co.name_last],
                source_system=self.co.system_cached):
            names.setdefault(int(row['person_id']), {})
            if int(self.co.name_first) == int(row['name_variant']):
                names[int(row['person_id'])]['first_name'] = row['name']
            elif int(self.co.name_last) == int(row['name_variant']):
                names[int(row['person_id'])]['last_name'] = row['name']

        return names

    def get_posix_group_rows(self):
        return self.get_all_posix_group_rows(spread=self.account_spread,
                                             keys=['name'])

    def get_host_data(self):
        return self.get_all_host_rows(keys=['name'])

    def get_posix_rows(self):
        return self.get_all_posix_accounts_rows(
            spread=self.account_spread,
            keys=['posix_uid',
                  'gid',
                  'gecos']
        )

    def get_all_posix_accounts_data(self):
        account_data = self.get_all_posix_accounts_rows(self.account_spread)
        grp_gids = self.get_all_posix_group_data()
        grp_names = self.get_all_posix_group_rows(self.account_spread,
                                                  keys=['name'])
        posix_data = {}
        for acc_id, acc_data in account_data.items():
            posix_data[acc_id] = dict(acc_data)
            posix_data[acc_id].update(
                {'posix_gid': grp_gids.get(acc_data['posix_group_id']['posix_gid']),
                 'posix_group_name': grp_names.get(acc_data['posix_group_id'])}
            )
        return posix_data

    def get_all_accounts_homedir_data(self, spread=None):
        host_data = self.get_all_host_rows()
        return {
            home['account_id']: {'home_host': host_data[home['host_id']['name']],
                                 'home_path': home['path']}
            for home in self.ac.list_account_home(
                account_spread=spread
            )
            if home['host_id'] and home['host_id'] in host_data
        }

    def get_account_data(self, account_id, spread=None):
        self.ac.clear()
        try:
            self.ac.find(account_id)
        except Errors.NotFoundError:
            return None
        if spread and not self.ac.has_spread(spread):
            return None
        return {'owner_id': self.ac.owner_id,
                'entity_id': account_id,
                'entity_type': 'account',
                'username': self.ac.account_name}

    def get_posix_data(self, account_id):
        self.pu.clear()
        self.pg.clear()
        try:
            self.pu.find(account_id)
            self.pg.find(self.pu.gid_id)
            return {'posix_uid': self.pu.posix_uid,
                    'gecos': self.pu.gecos,
                    'posix_gid': self.pg.posix_gid,
                    'posix_group_name': self.pg.group_name}
        except Errors.NotFoundError:
            return None

    def get_homedir_data(self, account_id):
        self.ac.clear()
        try:
            self.ac.find(account_id)
        except Errors.NotFoundError:
            return None
        homes = self.ac.get_homes()
        if not homes:
            return None
        home = None
        for h in homes:
            if h['disk_id']:
                home = h
                break
        if home is None:
            return None
        self.di.clear()
        self.di.find(home['disk_id'])
        self.ho.clear()
        self.ho.find(self.di.host_id)
        return {'home_path': self.ac.get_homepath(home['spread']),
                'host_name': self.ho.name}
