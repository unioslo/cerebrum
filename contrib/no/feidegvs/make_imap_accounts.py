#!/usr/bin/env python
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
import cyruslib
import string

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory

SUDO_CMD = "/usr/bin/sudo"
imapconn = None
imaphost = None
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

def cyrus_subscribe(uname, domain, server, action="create"):
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'subscribeimap',
           action, server, uname, domain];
    cmd = ["%s" % x for x in cmd]
    errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    if not errnum:
        return True
    print "ERROR: %s returned %i" % (cmd, errnum)
    return False

def connect_cyrus():
    global imapconn, imaphost
    if imapconn is None:
        imaphost = cereconf.CYRUS_HOST
        imapconn = cyruslib.CYRUS(host = cereconf.CYRUS_HOST)
        pw = db._read_password(cereconf.CYRUS_HOST, cereconf.CYRUS_ADMIN)
        #print pw, cereconf.CYRUS_HOST, cereconf.CYRUS_ADMIN, imapconn.auth

        if imapconn.login(cereconf.CYRUS_ADMIN, pw) == 0:
            raise Errors.DatabaseException("Connection to IMAP server %s failed" % host)
    return imapconn


def cyrus_create(uname):
    lp, dom = string.split(uname, '@')
    try:
        cyradm = connect_cyrus()
    except Errors.DatabaseException, e:
        print "ERROR: cyrus_create: " + str(e)
        return False
    for sub in ("", ".spam", ".Sent", ".Drafts", ".Trash"):
        res, list = cyradm.m.list ('user.', pattern='%s%s' % (uname, sub))
        if res == 'OK' and list[0]:
            continue
        res = cyradm.m.create('user.%s%s@%s' % (lp, sub, dom))
        if res[0] <> 'OK':
            print "ERROR: IMAP create %s%s@%s failed: %s" % (
                lp, sub, dom, res[1])
            return False
    # restrict access to INBOX.spam.  the user can change the
    # ACL to override this, though.
    cyradm.m.setacl("user.%s.spam" % uname, uname, "lrswipd")
    # we don't care to check if the next command runs OK.
    # almost all IMAP clients ignore the file, anyway ...
    cyrus_subscribe(lp, dom, imaphost)
    return True


def itarate_mail_targets():
    et = Email.EmailTarget(db)
    ac = Factory.get('Account')(db)
    user = Factory.get('Account')(db)

    for row in ac.list():
        user.clear()
        user.find(row['account_id'])
        uname = user.get_account_name()
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
        
        #print "   cyrus_create(%s)" % uname
        cyrus_create(uname)
        #sys.exit(0)

def main():
    global db, co
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    get_mail_prim()
    get_mail_addr()
    itarate_mail_targets()


if __name__ == '__main__':
    main()

# arch-tag: 23739f76-8a8d-4251-bd99-046628da0203
