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
import traceback
from getopt import getopt
from sys import argv, exit
from sets import Set as set
import os
import omniORB

log= config.logger

spine_cache= config.conf.get('spine','last_change') or \
             "/var/lib/cerebrum/sync.last_change"

def usage():
    print 'USAGE: %s -i|-b [OPTIONS]' % argv[0]
    print 
    print '        -i|--incremental incremental synchronization'
    print '        -b|--bulk        bulk synchronization. Default is to only delete'
    print '                         accounts. Not add or update'
    print '        -v|--verbose     verbose output'
    print '        -h|--help        show this help and exit'
    print
    print '    The following options only apply on bulk synchronization:'
    print '        -a|--add         add accounts'
    print '        -u|--update      update accounts'
    print '        -d|--delete      delete accounts'
    print '        --no-add         do not add accounts'
    print '        --no-update      do not update accounts'
    print '        --no-delete      do not delete accounts'
    

def main():
    #spine_cache= os.path.join(state_dir, 'spine.cache')
    shortargs= 'abdhiuv'
    longargs= [
        'incremental', 'bulk',
        'help',
        'verbose',
        'add', 'no-add',
        'update', 'no-update',
        'delete', 'no-delete',
    ]
    incr  = False
    add   = False
    update= False
    delete= True

    # Parse parameters
    try:
        opts, args= getopt(argv[1:], shortargs, longargs)
    except Exception,e:
        print e
        usage()
        exit(2)
    # count mandatory args. One (and only one) of -i|-b should be present
    mand_opts= 0
    for o,a in opts:
        if o in ('-h', '--help'):
            usage()
            exit(0)
        elif o in ('-i', '--incremental'):
            incr= True
            mand_opts += 1
        elif o in ('-b', '--bulk'):
            incr= False
            mand_opts += 1
        elif o in ('-a', '--add'):
            add= True
        elif o in ('-u', '--update'):
            update= True
        elif o in ('-d', '--delete'):
            delete= True
        elif o in ('-v', '--verbose'):
            verbose= True
            kerberosbackend.verbose=True
        elif o == '--no-add':
            add= False
        elif o == '--no-update':
            update= False
        elif o == '--no-delete':
            delete= False

    if mand_opts != 1:
        print "One and only one of -i and -b must be present"
        usage()
        exit(2)

    local_id= 0
    if os.path.isfile(spine_cache):
        local_id= long( file(spine_cache).read() )
    try: 
        s= sync.Sync(incr,local_id)
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
    log.info("Local changelog-id: %ld, server changelog-id: %s",local_id,server_id)

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
        except:
            log.exception("Exception occured, aborting")
            user.close()
            exit(1)
        else:
            user.close()
        
        if not user.dryrun:
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
                    user.delete(account, delete)
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

