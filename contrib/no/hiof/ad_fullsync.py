#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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
  -m ModuleName/ClassName
  --dryrun
  --ad-ldap domain_dn (overrides cereconf.AD_LDAP)
  
Example:
  ad_fullsync.py --url http://172.16.30.128:4321 --user_spread 'account@ad_fag' -m \\
    Cerebrum.modules.no.hiof.ADsync/ADFullUserSync
"""

import getopt
import sys
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Constants import _SpreadCode
from Cerebrum import Utils

db = Utils.Factory.get('Database')()
db.cl_init(change_program="ad_fullsync")
co = Utils.Factory.get('Constants')(db)
ac = Utils.Factory.get('Account')(db)

logger = Utils.Factory.get_logger("cronjob")

def fullsync(user_class_ref, user_spread, url, dryrun=False, delete_objects=False,
             ad_ldap=None):
    disk_spread = user_spread

    # Get module and glass name, and use getattr to get a class object.
    modname, classname = user_class_ref.split("/")
    sync_class = getattr(Utils.dyn_import(modname), classname)
    # instantiate sync_class and call full_sync
    sync_class(db, co, logger, url=url, ad_ldap=ad_ldap).full_sync(
        'user', delete_objects, user_spread, dryrun, disk_spread)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'm:', [
            'help', 'user_spread=', 'url=', 'dryrun', 'ad-ldap='])
    except getopt.GetoptError:
        usage(1)

    dryrun = False
    ad_ldap = cereconf.AD_LDAP
    ad_mod = cereconf.AD_DEFAULT_SYNC
    for opt, val in opts:
        if opt in ('--help',):
            usage()
##         elif opt in ('--host',):
##             host = val
##         elif opt in ('--port',):
##             port = int(val)
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--ad-ldap',):
            ad_ldap = val
        elif opt in ('--url',):
            url = val
        elif opt in ('-m',):
            ad_mod = val
        elif opt == '--user_spread':
            user_spread = _SpreadCode(val)
    if not opts:
        usage(1)

    fullsync(ad_mod, user_spread, url, dryrun=dryrun, ad_ldap=ad_ldap)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
