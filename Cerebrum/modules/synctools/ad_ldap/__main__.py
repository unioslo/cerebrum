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

import os
import sys
import argparse
import cereconf
import getpass

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

parser = argparse.ArgumentParser(prog='ad_ldap')
parser.add_argument('--send', help="send events", action='store_true')
parser.add_argument('--ad-ldap-config', help="Path to ad-ldap config file")
parser.add_argument('--formatter-config', help="Path to event-formatter "
                                               "config file.")
parser.add_argument('--publisher-config', help="Path to event-formatter "
                                               "config file.")
parser.add_argument('--log-diff',
                    help='Log diff data. This will be ignored '
                         'during password sync.',
                    action='store_true',
                    default=False)
parser.add_argument('--password-sync',
                    help="Sync password on targeted account(s)",
                    action='store_true',
                    default=False)
parser.add_argument('--ldap-user', help='User to make LDAP connection with. '
                                        'This will also require that you '
                                        'specify the user\'s password when '
                                        'the script starts.')

# This is needed to prevent argparse from complaining about unknown arg.
parser.add_argument('--logger-name', help="Cerebrum-logger name")
subparsers = parser.add_subparsers(dest='sub_command')

fullsync_parser = subparsers.add_parser(
    'fullsync',
    help='Do a fullsync. See "ad_ldap fullsync --help" for usage.'
)
fullsync_group = fullsync_parser.add_mutually_exclusive_group(required=True)
fullsync_group.add_argument('--all', action='store_true',
                            help='sync all accounts/groups.')
fullsync_group.add_argument('--groups', action='store_true',
                            help='sync all groups.')
fullsync_group.add_argument('--accounts', action='store_true',
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

logger = Utils.Factory.get_logger("console")
db = Utils.Factory.get('Database')(client_encoding='utf-8')
co = Utils.Factory.get('Constants')(db)
group_postfix = getattr(cereconf, 'AD_GROUP_POSTFIX', '')
path_req_disks = getattr(cereconf, 'AD_HOMEDIR_HITACHI_DISKS', ())
ad_acc_spread = co.Spread(cereconf.AD_ACCOUNT_SPREAD)
ad_grp_spread = co.Spread(cereconf.AD_GROUP_SPREAD)
acc_attrs = list(cereconf.AD_ATTRIBUTES)
acc_attrs.append('disabled')
grp_attrs = cereconf.AD_GRP_ATTRIBUTES


def load_config(loader, filepath=None):
    if filepath is not None:
        if os.path.isfile(filepath):
            return loader(filepath=filepath)
        else:
            sys.exit('Error: {} does not exist.'.format(filepath))
    else:
        return loader()


ad_ldap_config = load_config(load_ad_ldap_config, args.ad_ldap_config)
formatter_config = load_config(load_formatter_config, args.formatter_config)
publisher_config = load_config(load_publisher_config, args.publisher_config)


ldap_pass = None
if not args.password_sync and args.ldap_user:
    ldap_pass = getpass.getpass(prompt='Enter password for {}: '
                                       ''.format(args.ldap_user))

client = get_ad_ldapclient(ad_ldap_config)

if args.password_sync:
    if args.sub_command == 'fullsync' and args.all or args.groups:
        sys.exit('Option --password-sync can be used with accounts only.\n'
                 'See "ad_ldap accounts -h" for usage. Exiting...')
else:
    client.connect(username=args.ldap_user, password=ldap_pass)

events = []

if args.sub_command == 'accounts':
    if not (args.usernames or args.ids):
        sys.exit('See "ad_ldap accounts -h" for usage. Exiting...')
    account_ids = []
    if args.usernames:
        for username in args.usernames:
            account_id = get_account_id_by_username(db, username)
            if account_id:
                account_ids.append(account_id)
            else:
                sys.exit('Error: account "{}" not found! '
                         'Exiting...'.format(username))

    if args.ids:
        account_ids.extend(args.ids)

    events = functions.build_account_events(
        db=db,
        client=client,
        account_ids=account_ids,
        ad_acc_spread=ad_acc_spread,
        group_postfix=group_postfix,
        path_req_disks=path_req_disks,
        acc_attrs=acc_attrs,
        password_sync=args.password_sync,
        show_diff=args.log_diff)

elif args.sub_command == 'fullsync':
    if args.all:
        events = functions.build_all_group_events(
            db=db,
            client=client,
            ad_acc_spread=ad_acc_spread,
            ad_grp_spread=ad_grp_spread,
            group_postfix=group_postfix,
            grp_attrs=grp_attrs,
            show_diff=args.log_diff
        )
        events.extend(functions.build_all_account_events(
            db=db,
            client=client,
            ad_acc_spread=ad_acc_spread,
            ad_grp_spread=ad_grp_spread,
            group_postfix=group_postfix,
            path_req_disks=path_req_disks,
            acc_attrs=acc_attrs,
            show_diff=args.log_diff
        ))
    elif args.groups:
        events = functions.build_all_group_events(
            db=db,
            client=client,
            ad_acc_spread=ad_acc_spread,
            ad_grp_spread=ad_grp_spread,
            group_postfix=group_postfix,
            grp_attrs=grp_attrs,
            show_diff=args.log_diff
        )
    elif args.accounts:
        events = functions.build_all_account_events(
            db=db,
            client=client,
            ad_acc_spread=ad_acc_spread,
            ad_grp_spread=ad_grp_spread,
            group_postfix=group_postfix,
            path_req_disks=path_req_disks,
            acc_attrs=acc_attrs,
            password_sync=args.password_sync,
            show_diff=args.log_diff
        )

logger.info('# of generated events: {}'.format(len(events)))

if args.send:
    logger.info('Building SCIM-events out of events...')
    formatter = ScimFormatter(formatter_config)
    scim_events = [mappers.build_scim_event_msg(event,
                                                formatter,
                                                str(ad_acc_spread),
                                                str(ad_grp_spread))
                   for event in events]
    c = AMQP091Publisher(publisher_config)
    c.open()
    logger.info('Sending events...')
    for scim_event in scim_events:
        c.publish(scim_event['routing_key'], scim_event['payload'])
    c.close()
