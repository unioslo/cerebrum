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
import uuid


def format_ldap_data(ad_data, attrs):
    r = {}
    for data in ad_data:
        r[data[1]['cn'][0]] = {
            key: data[1].get(key, None)
            for key in attrs
        }
    return r


def format_ldap_acc_data(ad_data, attrs):
    extended_attrs = list(attrs)
    extended_attrs.extend(['userAccountControl', 'distinguishedName'])
    formatted_ad_data = format_ldap_data(ad_data, extended_attrs)
    formatted_acc_data = {}
    for username, acc_data in formatted_ad_data.items():
        fmt_acc_data = dict(acc_data)
        fmt_acc_data['disabled'] = deduct_acc_disabled(
            acc_data['userAccountControl']
        )
        formatted_acc_data[username] = fmt_acc_data
    return formatted_acc_data


def format_ldap_grp_data(ad_data, attrs):
    grp_data = format_ldap_data(ad_data, attrs)
    fmt_grp_data = dict()
    for grp_name, grp_vals in grp_data.items():
        fmt_grp_data[grp_name] = dict(grp_vals)
        if grp_vals['member'] is not None:
            fmt_grp_data[grp_name]['member'] = set(grp_vals['member'])
    return fmt_grp_data


def deduct_acc_disabled(ldap_uac_value):
    if hex(int(ldap_uac_value[0]))[-1] == '2':
        return True
    return False


def crb_acc_values_to_ad_values(account_data, path_req_disks,
                                nis_domain, group_postfix):
    def build_homedir(acc_data):
        home_host = acc_data.get('home_host')
        if not home_host:
            return None
        if home_host in path_req_disks:
            path = acc_data['home_path'].split('/')[-1]
            return '\\\\{0}\\{1}\\{2}'.format(home_host,
                                              path,
                                              acc_data['name'])
        return '\\\\{0}\\{1}'.format(home_host, acc_data['name'])

    def build_group_name(acc_data):
        grp_name = acc_data.get('posix_group_name')
        if grp_name:
            return ''.join([grp_name, group_postfix])
        return None

    def build_gecos(acc_data):
        if acc_data.get('gecos') is None:
            return None
        return account_data.get('gecos')

    def build_given_name(acc_data):
        if acc_data.get('first_name') is not None:
            return acc_data.get('first_name').strip()
        return None

    def build_sn(acc_data):
        if acc_data.get('last_name') is not None:
            return acc_data.get('last_name').strip()
        return None

    def build_display_name(acc_data):
        if acc_data.get('first_name') and acc_data.get('last_name'):
            return ' '.join([acc_data['first_name'], acc_data['last_name']])
        return None

    def build_uid_number(acc_data):
        if acc_data.get('posix_uid'):
            return str(acc_data['posix_uid'])
        return None

    def build_gid_number(acc_data):
        if acc_data.get('posix_gid'):
            return str(acc_data['posix_gid'])
        return None

    ad_values = {
        # account_id and username are included so we can easily
        # create lists of desynced/missing accounts, and look up
        # the corresponding accounts from the AD-LDAP payload.
        'account_id': account_data['account_id'],
        'username': account_data['name'],
        'mail': account_data['mail'],
        'disabled': account_data['disabled'],
        'givenName': build_given_name(account_data),
        'sn': build_sn(account_data),
        'displayName': build_display_name(account_data),
        'uidNumber': build_uid_number(account_data),
        'gidNumber': build_gid_number(account_data),
        'gecos': build_gecos(account_data),
        'primaryGroup_groupname': build_group_name(account_data),
        'uid': account_data['name'],
        'msSFU30Name': account_data['name'],
        'msSFU30NisDomain': nis_domain,
        'homeDirectory': build_homedir(account_data),
        'userPrincipalName': ''.join([account_data['name'], '@uio.no']),
        'homeDrive': 'M:'
    }
    for attr, val in ad_values.items():
        if attr not in ['account_id', 'username', 'disabled'] and \
           val is not None:
            # AD wraps all values (except for null/None) in lists
            ad_values[attr] = [val]
    return ad_values


def crb_grp_values_to_ad_values(group_data, users_dn, groups_dn, nis_domain,
                                group_postfix=''):
    def build_member(grp_data):
        members = grp_data.get('members')
        if not members:
            return None
        member_set = set()
        for member in members:
            if member['type'] == 'group':
                member_set.add('CN={0}{1},{2}'.format(member['name'],
                                                      group_postfix,
                                                      groups_dn))
            else:
                member_set.add('CN={0},{1}'.format(member['name'], users_dn))
        return member_set

    def build_gid_number(grp_data):
        gid = grp_data.get('posix_gid')
        if gid is not None:
            return str(gid)
        return None

    name = ''.join([group_data['name'], group_postfix])

    ad_values = {
        # We include group_id so we can reference it during diffing.
        'group_id': group_data['group_id'],
        'displayName': name,
        'description': group_data['description'] or None,
        'displayNamePrintable': name,
        'member': build_member(group_data),
        'gidNumber': build_gid_number(group_data),
        'msSFU30Name': name,
        'msSFU30NisDomain': nis_domain
    }
    # Wrap values in lists as this is how they are represented in data from AD
    for attr, val in ad_values.items():
        if attr not in ['member', 'group_id'] and val is not None:
            ad_values[attr] = [val]
    return ad_values


def build_scim_event_msg(event, formatter, ad_acc_spread, ad_grp_spread):
    routing_key = formatter.get_key(event['entity_type'], event['event_type'])
    entity_route = formatter.get_entity_type_route(event['entity_type'])
    aud = [ad_acc_spread]
    event_uri = formatter.get_uri(event['event_type'])
    if event['entity_type'] == 'group':
        aud = [ad_grp_spread]
    payload = {
        'jti': str(uuid.uuid4()),
        'eventUris': [event_uri],
        'iat': formatter.make_timestamp(),
        'iss': formatter.config.issuer,
        'sub': formatter.build_url(entity_route, event['entity_id']),
        'aud': aud,
        'resourceType': entity_route
    }
    if event.get('attrs'):
        payload[event_uri] = event['attrs']
    return {'routing_key': routing_key, 'payload': payload}
