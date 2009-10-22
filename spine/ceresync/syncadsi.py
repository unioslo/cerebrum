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
# You should have rec-ived a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

from ceresync import errors
from ceresync import sync
from ceresync import config

import os
import sys
import omniORB

log=config.logger

spine_cache= config.get("sync","last_change", "") or \
             "/var/lib/cerebrum/sync.last_change"


def main():
    options = config.make_bulk_options()
    options.append(config.make_option(
        "--test",
        action="store_true",
        default=True,
        dest="test",
        help="run against the test-backend in stead of the adsi-backend."))
    config.parse_args(options)

    incr= config.getboolean('args','incremental')
    add= config.getboolean('args','add')
    update= config.getboolean('args','update')
    delete= config.getboolean('args','delete')
    test= config.getboolean('args', 'test')
    local_id= 0
    if os.path.isfile(spine_cache):
        local_id= long(file(spine_cache).read())
    try:
        log.debug("Connecting to spine-server")
        s = sync.Sync(incr, local_id)
    except omniORB.CORBA.TRANSIENT, e:
        log.error("Unable to connect to spine-server: %s", e)
        sys.exit(1)
    except omniORB.CORBA.COMM_FAILURE, e:
        log.error("Unable to connect to spine-server: %s", e)
        sys.exit(1)
    except errors.LoginError, e:
        log.error("%S", e)
        sys.exit(1)
    server_id= long(s.cmd.get_last_changelog_id())
    encoding= s.session.get_encoding()
    log.debug("Local id: %ld, server_id: %ld",local_id,server_id)

    if local_id > server_id:
        log.warning("local changelogid is larger than the server's!")
    elif incr and local_id == server_id:
        log.debug("No changes to apply. Quiting.")
        s.close()
        return

    log.debug("Retrieving accounts and groups from spine")
    try: 
        accounts, groups= s.get_accounts(), s.get_groups()
    except:
        log.exception("Exception occured. Aborting")
        s.close()
        sys.exit(1)

    log.debug("Closing connection to spine")
    s.close()

    # FIXME: URLs from config
    if test:
        import ceresync.backend.test as adsibackend
        adsibackend.ADUser = lambda x: adsibackend.Account()
        adsibackend.ADGroup = lambda x: adsibackend.Group()
    else:
        import ceresync.backend.file as adsibackend

    userAD = adsibackend.ADUser( config.get("ad_ldap","userdn") )
    groupAD = adsibackend.ADGroup( config.get("ad_ldap","groupdn") )

    log.debug("Synchronizing accounts")
    userAD.begin(encoding, incr, add, update, delete)
    for account in accounts:
        log.debug("Processing account '%s'", account.name)
        userAD.add(account)
    userAD.close()
    log.debug("Done synchronizing accounts")

    log.debug("Synchronizing groups")
    groupAD.begin(encoding, incr)
    try:
        for group in groups:
            log.debug("Processing group '%s'", group.name)
            groupAD.add(group)
    except IOError,e:
        log.exception("Exception %s occured, aborting", e)
    else:
        groupAD.close()
    log.debug("Done synchronizing groups")
    if incr or ( not incr and add and update and delete ):
        log.debug("Storing changelog-id %ld", server_id) 
        file(spine_cache, 'w').write( str(server_id) )

if __name__ == "__main__":
    main()
