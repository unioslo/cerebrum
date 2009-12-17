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
from ceresync import syncws as sync
from ceresync import config

import os
import sys
import socket

log = config.logger

def load_changelog_id(changelog_file):
    local_id = 0
    if os.path.isfile(changelog_file):
        local_id = long(open(changelog_file).read())
        log.debug("Loaded changelog-id %ld", local_id)
    else:
        log.debug("Default changelog-id %ld", local_id)
    return local_id

def save_changelog_id(server_id, changelog_file):
    log.debug("Storing changelog-id %ld", server_id)
    open(changelog_file, 'w').write(str(server_id))

def set_incremental_options(options, incr, server_id, changelog_file):
    if not incr:
        return

    local_id = load_changelog_id()
    log.debug("Local id: %ld, server_id: %ld", local_id, server_id)
    if local_id > server_id:
        log.warning("local changelogid is larger than the server's!")
    elif incr and local_id == server_id:
        log.debug("No changes to apply. Quiting.")
        sys.exit(0)

    options['incr_from'] = local_id

def set_encoding_options(options, config):
    options['encode_to'] = 'utf-8'

def main():
    options = config.make_bulk_options() + config.make_testing_options()
    config.parse_args(options)
    changelog_file = config.get('sync','changelog_file', 
                                default="/var/lib/cerebrum/lastchangelog.id")

    incr= config.getboolean('args','incremental', allow_none=True)
    add= config.getboolean('args','add')
    update= config.getboolean('args','update')
    delete= config.getboolean('args','delete')
    using_test_backend = config.getboolean('args', 'use_test_backend')

    if incr is None:
        log.error("Invalid arguments. You must provide either the --bulk or the --incremental option")
        sys.exit(1)

    log.debug("Setting up CereWS connection")
    try:
        s = sync.Sync(locking=not using_test_backend)
        server_id = s.get_changelogid()
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        sys.exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        sys.exit(1)
    except socket.error, e:
        log.error("Unable to connect to web service: %s", e)
        sys.exit(1)

    sync_options = {}
    set_incremental_options(sync_options, incr, server_id, changelog_file)
    config.set_testing_options(sync_options)
    set_encoding_options(sync_options, config)

    try:
        log.debug("Getting accounts with arguments %s" % str(sync_options))
        accounts= s.get_accounts(**sync_options)

        log.debug("Getting groups with arguments %s" % str(sync_options))
        groups= s.get_groups(**sync_options)
    except:
        log.exception("Exception occured. Aborting")
        sys.exit(1)

    if using_test_backend:
        log.debug("Using testbackend")
        import ceresync.backend.test as adsibackend
        adsibackend.ADUser = lambda x: adsibackend.Account()
        adsibackend.ADGroup = lambda x: adsibackend.Group()
    else:
        log.debug("Using adsibackend")
        import ceresync.backend.adsi as adsibackend

    userAD = adsibackend.ADUser( config.get("ad_ldap","userdn") )
    groupAD = adsibackend.ADGroup( config.get("ad_ldap","groupdn") )

    log.debug("Synchronizing accounts")
    encoding= 'utf-8'
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

    if incr or (add and update and delete):
        save_changelog_id(server_id, changelog_file)

if __name__ == "__main__":
    main()
