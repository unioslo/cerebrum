#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2010, 2011 University of Oslo, Norway
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
AD-sync script for NIH to sync Cerebrum users and groups to AD and
Exchange. The arguments --group-sync, --user-sync and controls which
sync type that is performed. The argument --exchange-sync controls if
certain mail specific attribuets should be updated in Exchange, and
--forward-sync controls if forward addresses should be exported to
Exchange as contact objects.

The script reads config data from command line and/or cereconf,
initiate the correct ADsync and connects to the AD-service.

Usage: [options]
  --help: displays this text
  --user-sync: sync users to AD and Exchange
  --group-sync: sync groups to AD and Exchange
  --forward-sync: sync forward addrs to Exchange
  --exchange-sync: Only sync to exhange if True
  --user_spread SPREAD: overrides spread from cereconf
  --group_spread SPREAD: overrides spread from cereconf
  --user_exchange_spread SPREAD: overrides spread from cereconf
  --group_exchange_spread SPREAD: overrides spread from cereconf
  --store-sid: write sid of new AD objects to cerebrum databse as external ids.
               default is _not_ to write sid to database.
  --delete-groups: this option ensures deleting superfluous groups. default
                   is _not_ to delete groups.
  --delete-users: Should obsolete users be disabled or deleted?
  --cb_subset: Only sync users/groups from subset
  --ad_subset: Only compare users from this subset. Only usable if
               cb_subset is set.
  --dryrun: report changes that would have been done without --dryrun.
  --logger-level LEVEL: default is INFO
  --logger-name NAME: default is console

"""


import getopt
import sys
import xmlrpclib
import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum.modules.no.nih import ADSync

db = Utils.Factory.get('Database')()
db.cl_init(change_program="nih_ad_sync")


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hd",  [
            "user-sync", "group-sync", "forward-sync", 
            "exchange-sync", "user_spread=", "group_spread=",
            "exchange_spread=", "cb_subset=", "ad_subset=",
            "store-sid", "domain=", "delete", "host=", "port=", 
            "logger-level=", "logger-name=", "dryrun", "help"])
    except getopt.GetoptError, e:
        print e
        usage(1)

    host = cereconf.AD_SERVER_HOST
    port = cereconf.AD_SERVER_PORT
    delete = None
    logger_name = "console"
    logger_level = "INFO"
    # Configure AD sync. Set default values, then read cereconf and
    # user input.
    config_args = {'ad_ldap': cereconf.AD_LDAP,
                   'ad_domain': cereconf.AD_DOMAIN,
                   "user_spread": cereconf.AD_ACCOUNT_SPREAD,
                   "group_spread": cereconf.AD_GROUP_SPREAD,
                   "user_exchange_spread": cereconf.AD_EXCHANGE_SPREAD,
                   "group_exchange_spread": cereconf.AD_DIST_GROUP_SPREAD,
                   "dryrun": False,
                   "store_sid": False,
                   "forward_sync": False,
                   "exchange_sync": False,
                   "ad_subset": None,
                   "cb_subset": None}
    
    for opt, val in opts:
        # General options
        if opt in ("--help","-h"):
            usage()
        elif opt in ("--dryrun", "-d"):
            config_args["dryrun"] = True
        elif opt == "--host":
            config_args["host"] = val
        elif opt == "--port":
            config_args["port"]  = val
        elif opt == "--delete":
            delete = true_false(val)
        elif opt == "--store-sid":
            config_args["store_sid"] = True
        elif opt in ("ad_subset", "cb_subset"):
            try:
                unames = [line.strip() for line in file(val) if line.strip()]
            except IOError:
                unames = [f.strip() for f in val.split(",")]
            config_args[opt] = unames
        elif opt == "--logger-name":
            logger_name = val
        elif opt == "--logger-level":
            logger_level = val
        # Sync type options
        elif opt in ('--user-sync',):
            sync_type = "user"
        elif opt in ('--group-sync',):
            sync_type = "group"
        elif opt in ('--forward-sync',):
            config_args["forward_sync"] = True
        # spreads
        elif opt == "--user_spread":
            config_args["user_spread"] = val
        elif opt == "--group_spread":
            config_args["group_spread"] = val
        # Exchange options
        elif opt in ('--exchange-sync',):
            config_args["exchange_sync"] = True
        elif opt == "--exchange_spread":
            config_args["user_exchange_spread"] = val
        

    # Initate logger
    logger = Utils.Factory.get_logger(logger_name)
    
    # specific args for the different sync types:
    if sync_type == 'user':
        config_args["sync_class"] = "ADUserSync"
        # If delete and spread options is given use that value. If
        # not use cereconf.
        config_args["delete_users"] = cereconf.AD_DELETE_USERS
        if delete is not None:
            config_args["delete_users"] = delete

    elif sync_type == 'group':
        config_args["sync_class"] = "ADGroupSync"
        # If delete and spread options is given use given value. If
        # not use cereconf.
        config_args["delete_groups"] = cereconf.AD_DELETE_GROUPS
        if delete is not None:
            config_args["delete_groups"] = delete

    # Run AD sync
    run_sync(logger, host, port, config_args)
    

def run_sync(logger, host, port, config_args):
    """
    Initiate AD sync and run as configured.
    """
    # Initiate and connect to AD agent
    try:
        # Get instance for correct sync class
        ad_domain_admin = cereconf.AD_DOMAIN_ADMIN_USER
        sync_class = getattr(ADSync, config_args.pop('sync_class'))
        ad_sync = sync_class(db, logger, host, port, ad_domain_admin)
    except KeyError, ke:
        logger.error("Missing connection information. Giving up! %s" % ke)
        usage(1)
    except xmlrpclib.ProtocolError, xpe:
        logger.critical("Error connecting to AD service. Giving up!: %s %s" %
                        (xpe.errcode, xpe.errmsg))
        usage(1)
    # Configure sync
    ad_sync.configure(config_args)
    # Run sync
    ad_sync.fullsync()

    
def true_false(arg):
    if arg.lower() in ("t", "true", "y", "yes", ):
        return True
    return False


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


if __name__ == "__main__":
    main()
