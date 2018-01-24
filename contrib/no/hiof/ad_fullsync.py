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
ad-sync script that can be used with any module that extends ADutilMixIn.ADuserUtil

Usage: [options]
  --url url
  --user_spread spread
  --group_spread spread (only given if group sync is to be performed)
  -m ModuleName/ClassName
  --dryrun (report changes that would have been done without --dryrun)
  --delete (this option ensures deleting superfluous groups. default
            is _not_ to delete groups)
  --ad-ldap domain_dn (overrides cereconf.AD_LDAP)
  
Example:
  ad_fullsync.py --url http://172.16.30.128:4321 --user_spread 'account@ad_fag' -m \\
    Cerebrum.modules.no.hiof.ADsync/ADFullUserSync

  ad_fullsync.py --url https://dc-hiof-test.uio.no:8000 --group_spread 'group@ad_stud' \\
  --ad-ldap 'DC=test,DC=hiof,DC=no' -m Cerebrum.modules.no.hiof.ADsync/ADFullGroupSync \\
  --logger-level DEBUG --logger-name console
"""

import getopt
import sys
import xmlrpclib
import cerebrum_path
import cereconf
from Cerebrum.Constants import _SpreadCode
from Cerebrum import Utils

db = Utils.Factory.get('Database')()
db.cl_init(change_program="ad_fullsync")
co = Utils.Factory.get('Constants')(db)
ac = Utils.Factory.get('Account')(db)


def fullsync(user_class_ref, url, user_spread=None, group_spread=None,
             dryrun=False, delete_objects=False, ad_ldap=None):
    # Get module and glass name, and use getattr to get a class object.
    modname, classname = user_class_ref.split("/")
    sync_class = getattr(Utils.dyn_import(modname), classname)
    # Group or user sync?
    sync_type='user'
    spread=user_spread
    if group_spread:
        sync_type = 'group'
        spread=group_spread
    # Different logger for different adsyncs
    logger_name = "ad_" + sync_type + "sync_" + str(spread).split('@ad_')[1]
    logger = Utils.Factory.get_logger(logger_name)
    # Catch protocolError to avoid that url containing password is
    # written to log
    try:
        # instantiate sync_class and call full_sync
        sync_class(db, co, logger, url=url, ad_ldap=ad_ldap).full_sync(
            sync_type, delete_objects, spread, dryrun, user_spread)
    except xmlrpclib.ProtocolError, xpe:
        logger.critical("Error connecting to AD service. Giving up!: %s %s" %
                        (xpe.errcode, xpe.errmsg))


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'm:', [
            'help', 'user_spread=', 'url=', 'dryrun', 'ad-ldap=',
            'delete', 'group_spread=', 'logger-level=', 'logger-name='])
    except getopt.GetoptError:
        usage(1)

    dryrun = False
    delete_objects = False
    user_spread = None
    group_spread = None
    ad_ldap = cereconf.AD_LDAP
    ad_mod = cereconf.AD_DEFAULT_SYNC
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--delete',):
            delete_objects = True
        elif opt in ('--ad-ldap',):
            ad_ldap = val
        elif opt in ('--url',):
            url = val
        elif opt in ('-m',):
            ad_mod = val
        elif opt == '--user_spread':
            user_spread = _SpreadCode(val)
        elif opt == '--group_spread':
            group_spread = _SpreadCode(val)
        
    fullsync(ad_mod, url, user_spread, group_spread, dryrun=dryrun,
             delete_objects=delete_objects, ad_ldap=ad_ldap)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
