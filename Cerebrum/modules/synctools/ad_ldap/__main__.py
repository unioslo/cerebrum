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
import ldap

from Cerebrum import Utils
from Cerebrum.modules.synctools.ad_ldap import get_client
from Cerebrum.modules.synctools.ad_ldap import load_ad_ldap_config
from Cerebrum.modules.synctools.data_fetcher import CerebrumDataFetcher

parser = argparse.ArgumentParser()
parser.add_argument('--account_ids', nargs="*", type=int, help="""A list of entity_ids to sync""")
parser.add_argument('--usernames', nargs="*", type=str, help="""A list of usernames to sync""")
parser.add_argument('--fullsync', help="""Do a complete sync for all
                         accounts/groups""", action='store_true')
parser.add_argument('--groups', help="""Do a complete sync for all
                         accounts/groups""", action='store_true')
parser.add_argument('--send', help="""send messages""", action='store_true')
args = parser.parse_args()

if not args.usernames and not args.account_ids and not args.fullsync and not args.groups:
    raise SystemExit(
        'Error: No sync method specified. See --help.'
    )
if (args.usernames or args.account_ids) and args.fullsync:
    raise SystemExit(
        'Error: --fullsync cannot be used with --account_ids or --usernames'
    )


group_postfix = getattr(cereconf, 'AD_GROUP_POSTFIX', '')
path_req_disks = getattr(cereconf, 'AD_HOMEDIR_HITACHI_DISKS', ())
df = CerebrumDataFetcher()
db = Utils.Factory.get('Database')()
co = Utils.Factory.get('Constants')(db)
ad_acc_spread = co.Spread(cereconf.AD_ACCOUNT_SPREAD)
ad_grp_spread = co.Spread(cereconf.AD_GROUP_SPREAD)


attrs = ['sn', 'givenName', 'displayName', 'mail',
         'userPrincipalName', 'homeDrive', 'homeDirectory',
         'uidNumber', 'gidNumber', 'gecos',
         'uid', 'msSFU30Name', 'msSFU30NisDomain']

from pprint import pprint

def get_ad_ldap_data():
    client = get_client()
    config = load_ad_ldap_config()
    client.connect()
    raw_ad_data = client.fetch_data(config.users_dn, ldap.SCOPE_SUBTREE, '(ObjectClass=user)')

    pprint(raw_ad_data[0][1])

    ad_data = {}
    for acc_data in raw_ad_data:
        ad_data[acc_data[1]['cn'][0]] = {
            key: acc_data[1].get(key, None)
            for key in attrs
        }


if args.fullsync:
    #ad_ldap_data = get_ad_ldap_data()
    df = CerebrumDataFetcher()
    acc_rows = df.get_all_account_rows()
    pprint(acc_rows.popitem())

