#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2017 University of Oslo, Norway
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
r"""
ad-sync script for OFK that uses ADsync.py module to sync users and groups
to AD and Exchange.

Usage: [options]
  -h, --help
        displays this text
  -u, --user-sync
        sync users to AD and Exchange
  -g, --group-sync
        sync groups to AD and Exchange
  --user_spread SPREAD
        overrides cereconf.AD_ACCOUNT_SPREAD
  --user_exchange_spread SPREAD
        overrides cereconf.AD_EXCHANGE_SPREAD
  --group_spread SPREAD
        overrides cereconf.AD_GROUP_SPREAD
  --store-sid
        write sid of new AD objects to cerebrum databse as external ids.
        default is _not_ to write sid to database.
  --dryrun
        report changes that would have been done without --dryrun.
  --delete
        this option ensures deleting superfluous groups. default
        is _not_ to delete groups.
  --sendDN_boost
        this option tells the group sync to send full Distinguished
        Names of group memebers to the AD service thus saving time
        from looking up the user objects on the server.
  --logger-level LEVEL
        default is INFO
  --logger-name NAME
        default is console
Example:
  ad_fullsync.py --user-sync --store-sid

  ad_fullsync.py --user-sync --group-sync \
    --user_spread 'account@ad' \
    --user_exchange_spread 'account@exchange' \
    --group_spread 'group@ad' \
    --delete --store-sid
"""


import getopt
import sys
import xmlrpclib
import cereconf
from Cerebrum import Utils
from Cerebrum.modules.no.Indigo import OFK_ADsync


logger = Utils.Factory.get_logger('cronjob')

db = Utils.Factory.get('Database')()
db.cl_init(change_program="ofk_ad_sync")
co = Utils.Factory.get('Constants')(db)
ac = Utils.Factory.get('Account')(db)


def fullsync(user_sync, group_sync, user_spread, user_exchange_spread,
             group_spread, dryrun, delete_objects, store_sid, sendDN_boost):

    # --- USER SYNC ---
    if user_sync:
        # Catch protocolError to avoid that url containing password is
        # written to log
        try:
            # instantiate sync_class and call full_sync
            OFK_ADsync.ADFullUserSync(db, co, logger).full_sync(
                delete=delete_objects, spread=user_spread, dry_run=dryrun,
                store_sid=store_sid, exchange_spread=user_exchange_spread)
        except xmlrpclib.ProtocolError as xpe:
            logger.critical(
                "Error connecting to AD service. Giving up!: %s %s" %
                (xpe.errcode, xpe.errmsg))

    # --- GROUP SYNC ---
    if group_sync:
        # Catch protocolError to avoid that url containing password is
        # written to log
        try:
            # instantiate sync_class and call full_sync
            OFK_ADsync.ADFullGroupSync(db, co, logger).full_sync(
                delete=delete_objects, dry_run=dryrun, store_sid=store_sid,
                user_spread=user_spread, group_spread=group_spread,
                sendDN_boost=sendDN_boost)
        except xmlrpclib.ProtocolError as xpe:
            logger.critical(
                "Error connecting to AD service. Giving up!: %s %s" %
                (xpe.errcode, xpe.errmsg))


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hug',  [
            'help', 'user-sync', 'group-sync', 'user_spread=',
            'user_exchange_spread=', 'dryrun', 'store-sid', 'sendDN_boost',
            'delete', 'group_spread='])
    except getopt.GetoptError:
        usage(1)

    dryrun = False
    store_sid = False
    delete_objects = False
    user_sync = False
    group_sync = False
    sendDN_boost = False
    user_spread = cereconf.AD_ACCOUNT_SPREAD
    user_exchange_spread = cereconf.AD_EXCHANGE_SPREAD
    group_spread = cereconf.AD_GROUP_SPREAD
    for opt, val in opts:
        if opt in ('--help', '-h'):
            usage()
        elif opt in ('--dryrun', ):
            dryrun = True
        elif opt in ('--delete', ):
            delete_objects = True
        elif opt in ('--store-sid', ):
            store_sid = True
        elif opt in ('--user-sync', '-u'):
            user_sync = True
        elif opt in ('--group-sync', '-g'):
            group_sync = True
        elif opt == '--user_spread':
            user_spread = val
        elif opt == '--user_exchange_spread':
            user_exchange_spread = val
        elif opt == '--group_spread':
            group_spread = val
        elif opt == '--sendDN_boost':
            sendDN_boost = True

    fullsync(user_sync, group_sync, user_spread, user_exchange_spread,
             group_spread, dryrun, delete_objects, store_sid, sendDN_boost)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
