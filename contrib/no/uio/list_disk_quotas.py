#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import mx
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.DiskQuota import DiskQuota
db = Factory.get('Database')()

def list_disk_quotas():
    now = mx.DateTime.now()
    dq = DiskQuota(db)
    for row in dq.list_quotas():
        quota = row['quota']
        if row['override_expiration'] and row['override_expiration'] > now:
            quota = row['override_quota']
        if quota is None:
            quota = ''  # Unlimited
        if row['home']:
            home = row['home']
        else:
            home = "%s/%s" % (row['path'], row['entity_name'])
        print "%s:%s:%s" % (row['entity_name'], home, quota)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'l', ['help'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-l',):
            list_disk_quotas()
    if not opts:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
    List disk quotas for all users.

    -l : list disk quotas
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
