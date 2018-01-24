#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2006, 2007 University of Oslo, Norway
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


"""
ad-sync script for UiO that uses ADsync.py module to sync users and groups
to AD.
Usage: [options]
  -h, --help
        displays this text
  -u, --user-sync
        sync users to AD
  -p, --password-sync
        sync passwords for users in AD
  -g, --group-sync
        sync groups to AD
  --user_spread SPREAD
        overrides cereconf.AD_ACCOUNT_SPREAD
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
  --full_membersync
        this option uses a full sync of members, i.e. writing all
        group memberships with no regards to current status.
  --logger-level LEVEL
        default is INFO
  --logger-name NAME
        default is console
Example:
  ad_fullsync.py --user-sync --store-sid

  ad_fullsync.py --user-sync --password-sync --group-sync  
    --user_spread 'AD_account' --group_spread 'AD_group' 
    --delete --store-sid --logger-level DEBUG --logger-name console
"""


import getopt
import sys
import xmlrpclib
import cerebrum_path
import cereconf
from Cerebrum.Constants import _SpreadCode
from Cerebrum import Utils
from Cerebrum.modules.no.uio import ADsync



db = Utils.Factory.get('Database')()
db.cl_init(change_program="uio_ad_sync")
co = Utils.Factory.get('Constants')(db)
ac = Utils.Factory.get('Account')(db)


def fullsync(user_sync, group_sync, password_sync, user_spread, group_spread, 
             dryrun, delete_objects, store_sid, logger_name, logger_level, 
             sendDN_boost, full_membersync):
        
    # initate logger
    logger = Utils.Factory.get_logger(logger_name)
    # set logger level ...

    # --- USER SYNC ---
    if user_sync:
        # Catch protocolError to avoid that url containing password is
        # written to log
        try:
            # instantiate sync_class and call full_sync
            ADsync.ADFullUserSync(db, co, logger).full_sync(
                delete=delete_objects, spread=user_spread, dry_run=dryrun,
                store_sid=store_sid, pwd_sync=password_sync)
        except xmlrpclib.ProtocolError, xpe:
            logger.critical("Error connecting to AD service. Giving up!: %s %s" %
                            (xpe.errcode, xpe.errmsg))
    

    # --- GROUP SYNC ---
    if group_sync:
        # Catch protocolError to avoid that url containing password is
        # written to log
        try:
            # instantiate sync_class and call full_sync
            ADsync.ADFullGroupSync(db, co, logger).full_sync(
                delete=delete_objects, dry_run=dryrun, store_sid=store_sid,
                user_spread=user_spread, group_spread=group_spread,
                sendDN_boost=sendDN_boost, full_membersync=full_membersync)
        except xmlrpclib.ProtocolError, xpe:
            logger.critical("Error connecting to AD service. Giving up!: %s %s" %
                            (xpe.errcode, xpe.errmsg))
    

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hugp',  [
            'help', 'user-sync', 'group-sync', 'user_spread=',
            'dryrun', 'store-sid', 'sendDN_boost', 'password-sync',
            'delete', 'full_membersync', 'group_spread=', 
            'logger-level=', 'logger-name='])
    except getopt.GetoptError:
        usage(1)

    dryrun = False
    store_sid = False
    delete_objects = False
    user_sync = False
    group_sync = False
    password_sync = False
    sendDN_boost = False
    full_membersync = False
    user_spread = cereconf.AD_ACCOUNT_SPREAD
    group_spread = cereconf.AD_GROUP_SPREAD
    logger_name = 'cronjob'
    logger_level = 'INFO'
    for opt, val in opts:
        if opt in ('--help','-h'):
            usage()
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--delete',):
            delete_objects = True
        elif opt in ('--store-sid',):
            store_sid = True
        elif opt in ('--user-sync','-u'):
            user_sync = True
        elif opt in ('--group-sync','-g'):
            group_sync = True
        elif opt in ('--password-sync','-p'):
            password_sync = True
        elif opt == '--user_spread':
            user_spread = val
        elif opt == '--group_spread':
            group_spread = val
        elif opt == '--sendDN_boost':
            sendDN_boost = True
        elif opt == '--full_membersync':
            full_membersync = True    
        elif opt == '--logger-name':
            logger_name = val
        elif opt == '--logger-level':
            logger_level = val
        
    fullsync(user_sync, group_sync, password_sync, user_spread, group_spread, 
             dryrun, delete_objects, store_sid, logger_name, logger_level, 
             sendDN_boost, full_membersync)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
