#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

from ceresync import errors
from ceresync import sync
import ceresync.backend.directory as ldapbackend
from ceresync import config
import traceback

def main():
    incr = False
    id = -1
    s = sync.Sync(incr,id)

    # Defaults to fetch configuration from sync.conf
    user = ldapbackend.PosixUser(base=config.sync.get("ldap","user_base"))
    groups = ldapbackend.PosixGroup(base=config.sync.get("ldap","group_base"))
    persons = ldapbackend.Person(base=config.sync.get("ldap","people_base"))

    # Syncronize users
    print "Syncronizing users"
    user.begin(incr)
    try:
        for account in s.get_accounts():
            if account.posix_uid == -1: continue # Possible at all?
            if account.full_name == "": continue # Do not add system users to ou=users
            user.add(account)
    except IOError,e:
        print "Exception %s occured, aborting" % e
    else:
        user.close()

    # Syncronize groups
    print "Syncronizing groups"
    groups.begin(incr)
    try:
        for group in s.get_groups():
            if not group.posix_gid_exists: continue
            groups.add(group)
    except IOError,e:
        print "Exception %s occured, aborting" % e
    else:
        groups.close()

    # Syncronize persons
    print "Syncronizing persons"
    persons.begin(incr)
    try:
        for person in s.get_persons():
            persons.add(person)
    except IOError,e:
        print "Exception %s occured, aborting" % e
    else:
        persons.close()

    print "Final closing"
    s.close()
    print "Done"


if __name__ == "__main__":
    main()

# arch-tag: 7c77c215-87d0-47da-8ccd-a967768a3321
