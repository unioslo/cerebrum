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
from ceresync import sync
import ceresync.backend.kerberos as kerberosbackend
from ceresync import config
from sets import Set as set
import os
import omniORB

log = config.logger

spine_cache= config.conf.get('spine','last_change') or \
             "/var/lib/cerebrum/sync.last_change"

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
        kerberosbackend.verbose = True

    local_id= 0
    if os.path.isfile(spine_cache):
        local_id= long( file(spine_cache).read() )
    try: 
        log.info("Connecting to spine-server")
        s= sync.Sync(incr,local_id)
    except sync.AlreadyRunningWarning, e:
        log.info(str(e))
        exit(0)
    except sync.AlreadyRunning, e:
        log.warn(str(e))
        exit(1)
    except omniORB.CORBA.TRANSIENT,e:
        log.error('Unable to connect to spine-server: %s',e)
        exit(1)
    except omniORB.CORBA.COMM_FAILURE,e:
        log.error('Unable to connect to spine-server: %s',e)
        exit(1)
    except errors.LoginError, e:
        log.error('%s',e)
        exit(1)
    except:
        log.exception('Unable to connect')
        exit(1)
    server_id= s.cmd.get_last_changelog_id()
    log.info("Local id: %ld, server id: %s",local_id,server_id)
    if long(local_id) > long(server_id):
        log.warning("local changelogid is larger than the server's!")

    if incr and local_id == server_id:
        log.info("Nothing to be done.")
        s.close()
        return

    user= kerberosbackend.Account()
    user.begin(incr)
    try:
        all_accounts= s.get_accounts()
        s.close()
    except:
        log.exception("Exception occured, aborting")
        s.close()
        exit(1)

    if incr:
        log.info("Synchronizing users (incr) to changelog_id %ld",server_id)
        try:
            processed= set([])
            for account in all_accounts:
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
            file(spine_cache, 'w').write( str(server_id) )
    else:
        log.info("Synchronizing users (bulk) to changelog_id %ld", server_id)
        log.info("Options add: %d, update: %d, delete: %d",add,update,delete)
        try:
            for account in all_accounts:
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
            file(spine_cache, 'w').write( str(server_id) )
    
    log.info("Synchronization completed successfully")
        

if __name__ == "__main__":
    main()

