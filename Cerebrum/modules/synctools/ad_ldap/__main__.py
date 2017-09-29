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

import argparse
import ldap
import cereconf

from Cerebrum import Utils
from Cerebrum.modules.event_publisher.amqp_publisher import AMQP091Publisher
from Cerebrum.modules.event_publisher.scim import ScimFormatter
from Cerebrum.modules.event_publisher.config import load_publisher_config
from Cerebrum.modules.event_publisher.config import load_formatter_config
from Cerebrum.modules.synctools.clients import get_ad_ldapclient
from Cerebrum.modules.synctools.clients import load_ad_ldap_config
from Cerebrum.modules.synctools.compare import equal
from Cerebrum.modules.synctools.data_fetchers import get_account_id_by_username
from Cerebrum.modules.synctools.ad_ldap import data_fetchers as df
from Cerebrum.modules.synctools.ad_ldap.mappers \
    import (crb_acc_values_to_ad_values,
            crb_grp_values_to_ad_values,
            build_scim_event_msg)

parser = argparse.ArgumentParser()
parser.add_argument('--account_ids', nargs="*", type=int, help="""A list of entity_ids to sync""")
parser.add_argument('--usernames', nargs="*", type=str, help="""A list of usernames to sync""")
parser.add_argument('--fullsync', help="""Do a complete sync for all
                         accounts/groups""", action='store_true')
parser.add_argument('--groups', help="""Do a complete sync for all
                         accounts/groups""", action='store_true')
parser.add_argument('--test', help="""Do a complete sync for all
                         accounts/groups""", action='store_true')
parser.add_argument('--send', help="""send messages""", action='store_true')
args = parser.parse_args()

#if not args.usernames and not args.account_ids and not args.fullsync and not args.groups:
#    raise SystemExit(
#        'Error: No sync method specified. See --help.'
#    )
#if (args.usernames or args.account_ids) and args.fullsync:
#    raise SystemExit(
#        'Error: --fullsync cannot be used with --account_ids or --usernames'
#    )

db = Utils.Factory.get('Database')()
co = Utils.Factory.get('Constants')(db)
group_postfix = getattr(cereconf, 'AD_GROUP_POSTFIX', '')
path_req_disks = getattr(cereconf, 'AD_HOMEDIR_HITACHI_DISKS', ())
ad_acc_spread = co.Spread(cereconf.AD_ACCOUNT_SPREAD)
ad_grp_spread = co.Spread(cereconf.AD_GROUP_SPREAD)

acc_attrs = ['sn', 'givenName', 'displayName', 'mail',
             'userPrincipalName', 'homeDirectory', 'homeDrive',
             'gidNumber', 'gecos', 'uidNumber',
             'uid', 'msSFU30Name', 'msSFU30NisDomain']

grp_attrs = ['displayName', 'description', 'displayNamePrintable', 'member',
             'gidNumber', 'msSFU30Name', 'msSFU30NisDomain']


def format_ldap_data(ad_data, attrs):
    r = {}
    for data in ad_data:
        r[data[1]['cn'][0]] = {
            key: data[1].get(key, None)
            for key in attrs
        }
    return r


def get_ad_ldap_acc_values(client, config, attrs, username):
    raw_ad_data = client.fetch_data(config.users_dn,
                                    ldap.SCOPE_SUBTREE,
                                    '(cn={})'.format(username))
    return format_ldap_data(raw_ad_data, attrs)


def get_all_ad_ldap_acc_values(client, config, attrs):
    ad_data = client.fetch_data(config.users_dn,
                                ldap.SCOPE_SUBTREE,
                                '(objectClass=user)')
    return format_ldap_data(ad_data, attrs)


def get_all_ad_ldap_grp_values(client, config, attrs):
    ad_data = client.fetch_data(config.groups_dn,
                                ldap.SCOPE_SUBTREE,
                                '(objectClass=group)')
    return format_ldap_data(ad_data, attrs)


events = []
account_ids = []

if args.usernames:
    for username in args.usernames:
        account_id = get_account_id_by_username(db, username)
        if account_id:
            account_ids.append(account_id)

if account_ids:
    print(account_ids)
    ad_ldap_config = load_ad_ldap_config()
    client = get_ad_ldapclient(ad_ldap_config)
    client.connect()
    crb_accs_data = [
        df.get_crb_account_data(db, acc_id, ad_acc_spread)
        for acc_id in account_ids
    ]
    crb_acc_ad_values = [
        crb_acc_values_to_ad_values(crb_acc_data,
                                    path_req_disks,
                                    group_postfix,
                                    db.encoding)
        for crb_acc_data in crb_accs_data]

    desynced_accs = []
    not_in_ad = []

    for crb_acc in crb_acc_ad_values:
        if crb_acc.get('quarantine_action') == 'skip':
            continue
        ad_ldap_acc_values = get_ad_ldap_acc_values(client,
                                                    ad_ldap_config,
                                                    acc_attrs,
                                                    crb_acc['username'])
        if crb_acc['username'] not in ad_ldap_acc_values:
            not_in_ad.append(crb_acc['account_id'])
            continue
        if not equal(crb_acc, ad_ldap_acc_values[crb_acc['username']], acc_attrs):
            desynced_accs.append(crb_acc['account_id'])
        # Remove from dict to get number of accounts not present in AD,
        # but not Cerebrum when this for-loop is done.
        ad_ldap_acc_values.pop(crb_acc['username'])
        print('# of accounts that are desynced: {}'.format(len(desynced_accs)))
        print('# of accounts present in Cerebrum, but not in AD: {}'.format(
            len(not_in_ad)
        ))
        print('# of accounts present in AD, but not in Cerebrum: {}'.format(
            len(ad_ldap_acc_values)
        ))
    for acc in desynced_accs:
        events.append({'entity_id': acc,
                       'event_type': 'modify',
                       'entity_type': 'account'})

if args.fullsync:
    print('Getting data from AD-LDAP....')
    ad_ldap_config = load_ad_ldap_config()
    client = get_ad_ldapclient(ad_ldap_config)
    ad_ldap_acc_values = get_all_ad_ldap_acc_values(client,
                                                    ad_ldap_config,
                                                    acc_attrs)
    print('Getting data from Cerebrum...')
    all_crb_accs_data = df.get_all_crb_accounts_data(db,
                                                     ad_acc_spread,
                                                     ad_grp_spread)
    crb_acc_ad_values = [
        crb_acc_values_to_ad_values(crb_acc_data,
                                    path_req_disks,
                                    group_postfix,
                                    db.encoding)
        for crb_acc_data in all_crb_accs_data]

    skipped = len(all_crb_accs_data) - len(crb_acc_ad_values)
    desynced_accs = []
    not_in_ad = []

    print('Diffing account data...')
    for crb_acc in crb_acc_ad_values:
        if crb_acc['username'] not in ad_ldap_acc_values:
            not_in_ad.append(crb_acc['account_id'])
            continue
        if not equal(crb_acc, ad_ldap_acc_values[crb_acc['username']], acc_attrs):
            desynced_accs.append(crb_acc['account_id'])
        # Remove from dict to get number of accounts not present in AD,
        # but not Cerebrum when this for-loop is done.
        ad_ldap_acc_values.pop(crb_acc['username'])

    print('# of accounts that were skipped: {}'.format(skipped))
    print('# of accounts that are desynced: {}'.format(len(desynced_accs)))
    print('# of accounts present in Cerebrum, but not in AD: {}'.format(
        len(not_in_ad)
    ))
    print('# of accounts present in AD, but not in Cerebrum: {}'.format(
        len(ad_ldap_acc_values)
    ))
    for crb_acc in desynced_accs:
        events.append({'entity_id': crb_acc,
                       'event_type': 'modify',
                       'entity_type': 'account'})

from pprint import pprint

if args.groups:
    ad_ldap_config = load_ad_ldap_config()
    client = get_ad_ldapclient(ad_ldap_config)
    client.connect()
    all_ad_ldap_grp_values = get_all_ad_ldap_grp_values(client,
                                                        ad_ldap_config,
                                                        grp_attrs)

    all_crb_groups_data = df.get_all_groups_values(db,
                                                   ad_grp_spread,
                                                   ad_acc_spread)
    all_crb_groups_values = {}
    for grp_name, grp_data in all_crb_groups_data.iteritems():
        values = crb_grp_values_to_ad_values(grp_data,
                                             db.encoding,
                                             ad_ldap_config.users_dn,
                                             group_postfix)
        all_crb_groups_values[values['displayName']] = values

    skipped = 0
    not_in_ad = []
    desynced_grps = []

    for grp, group_data in all_crb_groups_values.items():
        if grp not in all_ad_ldap_grp_values:
            not_in_ad.append(group_data['group_id'])
            continue
        if not equal(group_data, all_ad_ldap_grp_values[grp], grp_attrs):
            desynced_grps.append(group_data['group_id'])
        all_ad_ldap_grp_values.pop(grp)
    print('# of groups that are desynced: {}'.format(len(desynced_grps)))
    print('# of groups present in Cerebrum, but not in AD: {}'.format(
        len(not_in_ad)
    ))

    #pprint(grp_values)


print('# of scim-events to be sent: {}'.format(len(events)))

formatter_config = load_formatter_config()
formatter = ScimFormatter(formatter_config)
scim_events = [build_scim_event_msg(event,
                                    formatter,
                                    str(ad_acc_spread),
                                    str(ad_grp_spread))
               for event in events]
pprint(scim_events)

if args.send:
    pub_config = load_publisher_config()
    c = AMQP091Publisher(pub_config)
    c.open()
    for msg in events:
        c.publish('omglol', events)
    c.close()

if args.test:
    pass