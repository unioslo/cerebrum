#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

# $Id$

import getopt
import sys
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _AuthoritativeSystemCode

progname = __file__.split("/")[-1]

__doc__ = """
Usage: %s [options]
   --fnr-src-sys code_str : identifies authoritative system for fnr [required]
   --user-info  : dump user info

This script is intended to grow, adding more options for customizing
both output format, and the selected output fields.

Example:
  %s --fnr-src-sys FS --user-info
""" % (progname, progname)

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
person = Factory.get('Person')(db)

logger = Factory.get_logger("cronjob")

class Fetcher(object):
    def fetch_acinfo(self):
        ac_info = {}
        for row in ac.search():
            ac_info[int(row['account_id'])] = {
                'uname': row['name']
                }

        for row in ac.list_account_home(
                filter_expired=True, include_nohome=True):
            if not ac_info.has_key(int(row['account_id'])):
                continue
            ac_info[int(row['account_id'])]['owner_id'] = int(row['owner_id'])

        ownerid2fnr = {}
        for row in person.list_external_ids(self.fnr_src_sys, id_type=co.externalid_fodselsnr):
            ownerid2fnr[int(row['entity_id'])] = row['external_id']
        
        uname2mailaddr = ac.getdict_uname2mailaddr()

        for ac_id, dta in ac_info.items():
            if ownerid2fnr.has_key(dta.get('owner_id')):
                dta['fnr'] = ownerid2fnr[dta['owner_id']]
            if uname2mailaddr.has_key(dta['uname']):
                dta['email'] = uname2mailaddr[dta['uname']]

        return ac_info

def dump_userinfo(fetcher):
    ac_info = fetcher.fetch_acinfo()
    for account_id, dta in ac_info.items():
        print "%s;%s" % (dta.get('fnr', ''), dta.get('email', ''))

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['help', 'user-info', 'fnr-src-sys='])
    except getopt.GetoptError:
        usage(1)

    fetcher = Fetcher()

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--fnr-src-sys',):
            fetcher.fnr_src_sys = int(_AuthoritativeSystemCode(val))
        elif opt in ('--user-info',):
            dump_userinfo(fetcher)
    if not opts:
        usage(1)

def usage(exitcode=0):
    print >>sys.stderr, __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
