#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005-2019 University of Oslo, Norway
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
"""Dump disk quotas for users with a specific spread to file

Can be further restricted to users on a specific host or disk

"""
import datetime
import getopt
import sys

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import date_compat
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules.disk_quota import DiskQuota


db = Factory.get('Database')()
co = Factory.get('Constants')(db)


def list_quotas(fname, hostname, diskname, spread):
    f = SimilarSizeWriter(fname, "w")
    f.max_pct_change = 10

    disk = Factory.get("Disk")(db)
    if diskname:
        disk.find_by_path(diskname)
        list_disk_quotas(f, disk.entity_id, spread)
    elif hostname:
        host = Factory.get("Host")(db)
        host.find_by_name(hostname)
        for row in disk.list(host_id=host.entity_id, spread=spread):
            list_disk_quotas(f, row['disk_id'], spread)
    else:
        for row in disk.list_traits(co.trait_disk_quota):
            list_disk_quotas(f, row['entity_id'], spread)

    f.close()


def list_disk_quotas(f, disk_id, spread):
    account = Factory.get("Account")(db)
    disk = Factory.get("Disk")(db)
    disk.find(disk_id)

    if not disk.has_quota():
        logger.debug("Skipping %s, no quotas on disk" % disk.path)
        return

    default_quota = disk.get_default_quota()
    logger.debug("Listing quotas on %s" % disk.path)

    if default_quota is None:
        default_quota = ''  # Unlimited
        all_users = False
    else:
        all_users = True

    dq = DiskQuota(db)
    for row in dq.list_quotas(spread=spread, disk_id=disk.entity_id,
                              all_users=all_users):
        quota = row['quota']
        if (row['override_expiration'] and
                 date_compat.get_date(row['override_expiration'])
                 > datetime.date.today()):
            quota = row['override_quota']
        if quota is None:
            quota = default_quota
        home = account.resolve_homedir(
            account_name=row['entity_name'],
            home=row['home'],
            disk_path=row['path'])
        f.write("%s:%s:%s\n" % (row['entity_name'], home, quota))


def main():
    global logger
    logger = Factory.get_logger("cronjob")

    try:
        opts, args = getopt.getopt(sys.argv[1:], 't:s:h:d:', ['help'])
    except getopt.GetoptError:
        usage()

    fname = spread = hostname = diskname = None
    for opt, val in opts:
        if opt in ('--help',):
            usage(0)
        elif opt in ('-t',):
            fname = val
        elif opt in ('-s',):
            spread = co.Spread(val)
            try:
                int(spread)
            except Errors.NotFoundError:
                print "Unknown spread code:", val
        elif opt in ('-d',):
            diskname = val
        elif opt in ('-h',):
            hostname = val

    if not opts or (hostname and diskname) or fname is None or spread is None:
        usage()

    list_quotas(fname, hostname, diskname, spread)


def usage(exitcode=64):
    print """Usage: [options]
List disk quotas for all users.
Options:
    -t OUTPUT-FILE  (required)
    -s SPREAD       (required)
    -h HOST         restrict listing to users on HOST
    -d DISK         restrict listing to users on DISK (path)
"""
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
