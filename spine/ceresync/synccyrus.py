#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005, 2006, 2007 University of Oslo, Norway
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

import sync
import backend.cyrus
import config
from sets import Set as set
import os
log = config.logger

spine_cache= "/var/cache/cerebrum/spine_cyrus_lastupdate"

def main():
    config.parse_args(config.make_bulk_options())

    incr   = config.getboolean('args', 'incremental', allow_none=True)
    add    = config.getboolean('args', 'add')
    update = config.getboolean('args', 'update')
    delete = config.getboolean('args', 'delete')

    if incr is None:
        log.error("Invalid arguments: You must provide either the --bulk or the --incremental option")
        exit(1)

    if config.get('args', 'verbose'):
        verbose = True
        backend.cyrus.verbose = True

    local_id= 0
    if os.path.isfile(spine_cache):
        local_id= long( file(spine_cache).read() )
    print "Local changelog-id:",local_id
    s= sync.Sync(incr,local_id)
    server_id= s.cmd.get_last_changelog_id()
    print "Server changelog-id:",server_id

    if local_id >= server_id:
        print "Nothing to be done."
        return

    cyrus = backend.cyrus.Account()
    cyrus.begin(incr)
    print "Fetch all accounts from Spine"
    try: all_accounts= list(s.get_accounts())
    except Exception,e:
        print "Exception '%s' occured, aborting" % e
        s.close()
        exit(1)
    s.close()
    print "Done fetching accounts"

    if incr:
        print "Synchronizing users (incr) to changelog",server_id
        try:
            processed= set([])
            for account in all_accounts:
                if account.name not in processed:
                    cyrus.add(account)
                    processed.add(account.name)
        except Exception,e:
            print "Exception '%s' occured, aborting" % e
            cyrus.close()
            exit(1)
        else:
            cyrus.close()
        
        file(spine_cache, 'w').write( str(server_id) )
    else:
        print "Synchronizing users (bulk) to changelog",server_id
        print "Options:",add and "add" or "", update and "update" or "",
        print delete and "delete" or ""
        try:
            for account in all_accounts:
                cyrus.add(account)
        except Exception, e:
            print "Exception %s occured, aborting" % e
            cyrus.close()
            exit(1)
        else:
            cyrus.close(delete)
        # If we did a full bulk sync, we should update the changelog-id
        if add and update and delete:
            file(spine_cache, 'w').write( str(server_id) )
    
    print "Synchronization completed successfully"
        

if __name__ == "__main__":
    main()

