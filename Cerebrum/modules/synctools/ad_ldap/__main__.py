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
import cereconf

from Cerebrum import Utils
from Cerebrum.modules.event_publisher.amqp_publisher import AMQP091Publisher
from Cerebrum.modules.event_publisher.scim import ScimFormatter
from Cerebrum.modules.event_publisher.config import load_publisher_config
from Cerebrum.modules.event_publisher.config import load_formatter_config
from Cerebrum.modules.synctools.clients import get_ad_ldapclient
from Cerebrum.modules.synctools.clients import load_ad_ldap_config
from Cerebrum.modules.synctools.base_data_fetchers import get_account_id_by_username
from Cerebrum.modules.synctools.ad_ldap import mappers
from Cerebrum.modules.synctools.ad_ldap import functions

logger = Utils.Factory.get_logger("console")
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

parser = argparse.ArgumentParser(prog='ad_ldap')
parser.add_argument('--send', help="send events", action='store_true')
parser.add_argument('--queue-name', help="Queue name to send events to.",
                    required=True)

subparsers = parser.add_subparsers(dest='sub_command')

fullsync_parser = subparsers.add_parser(
    'fullsync',
    help='Do a fullsync. See "ad_ldap fullsync --help" for usage.'
)
fullsync_parser.add_argument('--all', action='store_true',
                             help='sync all accounts/groups.')
fullsync_parser.add_argument('--groups', action='store_true',
                             help='sync all groups.')
fullsync_parser.add_argument('--accounts', action='store_true',
                             help='sync all accounts.')

accounts_sync_parsers = subparsers.add_parser(
    'accounts',
    help='Only sync some specified accounts. '
         'See "ad_ldap accounts --help" for usage.')

accounts_sync_parsers.add_argument(
    '--ids', nargs="*", type=int,
    help="A list of account_ids to sync")
accounts_sync_parsers.add_argument(
    '--usernames', nargs="*", type=str,
    help="A list of account usernames to sync")
args = parser.parse_args()
print(args)
ad_ldap_config = load_ad_ldap_config()
client = get_ad_ldapclient(ad_ldap_config)
client.connect()

events = []

if args.sub_command == 'accounts':
    if not (args.usernames or args.ids):
        raise SystemExit('See "ad_ldap accounts -h" for usage. Exiting...')
    account_ids = []
    if args.usernames:
        for username in args.usernames:
            account_id = get_account_id_by_username(db, username)
            if account_id:
                account_ids.append(account_id)
            else:
                raise SystemExit('Error: account "{}" not found! '
                                 'Exiting...'.format(username))

    if args.ids:
        account_ids.extend(args.ids)
        events = functions.get_account_events(
            db=db,
            client=client,
            account_ids=account_ids,
            ad_acc_spread=ad_acc_spread,
            group_postfix=group_postfix,
            path_req_disks=path_req_disks,
            acc_attrs=acc_attrs
        )

if args.sub_command == 'fullsync':
    if args.all:
        if args.groups or args.accounts:
            raise SystemExit(
                'Error: --all cannot be used along --accounts/--groups. '
                'Exiting..'
            )
        events = functions.build_all_acc_and_grp_events(
            db=db,
            client=client,
            ad_acc_spread=ad_acc_spread,
            ad_grp_spread=ad_grp_spread,
            group_postfix=group_postfix,
            path_req_disks=path_req_disks,
            acc_attrs=acc_attrs,
            grp_attrs=grp_attrs)

    if args.accounts and args.groups:
        raise SystemExit(
            'Error: Use --all instead of both --accounts & --groups. '
            'Exiting..'
        )
    if args.groups:
        events = functions.build_all_group_events(
            db=db,
            client=client,
            ad_acc_spread=ad_acc_spread,
            ad_grp_spread=ad_grp_spread,
            group_postfix=group_postfix,
            grp_attrs=grp_attrs
        )

    if args.accounts:
        events = functions.build_all_account_events(
            db=db,
            client=client,
            ad_acc_spread=ad_acc_spread,
            ad_grp_spread=ad_grp_spread,
            group_postfix=group_postfix,
            path_req_disks=path_req_disks,
            acc_attrs=acc_attrs
        )

logger.info('# of generated scim-events to be sent: {}'.format(len(events)))

if args.send:
    formatter_config = load_formatter_config()
    formatter = ScimFormatter(formatter_config)
    scim_events = [mappers.build_scim_event_msg(event,
                                                formatter,
                                                str(ad_acc_spread),
                                                str(ad_grp_spread))
                   for event in events]
    pub_config = load_publisher_config()
    c = AMQP091Publisher(pub_config)
    c.open()
    for msg in events:
        c.publish(args.queue_name, events)
    c.close()
