#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2010 University of Oslo, Norway
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
Generates simple account objects in LDIF format. Spread and base
are mandatory arguments to this script.

This script take the following arguments:

-h, --help : this message
-s, --spread : Which spread to look for 
-f, --filename : LDIF file to write
-b, --base : base DN for the objects
"""

from os.path import join as pj

import sys
import getopt

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules.LDIFutils import entry_string
# from Cerebrum.modules.LDIFutils import *

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


def main():
    filename = pj(cereconf.LDAP['dump_dir'], 'webaccounts.ldif')
    spread = base = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hf:b:s:', [
            'help', 'filename=', 'spread=', 'base='])
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
        elif opt in ('-f', '--filename'):
            filename = val
        elif opt in ('-s', '--spread'):
            str2const = dict()
            for c in dir(co):
                tmp = getattr(co, c)
                str2const[str(tmp)] = tmp
            spread = str2const[val]
        elif opt in ('-b', '--base'):
            base = val
    if not (spread and base):
        print spread, base
        usage(1)

    print "foo"

    f = SimilarSizeWriter(filename, 'w')
    f.max_pct_change = 90
    dump_accounts(f, spread, base)
    f.close()


def dump_accounts(file_handle, spread, base):
    for row in ac.search(spread):
        ac.clear()
        ac.find(row['account_id'])
        dn = "uid=%s,%s" % (row['name'], base)
        file_handle.write(entry_string(dn, {
            'objectClass': ("top", "account"),
            'uid': (row['name'],),
            'userPassword': (ac.get_account_authentication(co.auth_type_md5_crypt),)}))

if __name__ == '__main__':
    main()
