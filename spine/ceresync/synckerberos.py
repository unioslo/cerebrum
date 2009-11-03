#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005, 2006 University of Oslo, Norway
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

try:
    set()
except:
    from sets import Set as set

log = config.logger

changelog_file = config.get('sync','changelog_file', default="/var/lib/cerebrum/lastchangelog.id")

def load_changelog_id():
    local_id = 0
    if os.path.isfile(changelog_file):
        local_id = long(open(changelog_file).read())
        log.debug("Loaded changelog-id %ld", local_id)
    else:
        log.debug("Default changelog-id %ld", local_id)
    return local_id

def save_changelog_id(server_id):
    log.debug("Storing changelog-id %ld", server_id)
    open(changelog_file, 'w').write(str(server_id))

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

def set_encoding_options(options, config):
    options['encode_to'] = 'utf-8'

def main():
    options = config.make_bulk_options() + config.make_testing_options()
    config.parse_args(options)

    incr   = config.getboolean('args', 'incremental', allow_none=True)
    add    = incr or config.getboolean('args', 'add')
    update = incr or config.getboolean('args', 'update')
    delete = incr or config.getboolean('args', 'delete')

    if incr is None:
        log.error("Invalid arguments: You must provide either the --bulk or the --incremental option")
        sys.exit(1)

    log.debug("Setting up CereWS connection")
    try: 
        s = sync.Sync()
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
    set_incremental_options(sync_options, incr, server_id)
    config.set_testing_options(sync_options)
    set_encoding_options(sync_options, config)

    try:
        log.debug("Getting accounts with arguments %s" % str(sync_options))
        accounts = s.get_accounts(**sync_options)
    except:
        log.exception("Exception occured. Aborting")
        sys.exit(1)

    if config.getboolean('args', 'use_test_backend'):
        log.debug("Using testbackend")
        import ceresync.backend.test as kerberosbackend
    else:
        log.debug("Using adsibackend")
        import ceresync.backend.kerberos as kerberosbackend

    user= kerberosbackend.Account()
    user.begin(incr)

    mode = incr and "incr" or "bulk"
    log.debug("Synchronizing users (%s) to changelog_id %ld", mode, server_id)
    log.debug("Options add: %d, update: %d, delete: %d",add,update,delete)
    try:
        for account in accounts:
            if account.posix_uid == None:
                log.debug('no posix_uid on account: %s',account.name)
                continue
            if hasattr(account,'deleted') and account.deleted:
                log.debug('deleted attribute set on account: %s',account.name)
                if delete:
                    user.delete(account)
            else:
                user.add(account, add, update)
    except:
        log.exception("Exception occured, aborting")
        user.close()
        sys.exit(1)
    else:
        user.close(delete)

    if not user.dryrun and add and update and delete:
        save_changelog_id(server_id)

    log.info("Synchronization completed successfully")
        
if __name__ == "__main__":
    main()
