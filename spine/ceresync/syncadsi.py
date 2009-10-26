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
from ceresync import syncws as sync
from ceresync import config

import os
import sys
import socket

log=config.logger

last_change_file = config.get("sync","last_change", "/var/lib/cerebrum/sync.last_change")

def load_changelog_id():
    local_id = 0
    if os.path.isfile(last_change_file):
        local_id = long(open(last_change_file).read())
        log.debug("Loaded changelog-id %ld", local_id)
    else:
        log.debug("Default changelog-id %ld", local_id)
    return local_id

def save_changelog_id(server_id):
    log.debug("Storing changelog-id %ld", server_id)
    open(last_change_file, 'w').write(str(server_id))

def set_incremental_options(options, incr, server_id):
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

def set_testing_options(options, config):
    args = ('account_xml_in', 'account_xml_out', 'group_xml_in',
            'group_xml_out', 'ou_xml_in', 'ou_xml_out',
            'person_xml_in', 'person_xml_out', 'alias_xml_in',
            'alias_xml_out', 'homedir_xml_in', 'homedir_xml_out')

    for arg in args:
        options[arg] = config.get('args', arg, allow_none=True)

def set_encoding_options(options, config):
    options['encode_to'] = 'utf-8'

def main():
    config.parse_args(config.make_bulk_options(include_testing_options=True))

    incr= config.getboolean('args','incremental', allow_none=True)
    add= config.getboolean('args','add')
    update= config.getboolean('args','update')
    delete= config.getboolean('args','delete')

    if incr is None:
        log.error("Invalid arguments. You must provide either the --bulk or the --incremental option")
        exit(1)

    log.debug("Setting up CereWS connection")
    try:
        s = sync.Sync()
        server_id= s.get_changelogid()
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        exit(1)
    except socket.error, e:
        log.error("Unable to connect to web service: %s", e)
        sys.exit(1)

    sync_options = {}
    set_incremental_options(sync_options, incr, server_id)
    set_testing_options(sync_options, config)
    set_encoding_options(sync_options, config)

    try:
        log.debug("Getting accounts with arguments %s" % str(sync_options))
        accounts= s.get_accounts(**sync_options)

        log.debug("Getting groups with arguments %s" % str(sync_options))
        groups= s.get_groups(**sync_options)
    except:
        log.exception("Exception occured. Aborting")
        sys.exit(1)

    # FIXME: URLs from config
    if config.getboolean('args', 'use_test_backend'):
        log.debug("Using testbackend")
        import ceresync.backend.test as adsibackend
        adsibackend.ADUser = lambda x: adsibackend.Account()
        adsibackend.ADGroup = lambda x: adsibackend.Group()
    else:
        log.debug("Using adsibackend")
        import ceresync.backend.file as adsibackend

    userAD = adsibackend.ADUser( config.get("ad_ldap","userdn") )
    groupAD = adsibackend.ADGroup( config.get("ad_ldap","groupdn") )

    log.debug("Synchronizing accounts")
    encoding= 'iso-8859-1'
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
        save_changelog_id(server_id)

if __name__ == "__main__":
    main()
