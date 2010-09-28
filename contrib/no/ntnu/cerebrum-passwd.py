#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

import cerebrum_path
import getopt
from Cerebrum.Utils import Factory
from getpass import getpass
import sys

db=Factory.get("Database")()
db.cl_init(change_program="set_password")
ac=Factory.get("Account")(db)


def set_passwd_interactive(user, admin_password):
    ac.find_by_name(user)

    pass1 = getpass("Password:")
    pass2 = getpass("Repeat password:")

    assert pass1 == pass2

    if admin_password:
        ac.set_admin_password(pass1)
    else:
        ac.set_password(pass1)

    ac.write_db()

def copy_to_admin_passwd(user):
    ac.find_by_name(user)
    
    pw = ac.get_account_authentication(ac.const.auth_type_md5_crypt)
    ac.affect_auth_types(ac.const.auth_type_admin_md5_crypt)
    ac.populate_authentication_type(ac.const.auth_type_admin_md5_crypt, pw)
    ac.write_db()

def check_passwd(user, admin_password):
    ac.find_by_name(user)
    
    if admin_password:
        verify_auth = ac.verify_admin_auth
    else:
        verify_auth = ac.verify_auth

    pass1 = getpass("Password:")
    
    if verify_auth(pass1):
        print "OK"
    else:
        print "FAILED"

opts,args = getopt.getopt(sys.argv[1:], 'act')

copy_passwd = False
test_passwd = False
admin_password = False
for opt, val in opts:
    if opt=='-a':
        admin_password = True
    if opt=='-c':
        copy_passwd = True
    if opt=='-t':
        test_passwd = True
        
if copy_passwd:
    copy_to_admin_passwd(args[0])
elif test_passwd:
    check_passwd(args[0], admin_password)
else:
    set_passwd_interactive(args[0], admin_password)

db.commit()
