#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005, 2006 University of Oslo, Norway
#
# This filebackend is part of Cerebrum.
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

import ceresync.errors
import ceresync.sync
import ceresync.backend.file as filebackend
import ceresync.config
import traceback
import re
import sys

name_regex=re.compile("^[A-Za-z0-9_]+$")
def check_account(account):
    if not name_regex.match(account.name):
        return "Bad accountname"
    if not account.posix_uid >= 1000:
        return "Bad uid (%s)" % account.posix_uid
    if not account.posix_gid >= 1000:
        return "Bad gid (%s)" % account.posix_gid
    if account.passwd == "":
        account.passwd = "x"
    return None

def check_group(group):
    if not name_regex.match(group.name):
        return "Bad groupname"
    if not group.posix_gid >= 1000:
        return "Bad gid (%s)" % group.posix_gid
    for n in group.members:
        if not name_regex.match(n):
            group.members.remove(n)
    return None

def main():
    incr = False
    id = -1
    s = sync.Sync(incr,id)

    accounts = filebackend.Account()
    groups = filebackend.Group()

    print "Syncronizing accounts"
    accounts.begin(incr)
    try:
        for account in s.get_accounts():
            fail = check_account(account)
            if not fail: 
                accounts.add(account)
            else:
                print >>sys.stderr, "Skipping account", account.name, fail
    except IOError,e:
        print "Exception %s occured, aborting" % e
    else:
        accounts.close()

    print "Syncronizing groups"
    groups.begin(incr)
    try:
        for group in s.get_groups():
            fail = check_group(group)
            if not fail:
                groups.add(group)
            else:
                print >>sys.stderr, "Skipping group", group.name, fail
    except IOError,e:
        print "Exception %s occured, aborting" % e
    else:
        groups.close()

if __name__ == "__main__":
    main()
