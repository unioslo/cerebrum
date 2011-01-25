#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

"""Generate an LDIF-file with automount information
"""

import sys
import getopt

import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import ldapconf
from Cerebrum.modules.LDIFutils import entry_string
from Cerebrum.modules.LDIFutils import ldif_outfile
from Cerebrum.modules.LDIFutils import container_entry_string

def generate_automount(f):
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    d = Factory.get('Disk')(db)
    h = Factory.get('Host')(db)

    hosts = []
    d_list = d.list(filter_expired=True)
    for row in d_list:
        if row[0] <= 0:
            continue
        if row[3] not in hosts:
            hosts.append(row[3])
    h_id2name = {}
    # TBD: any point in filtering? does it just consume more resources than
    # listing all hosts? 
    for row in h.search(host_id=hosts):
        h_id2name[row['host_id']] = row['name']

    paths = {}
    for d in d_list:
        if d[0] <= 0:
            continue
        path = d[4].split('/')
        if not ((path[1], path[2])) in paths.keys():
            paths[(path[1], path[2])] = d[3]

    f.write(container_entry_string('AUTOMOUNT_MASTER'))

    for p in paths:
        entry = {}
        entry['objectClass'] = ['top','automount']
        dn = "cn=%s,%s" % ("/%s/%s" % (p[0], p[1]), 
                          ldapconf('AUTOMOUNT_MASTER', 'dn', None))
        entry['automountInformation'] = "ldap:auto.%s-%s,%s" %(p[1],p[0],
                                                              ldapconf('AUTOMOUNT', 'dn', None))
        f.write(entry_string(dn, entry))

        entry = {}
        entry['objectClass'] = ['top','automountMap']
        dn = "ou=auto.%s-%s,%s" % (p[1], p[0], 
                                   ldapconf('AUTOMOUNT', 'dn', None))
        f.write(entry_string(dn, entry))

        entry = {}
        entry['objectClass'] = ['top','automount']
        dn = "cn=/,ou=auto.%s-%s,%s" % (p[1], p[0], 
                                         ldapconf('AUTOMOUNT', 'dn', None))
        dns = 'uio.no'
        if p[0] == 'ifi':
            dns = 'ifi.uio.no'
        entry['automountInformation'] = "-fstype=nfs,tcp,vers=3,rw,intr,hard,nodev,nosuid,noacl %s.%s:/%s/%s/&" % (h_id2name[paths[p]], dns, p[0], p[1])
        f.write(entry_string(dn, entry))

def main():
    global logger
    logger = Factory.get_logger("cronjob")
    ofile = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ho:",("help","outfile="))
    except getopt.GetoptError, e:
        usage(str(e))

    if args:
        usage("Invalid arguments: " + " ".join(args))
    for opt, val in opts:
        if opt in ("-o", "--outfile"):
            ofile = val
        else:
            usage()

    output_encoding = "utf-8"
    f = ldif_outfile('AUTOMOUNT', ofile)
    f.write(container_entry_string('AUTOMOUNT'))
    generate_automount(f)
    f.close()


def usage(err=0):
    if err:
        print >>sys.stderr, err
    print >>sys.stderr, __doc__
    sys.exit(bool(err))


if __name__ == '__main__':
    main()
