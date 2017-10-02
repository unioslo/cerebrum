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


def crb_acc_values_to_ad_values(account_data, path_req_disks,
                                nis_domain, group_postfix, encoding):
    first_name = unicode(account_data.get('first_name') or '', encoding)
    last_name = unicode(account_data.get('last_name') or '', encoding)

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

    def build_mail(acc_data):
        email = acc_data.get('email')
        if email:
            return {'mail': [email]}
        return {}

    def build_group_name(acc_data):
        grp_name = acc_data.get('posix_group_name')
        if grp_name:
            return ''.join([grp_name, group_postfix])
        return ''

    ad_values = {
        # account_id and username are included so we can easily
        # create lists of desynced/missing accounts, and look up
        # the corresponding accounts from the AD-LDAP payload.
        'account_id': account_data['account_id'],
        'username': account_data['name'],
        'mail': unicode(account_data['mail']),
        'disabled': account_data['disabled'],
        'givenName': first_name.strip(),
        'sn': last_name.strip(),
        'displayName': ' '.join([first_name, last_name]),
        'uidNumber': str(account_data.get('posix_uid')) or '',
        'gidNumber': str(account_data.get('posix_gid')) or '',
        'gecos': unicode(account_data.get('gecos') or '', encoding),
        'primaryGroup_groupname': build_group_name(account_data),
        'uid': account_data['name'],
        'msSFU30Name': account_data['name'],
        'msSFU30NisDomain': nis_domain,
        'homeDirectory': build_homedir(account_data),
        'userPrincipalName': ''.join([account_data['name'], '@uio.no']),
        'homeDrive': 'M:'
    }
    ad_values.update(build_mail(account_data))
    return ad_values


def crb_grp_values_to_ad_values(group_data, encoding, users_dn, nis_domain,
                                group_postfix=''):
    name = unicode(''.join([group_data['name'], group_postfix]), encoding)
    if 'member' in group_data:
        members = [u'cn={0},{1}'.format(member, users_dn)
                   for member in sorted(group_data['member'])]
    else:
        members = None
    return {
        # We include group_id so we can reference it during diffing.
        'group_id': group_data['group_id'],
        'displayName': name,
        'description': unicode(group_data['description'], encoding),
        'displayNamePrintable': name,
        'member': members,
        'gidNumber': group_data.get('posix_gid'),
        'msSFU30Name': name,
        'msSFU30NisDomain': nis_domain
    }


def build_scim_event_msg(event, formatter, ad_acc_spread, ad_grp_spread):
    entity_route = formatter.get_entity_type_route(event['entity_type'])
    aud = [ad_acc_spread]
    if event['entity_type'] == 'group':
        aud = [ad_grp_spread]
    payload = {
        'jti': str(uuid.uuid4()),
        'eventUris': [formatter.get_uri(event['event_type'])],
        'iat': formatter.make_timestamp(),
        'iss': formatter.config.issuer,
        'sub': formatter.build_url(entity_route, event['entity_id']),
        'aud': aud,
        'resourceType': entity_route
    }
    return payload

