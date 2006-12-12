#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""
ad-sync script that can be used with any module that extends ADutilMixIn.ADuserUtil

Usage: [options]
  --url url
  --user_spread spread
  -m ModuleName/ClassName
  --dryrun

Example:
  ad_fullsync.py --url http://172.16.30.128:4321 --user_spread 'account@ad_fag' -m \\
    Cerebrum.modules.no.hiof.ADsync/ADFullUserSync
"""

import getopt
import sys
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Constants import _SpreadCode
from Cerebrum import Utils

db = Utils.Factory.get('Database')()
db.cl_init(change_program="ad_fullsync")
co = Utils.Factory.get('Constants')(db)
ac = Utils.Factory.get('Account')(db)

logger = Utils.Factory.get_logger("cronjob")

def fullsync(user_class_ref, user_spread, url, dryrun=False, delete_objects=False):
    disk_spread = user_spread
    modname, classname = user_class_ref.split("/")
    sync_class = getattr(Utils.dyn_import(modname), classname)

    sync_class(db, co, logger, url=url).full_sync(
        'user', delete_objects, user_spread, dryrun, disk_spread)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'm:', [
            'help', 'user_spread=', 'url=', 'dryrun'])
    except getopt.GetoptError:
        usage(1)

    dryrun = False
    for opt, val in opts:
        if opt in ('--help',):
            usage()
##         elif opt in ('--host',):
##             host = val
##         elif opt in ('--port',):
##             port = int(val)
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--url',):
            url = val
        elif opt in ('-m',):
            fullsync(val, user_spread, url, dryrun=dryrun)
        elif opt == '--user_spread':
            user_spread = _SpreadCode(val)
    if not opts:
        usage(1)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
