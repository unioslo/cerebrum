#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2023 University of Oslo, Norway
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
Compare Active Directory LDAP dump to Cerebrum.

Examples
--------
To dump data from AD, do something like:
::

    DN="DC=w2k3test,DC=uio,DC=no"
    ATTRS="cn,displayName,memberOf,homeDirectory,sAMAccountName,homeDrive,givenName,sn,profilePath,mail"
    ldifde -d$DN -r "(&(objectClass=user)(objectCategory=user))" \\
        -p Subtree -l $ATTRS -f userdump.ldp

To compare the dump with Cerebrum-data:
::

    python ad_cmp.py --old userdump.ldp.old --new userdump.ldp.new \\
        --old-dn $DN --new-dn $DN2 --attrs $ATTRS -c


Options
-------
--old-dn dn
    Use with --new-dn if the servers DNs differs

--new-dn dn
    Use with --old-dn if the servers DNs differs

--old fname
    old dump file

--new fname
    new dump file

--attrs
    sAMAccountName,homeDirectory...

-c
    run comparison
"""
from __future__ import print_function

import getopt
import sys
import re


def parse_ldif(fname, filter_dn):
    ret = {}
    tmp = {}
    attr_re = re.compile(r'^(.*?): (.*)')
    for line in file(fname):
        if line.startswith("dn: "):
            dn = line[4:].strip()
            if filter_dn:
                dn = dn[:dn.find(filter_dn)]
            tmp = {}
            ret[dn] = tmp
        else:
            m = attr_re.search(line)
            if m:
                tmp.setdefault(m.group(1), []).append(m.group(2))
    return ret


def run_comparison(old_dta, new_dta, attrs, ignore_case_attrs):
    """Compare attributes specified in attrs for AD data in old_dta
    and new_dta. if ignore_case_attrs is specified ignire case
    differences for those attributes.
    """
    tmp = old_dta.keys()
    tmp.sort()
    for dn in tmp:
        o = old_dta[dn]
        n = new_dta.get(dn)
        if n is None:
            print("DN: %s only in old" % dn)
            continue
        for a in attrs:
            oa = [x.strip() for x in o.get(a, [])]
            na = [x.strip() for x in n.get(a, [])]
            if a in ignore_case_attrs:
                oa = [x.lower() for x in oa]
                na = [x.lower() for x in na]
            oa.sort()
            na.sort()
            if oa != na:
                print("DN: %s attribute %s diffs: %s -> %s" % (dn, a, oa, na))

        del(new_dta[dn])
    if new_dta:
        print("The following entries were only in new: %s" % new_dta.keys())


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'c', ['help', 'old-dn=',
                                                       'new-dn=', 'old=',
                                                       'new=', 'attrs=',
                                                       'ignore-case-attrs='])
    except getopt.GetoptError:
        usage(1)

    old_dn = new_dn = None
    ignore_case_attrs = []
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--old-dn',):
            old_dn = val
        elif opt in ('--new-dn',):
            new_dn = val
        elif opt in ('--old',):
            old_fname = val
        elif opt in ('--new',):
            new_fname = val
        elif opt in ('--attrs',):
            attrs = val.split(",")
        elif opt in ('--ignore-case-attrs',):
            ignore_case_attrs = val.split(",")
    if not opts:
        usage(1)
    for opt, val in opts:
        if opt in ('-c',):
            run_comparison(parse_ldif(old_fname, old_dn),
                           parse_ldif(new_fname, new_dn),
                           attrs, ignore_case_attrs)


def usage(exitcode=0):
    print(__doc__)
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
