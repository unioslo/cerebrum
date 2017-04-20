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
ad-sync script for UiA that uses ADsync.py module to sync users and groups
to AD and Exchange.

Usage: [options]
  --help: displays this text
  --user-sync: sync users to AD and Exchange
  --group-sync: sync groups to AD and Exchange
  --maillists-sync: sync mailing lists to AD and Exchange
  --forwarding-sync: sync forwarding rules to AD and Exchange
  --user_spread SPREAD: overrides cereconf.AD_ACCOUNT_SPREAD
  --user_exchange_spread SPREAD: overrides cereconf.AD_EXCHANGE_SPREAD
  --user_imap_spread SPREAD: overrides cereconf.AD_IMAP_SPREAD
  --default_user_ou OU: overrides default OU for users
  --only_ous OU: Override what user OUs that should be affected by the sync.
                 Users outside of these OUs are for instance not deleted. OUs
                 are separated by semicolons.
                 Default: cereconf.AD_ALL_CEREBRUM_OU
                 Example: 'OU=Users,OU=UiA;OU=Deleted Users,OU=UiA'
  --group_spread SPREAD: overrides cereconf.AD_GROUP_SPREAD
  --group_exchange_spread SPREAD: overrides cereconf.AD_GROUP_EXCHANGE_SPREAD
  --store-sid: write sid of new AD objects to cerebrum databse as external ids.
               default is _not_ to write sid to database.
  --dryrun: report changes that would have been done without --dryrun.
            Note that this executes the caching of Cerebrum data even when the
            AD server can't be reached. This makes it easier to debug some of
            the code.
  --delete: this option ensures deleting superfluous groups. default
            is _not_ to delete groups.
  --logger-level LEVEL: default is INFO
  --logger-name NAME: default is console

Example:
  ad_fullsync.py --user-sync --store-sid

  ad_fullsync.py --user-sync --group-sync \
    --user_spread 'account@ad' \
    --user_exchange_spread 'account@exchange' \
    --user_imap_spread 'account@imap'\
    --group_spread 'group@ad' \
    --group_exchange_spread 'group@exchange \
    --delete --store-sid

TODO: the script should support --ad_ldap for setting the root OU. Usable e.g.
for the guest users, and might speed up the job quite a bit. It is already
supported in ADutilsMixin, so all we need is to give it as an argument to
ADFullUserSync when instantiating it.

"""

import getopt
import sys
import xmlrpclib

import cereconf

from Cerebrum import Utils
from Cerebrum.modules.no.hia import ADsync


logger = Utils.Factory.get_logger('cronjob')
db = Utils.Factory.get('Database')()
db.cl_init(change_program="hia_ad_sync")
co = Utils.Factory.get('Constants')(db)
ac = Utils.Factory.get('Account')(db)


def fullsync(user_sync, group_sync, maillists_sync, forwarding_sync,
             user_spread, user_exchange_spread, user_imap_spread,
             group_spread, group_exchange_spread, dryrun,
             delete_objects, store_sid,
             default_user_ou, only_ous):

    # --- USER SYNC ---
    if user_sync:
        # Catch protocolError to avoid that url containing password is
        # written to log
        try:
            # instantiate sync_class and call full_sync
            adsync = ADsync.ADFullUserSync(db, co, logger, dry_run=dryrun)
            adsync.default_ou = default_user_ou
            adsync.only_ous = only_ous
            adsync.full_sync(delete=delete_objects, spread=user_spread,
                             dry_run=dryrun, store_sid=store_sid,
                             exchange_spread=user_exchange_spread,
                             imap_spread=user_imap_spread,
                             forwarding_sync=forwarding_sync)
        except xmlrpclib.ProtocolError, xpe:
            logger.critical(
                "Error connecting to AD service. Giving up!: %s %s" %
                (xpe.errcode, xpe.errmsg))

    # --- GROUP SYNC ---
    if group_sync:
        # Catch protocolError to avoid that url containing password is
        # written to log
        try:
            # instantiate sync_class and call full_sync
            ADsync.ADFullGroupSync(db, co, logger).full_sync(
                delete=delete_objects, group_spread=group_spread,
                dry_run=dryrun, store_sid=store_sid, user_spread=user_spread,
                exchange_spread=group_exchange_spread)
        except xmlrpclib.ProtocolError, xpe:
            logger.critical(
                "Error connecting to AD service. Giving up!: %s %s" %
                (xpe.errcode, xpe.errmsg))

    # --- MAILLIST CONTACT OBJECTS SYNC ---
    if maillists_sync:
        # Catch protocolError to avoid that url containing password is
        # written to log
        try:
            # instantiate sync_class and call full_sync
            ADsync.ADFullContactSync(db, co, logger).full_sync(
                dry_run=dryrun)
        except xmlrpclib.ProtocolError, xpe:
            logger.critical(
                "Error connecting to AD service. Giving up!: %s %s" %
                (xpe.errcode, xpe.errmsg))


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hugfm',  [
            'help', 'user-sync', 'group-sync', 'user_spread=',
            'user_exchange_spread=', 'user_imap_spread=', 'default_user_ou=',
            'only_ous=', 'dryrun', 'store-sid', 'delete',
            'group_spread=',
            'group_exchange_spread=', 'maillists-sync', 'forwarding-sync'])
    except getopt.GetoptError:
        usage(1)

    dryrun = False
    store_sid = False
    delete_objects = False
    user_sync = False
    group_sync = False
    maillists_sync = False
    forwarding_sync = False
    user_spread = cereconf.AD_ACCOUNT_SPREAD
    user_exchange_spread = cereconf.AD_EXCHANGE_SPREAD
    user_imap_spread = cereconf.AD_IMAP_SPREAD
    default_user_ou = None
    only_ous = None
    group_spread = cereconf.AD_GROUP_SPREAD
    group_exchange_spread = cereconf.AD_GROUP_EXCHANGE_SPREAD

    for opt, val in opts:
        if opt in ('--help', '-h'):
            usage()
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--delete',):
            delete_objects = True
        elif opt in ('--store-sid',):
            store_sid = True
        elif opt in ('--user-sync', '-u'):
            user_sync = True
        elif opt in ('--group-sync', '-g'):
            group_sync = True
        elif opt in ('--maillists-sync', '-m'):
            maillists_sync = True
        elif opt in ('--forwarding-sync', '-f'):
            forwarding_sync = True
        elif opt == '--user_spread':
            user_spread = val
        elif opt == '--user_exchange_spread':
            user_exchange_spread = val
        elif opt == '--user_imap_spread':
            user_imap_spread = val
        elif opt == '--default_user_ou':
            default_user_ou = val
        elif opt == '--only_ous':
            only_ous = val.split(';')
        elif opt == '--group_spread':
            group_spread = val
        elif opt == '--group_exchange_spread':
            group_exchange_spread = val

    fullsync(user_sync, group_sync, maillists_sync, forwarding_sync,
             user_spread, user_exchange_spread, user_imap_spread,
             group_spread, group_exchange_spread, dryrun,
             delete_objects, store_sid,
             default_user_ou, only_ous)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
