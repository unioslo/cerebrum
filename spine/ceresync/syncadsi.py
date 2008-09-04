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
from ceresync import config
import ceresync.backend.adsi as adsibackend

log=config.logger

def main():
    incr = False
    id = -1
    s = sync.Sync(incr,id)

    # FIXME: URLs from config
    userAD = adsibackend.ADUser("LDAP://OU=Brukere,DC=tymse,DC=itea,DC=ntnu,DC=no")
    groupAD = adsibackend.ADGroup("LDAP://OU=Grupper,DC=tymse,DC=itea,DC=ntnu,DC=no")

    log.debug("Retrieving accounts and groups from spine")
    accounts, groups= s.get_accounts(), s.get_groups()
    log.debug("Closing connection to spine")
    s.close()

    log.info("Synchronizing accounts")
    userAD.begin(incr)
    for account in accounts:
        log.debug("Processing account '%s'", account.name)
        userAD.add(account)
    userAD.close()
    log.info("Done synchronizing accounts")

    log.info("Synchronizing groups")
    groupAD.begin(incr)
    try:
        for group in groups:
            log.debug("Processing group '%s'", group.name)
            groupAD.add(group)
    except IOError,e:
        log.exception("Exception %s occured, aborting", e)
    else:
        groupAD.close()
    log.info("Done synchronizing groups")

if __name__ == "__main__":
    main()
