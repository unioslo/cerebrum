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

import errors
import sync
import config
import adsi

def main():
    incr = False
    id = -1
    s = sync.Sync(incr,id)

    # FIXME: URLs from config
    userAD = adsi.ADUser("LDAP://OU=Brukere,DC=twin,DC=itea,DC=ntnu,DC=no")
    groupAD = adsi.ADGroup("LDAP://OU=Grupper,DC=twin,DC=itea,DC=ntnu,DC=no")

    # Syncronize users
    print "Syncronizing users"
    userAD.begin(incr)
    for account in s.get_accounts():
        userAD.add(account)
    userAD.close()

    # Syncronize groups
    print "Syncronizing groups"
    groupAD.begin(incr)
    try:
        for group in s.get_groups():
            groupAD.add(group)
    except IOError,e:
        print "Exception %s occured, aborting" % e
    else:
        groupAD.close()

    print "Final closing"
    s.close()
    print "Done"


if __name__ == "__main__":
    main()

# arch-tag: 7c77c215-87d0-47da-8ccd-a967768a3321
