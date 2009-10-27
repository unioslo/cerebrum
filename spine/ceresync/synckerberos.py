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
import ceresync.backend.kerberos as kerberosbackend
from ceresync import config
import os
import omniORB
from sys import exit

try:
    set()
except:
    from sets import Set as set

log = config.logger

changelog_file = config.get('sync','changelog_file',                                                        default="/var/lib/cerebrum/lastchangelog.id")

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
        #FIXME: This currently doesn't make it any more verbose. It needs to
        # set loglevel for stderr on the logging module.
        verbose = True
        kerberosbackend.verbose = True

    local_id= None
    if os.path.isfile(changelog_file):
        local_id= long( file(changelog_file).read() )
    try: 
        s= sync.Sync()
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        exit(1)
    except:
        log.exception('Unable to connect')
        exit(1)
    server_id= s.get_changelogid()

    log.info("Local id: %ld, server id: %ld",local_id or -1,server_id)
    if local_id is not None and local_id > server_id:
        log.warning("local changelogid is greater than the server's!")

    if incr and local_id == server_id:
        log.info("Nothing to be done.")
        return
    
    user= kerberosbackend.Account()
    user.begin(incr)
    if incr:
        log.info("Synchronizing users (incr) to changelog_id %ld",server_id)
        try:
            processed= set([])
            for account in s.get_accounts(incr_from=local_id, 
                                          encode_to='utf-8'):
                if account.posix_uid == None:
                    continue
                if account.name not in processed:
                    if hasattr(account,'deleted') and account.deleted:
                        user.delete(account)
                    else: 
                        user.add(account)
                    processed.add(account.name)
            user.close()
        except:
            log.exception("Exception occured, aborting")
            user.close()
            exit(1)
        
        if not user.dryrun:
            log.debug("Storing changelog-id")
            file(changelog_file, 'w').write( str(server_id) )
    else:
        log.info("Synchronizing users (bulk) to changelog_id %ld", server_id)
        log.info("Options add: %d, update: %d, delete: %d",add,update,delete)
        try:
            for account in s.get_accounts(encode_to='utf-8'):
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
            exit(1)
        else:
            user.close(delete)
        # If we did a full bulk sync, we should update the changelog-id
        if add and update and delete and not user.dryrun:
            file(changelog_file, 'w').write( str(server_id) )
    
    log.info("Synchronization completed successfully")
        

if __name__ == "__main__":
    main()

