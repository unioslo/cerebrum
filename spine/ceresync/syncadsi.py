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

from sys import exit 
import os
import omniORB

log=config.logger

spine_cache= config.get("spine","last_change") or \
             "/var/lib/cerebrum/sync.last_change"


def main():
    config.parse_args(config.make_bulk_options())

    incr= config.getboolean('args','incremental')
    local_id= 0
    if os.path.isfile(spine_cache):
        local_id= long(file(spine_cache).read())
    try:
        log.info("Connecting to spine-server")
        s = sync.Sync(incr,local_id)
    except omniORB.CORBA.TRANSIENT, e:
        log.error("Unable to connect to spine-server: %s", e)
        exit(1)
    except omniORB.CORBA.COMM_FAILURE, e:
        log.error("Unable to connect to spine-server: %s", e)
        exit(1)
    except errors.LoginError, e:
        log.error("%S", e)
        exit(1)
    server_id= long(s.cmd.get_last_changelog_id())
    log.info("Local id: %d, server_id: %d",local_id,server_id)

    if local_id > server_id:
        log.warning("local changelogid is larger than the server's!")
    elif incr and local_id == server_id:
        log.info("Nothing to be done.")
        s.close()
        return

    # FIXME: URLs from config
    userAD = adsibackend.ADUser("LDAP://OU=Brukere,DC=tymse,DC=itea,DC=ntnu,DC=no")
    groupAD = adsibackend.ADGroup("LDAP://OU=Grupper,DC=tymse,DC=itea,DC=ntnu,DC=no")

    log.debug("Retrieving accounts and groups from spine")
    try: 
        accounts, groups= s.get_accounts(), s.get_groups()
    except:
        log.exception("Exception occured. Aborting")
        s.close()
        exit(1)

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
    if incr or ( not incr and add and update and delete ):
        log.debug("Storing changelog-id %d", server_id) 
        file(spine_cache, 'w').write( str(server_id) )

if __name__ == "__main__":
    main()
