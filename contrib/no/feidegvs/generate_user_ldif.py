#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

import getopt
import sys
import os

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory, latin1_to_iso646_60,SimilarSizeWriter

targ2prim = {}
aid2addr = {}


def get_mail_prim():
    mail_prim = Email.EmailPrimaryAddressTarget(db)
    for row in mail_prim.list_email_primary_address_targets():
        targ2prim[int(row['target_id'])] = int(row['address_id'])


def get_mail_addr():
    mail_dom = Email.EmailDomain(db)
    mail_addr = Email.EmailAddress(db)
    for row in mail_addr.list_email_addresses_ext():
        a_id, t_id = int(row['address_id']), int(row['target_id'])
        lp, dom = row['local_part'], row['domain']
        aid2addr[a_id] = dom

def list_users(f):
    f.write(cereconf.LDAP_BASE_OBJ)
    
    user = Factory.get('Account')(db)
    et = Email.EmailTarget(db)
    #pos = pu.list_extended_posix_users_test(getattr(co,'auth_type_md5_crypt'),
    #                                        spreads,include_quarantines=1)
    for row in ac.list():
        user.clear()
        user.find(row['account_id'])
        uname = user.get_account_name()
        passwd = user.get_account_authentication(co.auth_type_md5_crypt)
        sas_user = None
        et.clear()
        try:
            et.find_by_entity(row['account_id'])
        except Errors.NotFoundError:
            print "WARNING! Couldn't find info for %s. Skipping." % uname
            continue

        addr = None
        
        if targ2prim.has_key(et.email_target_id):
            addr = aid2addr[targ2prim[et.email_target_id]]
        else:
            print "WARNING! Couldn't find %s's primary address." % uname
            continue
        uname = "%s@%s" % (uname, addr)
        txt = """
dn: uid=%s,ou=users,%s
objectClass: top
objectClass: shadowAccount
uid: %s
userPassword: {crypt}%s
\n""" % (uname, cereconf.LDAP_BASE, uname, passwd)
        f.write(txt)

def usage():
    print """Usage: generate_user_ldif.py
    -v, --verbose : Show extra information.
    -f, --file    : File to parse.
    """


def main():
    global db, ac, co

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vf:', ['verbose','file'])
    except getopt.GetoptError:
        usage()
        
    verbose = 0
    fname = None

    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-f', '--file'):
            fname = val

    if fname is None:
        usage()

    db = Factory.get('Database')()
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    f = file(fname, 'w')
    get_mail_prim()
    get_mail_addr()
    list_users(f)
    f.close()


if __name__ == '__main__':
    main()

# arch-tag: 5a5f5159-0363-42f1-ae2d-6d6c4b49ed1f
