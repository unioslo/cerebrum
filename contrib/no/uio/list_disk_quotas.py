#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import mx
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Utils
from Cerebrum.modules.no.uio.DiskQuota import DiskQuota
db = Factory.get('Database')()
co = Factory.get('Constants')(db)

def list_disk_quotas(fname, spread):
    f = Utils.SimilarSizeWriter(fname, "w")
    f.set_size_change_limit(10)
    now = mx.DateTime.now()
    dq = DiskQuota(db)
    for row in dq.list_quotas(spread=spread):
        quota = row['quota']
        if row['override_expiration'] and row['override_expiration'] > now:
            quota = row['override_quota']
        if quota is None:
            quota = ''  # Unlimited
        if row['home']:
            home = row['home']
        else:
            home = "%s/%s" % (row['path'], row['entity_name'])
        f.write("%s:%s:%s\n" % (row['entity_name'], home, quota))
    f.close()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'lt:s:', ['help'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-t',):
            fname = val
        elif opt in ('-s',):
            spread = val
        elif opt in ('-l',):
            list_disk_quotas(fname, co.Spread(spread))
    if not opts:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
    List disk quotas for all users.

    -t target_file
    -s spread
    -l : list disk quotas
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: f117d52b-d39c-468e-b09f-10afe75511aa
