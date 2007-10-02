#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005, 2006, 2007 University of Oslo, Norway
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

import cerebrum_path
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum import Utils

import sets
import getopt
import sys

Factory = Utils.Factory

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='update_auth_methods')

ac = Factory.get("Account")(db)

def usage():
    print """Usage: %s <option>

    This program is intended to be used when adding new authentication methods
    to Cerebrum, and you want all existing accounts to get the new auth-method.

    -d | --dry-run: if you only want to show which users whould gotten their passwords set with new hashes
    -v | --verbose: print the users being processed
    -h | --help   : need no explenation
    """ % sys.argv[0]
    sys.exit(1)



def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'vdh',['verbose','dryrun','help'])
    except getopt.GetoptError:
        usage()

    global dryrun, verbose
    dryrun = verbose = False
    for opt,val in opts:
        if opt in ('-d','--dryrun'):
            dryrun = True
        if opt in ('-v','--verbose'):
            verbose = True
        if opt in ('-h','--help'):
            usage()

    if (len(args) > 0):
        for arg in args:
            ac.clear()
            ac.find_by_name(arg)
            update_auth(ac)
    else:
        accounts = ac.list_all_with_type(co.entity_account)
        for account in accounts:
            ac.clear()
            ac.find(account[0])
            update_auth(ac)
            
def update_auth(ac):
    if verbose:
        print "Processing entity %s with username: %s" % (ac.entity_id,ac.get_account_name())
    try:
        password = ac.get_account_authentication(co.auth_type_pgp_offline)
    except Errors.NotFoundError:
        print "Error: %s has no hash pgp_offline" % ac.get_account_name()
        db.rollback()
        return
    cleartext = ac.decrypt_password(co.auth_type_pgp_offline, password)

    ac.set_password(cleartext)
    ac.writedb()
    if dryrun:
        db.rollback()
    else:
        db.commit()

if __name__ == '__main__':
    main()
