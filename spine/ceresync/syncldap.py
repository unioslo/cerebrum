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
from ceresync.backend import ldapbackend
from ceresync import config
import traceback
from sys import exit
import os

log = config.logger


def main():
    config.parse_args(config.make_bulk_options())

    spine_cache = config.get('spine','last_change') or \
                  "/var/lib/cerebrum/sync.last_change"

    incr   = config.getboolean('args', 'incremental', allow_none=True)
    add    = config.getboolean('args', 'add')
    update = config.getboolean('args', 'update')
    delete = config.getboolean('args', 'delete')

    systems= config.get('ldap', 'sync', default='').split()

    if incr is None:
        log.error("Invalid arguments. You must provide either the --bulk or the --incremental option")
        exit(1)

    local_id= 0
    if os.path.isfile(spine_cache):
        local_id= long( file(spine_cache).read() )
    try:
        log.debug("Connecting to spine-server")
        s = sync.Sync(incr,local_id)
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        exit(1)
    
    server_id= s.cmd.get_last_changelog_id()
    encoding= s.session.get_encoding()
    log.debug("Local id: %ld, server id: %ld", local_id, server_id)
    
    if local_id > server_id:
        log.warning("Local changelogid is greater than the server's!")

    if incr and local_id == server_id:
        log.debug("Nothing to be done.")
        s.close()
        return

    for system in systems:
        log.debug("System %s", system)
        conf_section= 'ldap_%s' % (system,)
        entity= config.get(conf_section, "entity")
        spread= None
        if entity == 'account':
            spread= config.get(conf_section, "spread")
        backend_class= config.get(conf_section, "backend")
        base= config.get(conf_section, "base")
        filter= config.get(conf_section, "filter", default="(objectClass='*')")
        log.debug("filter: %s", filter)

        if spread:
            log.debug("Setting account_spread to %s", spread)
            s.view.set_account_spread(s.tr.get_spread(spread))
        
        log.debug("Initializing %s backend with base %s", backend_class, base)
        backend= getattr(ldapbackend, backend_class)(base=base, filter=filter)
        backend.begin(encoding, incr, add, update, delete)

        log.debug("Adding objects")
        for obj in getattr(s, "get_%ss" % (entity,))():
            backend.add(obj)

        log.debug("Closing %s backend", backend_class)
        backend.close()

    log.debug("Disconnecting cerebrum")
    s.close()

    if incr or ( not incr and add and update and delete ):
        log.debug("Storing changelog-id %ld", server_id)
        file(spine_cache, 'w').write( str(server_id) )

if __name__ == "__main__":
    main()

# arch-tag: 7c77c215-87d0-47da-8ccd-a967768a3321
