#!/usr/bin/env python
#
# Copyright 2007 University of Oslo, Norway
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

# Clean out manually registered affiliation if an equivalent affiliation
# has been registered by an authoritative system.

import cerebrum_path
import cereconf
import getopt
import sys
import getpass
import SpineClient

def usage():
    print """Usage %s
    -u <user> | --user <user>     log in as <user>
    """ % sys.argv[0]

username='bootstrap_account'
try:
    opts,args = getopt.getopt(sys.argv[1:],'u:', ['user'])
    for opt, val in opts:
        if opt in ('-u', '--user'):
            username = val
except getopt.GetoptError:
    usage()
    sys.exit(1)
password=getpass.getpass("%s's password: " % username)

ior_file=cereconf.SPINE_IOR_FILE
cache_dir="/tmp/test-spine-IDL"

spine=SpineClient.SpineClient(ior_file, idl_path=cache_dir).connect()
session = spine.login(username, password)
tr = session.new_transaction()

acc=tr.get_commands().get_account_by_name("bootstrap_account")
print "OK found %s" % acc.get_name()
