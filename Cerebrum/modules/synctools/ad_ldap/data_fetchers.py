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

from Cerebrum import Errors, Utils
from Cerebrum.modules.synctools import base_data_fetchers as df


def get_ad_ldap_acc_values(client, username):
    return client.fetch_data(client.config.users_dn,
                             client.scope_subtree,
                             '(cn={})'.format(username))


def get_all_ad_ldap_acc_values(client):
    return client.fetch_data(client.config.users_dn,
                             client.scope_subtree,
                             '(objectClass=user)')


def get_all_ad_ldap_grp_values(client):
    return client.fetch_data(client.config.groups_dn,
                             client.scope_subtree,
                             '(objectClass=group)')


def get_person_names(db, person_id):
    co = Utils.Factory.get('Constants')(db)
    pe = Utils.Factory.get('Person')(db)
    try:
        pe.find(person_id)
    except Errors.NotFoundError:
        return None
    return {'first_name': pe.get_name(co.system_cached,
                                      co.name_first),
            'last_name': pe.get_name(co.system_cached,
                                     co.name_last)}


def get_all_persons_names(db):
    """Returns a dict person_id -> first_name & last_name using
    system_cached as source_system."""
    co = Utils.Factory.get('Constants')(db)
    pe = Utils.Factory.get('Person')(db)
    names = {}
    for row in pe.search_person_names(
            name_variant=[co.name_first,
                          co.name_last],
            source_system=co.system_cached):
        names.setdefault(int(row['person_id']), {})
        if int(co.name_first) == int(row['name_variant']):
            names[int(row['person_id'])]['first_name'] = row['name']
        elif int(co.name_last) == int(row['name_variant']):
            names[int(row['person_id'])]['last_name'] = row['name']
    return names


def get_all_posix_accounts_data(db, acc_spread, grp_spread):
    account_data = df.get_all_posix_accounts_rows(db, spread=acc_spread)
    grp_gids = df.get_all_posix_group_gids(db)
    grp_names = df.get_all_posix_groups(db,
                                        spread=grp_spread,
                                        keys=['name'])
    posix_data = {}
    for acc_id, acc_data in account_data.items():
        pg_gid = grp_gids[acc_data['gid']]
        posix_group_name = None
        if grp_names.get(acc_data['gid']) is not None:
            posix_group_name = grp_names[acc_data['gid']]['name']
        posix_data[acc_id] = dict(acc_data)
        posix_data[acc_id].update(
            {'posix_gid': pg_gid.get('posix_gid') or '',
             'posix_group_name': posix_group_name or ''}
        )
    return posix_data


def get_account_data(db, account_id, spread):
    ac = Utils.Factory.get('Account')(db)
    try:
        ac.find(account_id)
    except Errors.NotFoundError:
        return None
    if spread and not ac.has_spread(spread):
        return None
    return {'owner_id': ac.owner_id,
            'account_id': ac.entity_id,
            'name': ac.account_name}


def get_posix_account_data(db, account_id):
    pg = Utils.Factory.get('PosixGroup')(db)
    pu = Utils.Factory.get('PosixUser')(db)
    try:
        pu.find(account_id)
        pg.find(pu.gid_id)
        return {'posix_uid': pu.posix_uid,
                'gecos': pu.gecos,
                'posix_gid': pg.posix_gid,
                'posix_group_name': pg.group_name}
    except Errors.NotFoundError:
        return None


def get_all_accounts_homedir_data(db, acc_spread):
    ac = Utils.Factory.get('Account')(db)
    host_data = df.get_all_host_rows(db)
    return {
        home['account_id']: {'home_host': host_data[home['host_id']]['name'],
                             'home_path': home['path']}
        for home in ac.list_account_home(
            account_spread=acc_spread
        )
        if home['host_id'] and home['host_id'] in host_data
    }


def get_homedir_data(db, account_id):
    ac = Utils.Factory.get('Account')(db)
    di = Utils.Factory.get('Disk')(db)
    ho = Utils.Factory.get('Host')(db)
    try:
        ac.find(account_id)
    except Errors.NotFoundError:
        return None
    homes = ac.get_homes()
    if not homes:
        return None
    home = None
    for h in homes:
        if h['disk_id']:
            home = h
            break
    if home is None:
        return None
    di.find(home['disk_id'])
    ho.find(di.host_id)
    return {'home_path': ac.get_homepath(home['spread']),
            'host_name': ho.name}


def combine_crb_acc_values(acc_data,
                           name_data,
                           quarantine_action,
                           posix_data,
                           mail,
                           home_dir_data):
    crb_acc_values = {'disabled': False,
                      'account_id': acc_data['account_id'],
                      'mail': mail or None}
    crb_acc_values.update(acc_data)
    if posix_data:
        crb_acc_values.update(posix_data)
    if name_data:
        crb_acc_values.update(name_data)
    if quarantine_action:
        if quarantine_action == 'lock':
            crb_acc_values.update({'disabled': True})
        elif quarantine_action == 'skip':
            crb_acc_values.update({'skip': True})
    if home_dir_data:
        crb_acc_values.update(home_dir_data)
    return crb_acc_values


def get_crb_account_data(db, account_id, spread):
    acc_data = get_account_data(db, account_id, spread)
    return combine_crb_acc_values(
        acc_data=acc_data,
        name_data=get_person_names(db, acc_data['owner_id']),
        quarantine_action=df.get_accounts_quarantine_data(
            db,
            account_ids=[account_id]),
        posix_data=get_posix_account_data(db, account_id),
        mail=df.get_email_addr(db, account_id),
        home_dir_data=get_homedir_data(db, account_id),
    )


def get_all_crb_accounts_data(db, ad_acc_spread, ad_grp_spread):
    ac = Utils.Factory.get('Account')(db)
    accounts_data = df.get_all_account_rows(db,
                                            keys=['owner_id',
                                                  'account_id',
                                                  'name'],
                                            spread=ad_acc_spread)
    quarantine_data = df.get_accounts_quarantine_data(
        db,
        account_ids=accounts_data.keys()
    )
    name_data = get_all_persons_names(db)
    mail_data = ac.getdict_uname2mailaddr(filter_expired=True,
                                          primary_only=True)
    posix_data = get_all_posix_accounts_data(db, ad_acc_spread, ad_grp_spread)
    accounts_homedir_data = get_all_accounts_homedir_data(db, ad_acc_spread)

    return [combine_crb_acc_values(
        acc_data=acc_data,
        name_data=name_data.get(acc_data['owner_id']),
        quarantine_action=quarantine_data.get(acc_id),
        posix_data=posix_data.get(acc_id),
        mail=mail_data.get(acc_data['name']),
        home_dir_data=accounts_homedir_data.get(acc_id))
        for acc_id, acc_data in accounts_data.items()
        if not acc_data.get('skip') is True]


def get_all_groups_values(db, group_spread, account_spread):
    grp_dict = df.get_all_groups_data(db,
                                      spread=group_spread,
                                      keys=['name',
                                            'description',
                                            'group_id'])
    gid_dict = df.get_all_posix_group_gids(db)
    combined_dicts = {}
    members = df.get_all_group_members(db,
                                       spread=group_spread,
                                       member_spread=account_spread)
    for grp_id, grp_data in grp_dict.items():
        combined_dicts[grp_id] = grp_data
        if grp_id in members:
            combined_dicts[grp_id].update({'member': members[grp_id]})
        if grp_id in gid_dict:
            combined_dicts[grp_id].update(gid_dict[grp_id])
    return combined_dicts
