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
import ceresync.backend.kerberos kerberosbackend
from ceresync import config
import traceback
from getopt import getopt
from sys import argv, exit
from sets import Set as set
import os

spine_cache= "/var/cache/cerebrum/spine_lastupdate"

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
    print "Local changelog-id:",local_id
    s= sync.Sync(incr,local_id)
    server_id= s.cmd.get_last_changelog_id()
    print "Server changelog-id:",server_id

    if incr and local_id == server_id:
        print "Nothing to be done."
	s.close()
        return

    user= kerberosbackend.Account()
    user.begin(incr)
    try:
	all_accounts= list(s.get_accounts())
	s.close()
    except Exception,e:
        print "Exception '%s' occured, aborting" % e
        s.close()
        exit(1)

    if incr:
        print "Synchronizing users (incr) to changelog",server_id
        try:
            processed= set([])
            for account in all_accounts:
                if account.posix_uid == None:
                    continue
                if account.name not in processed:
                    user.add(account)
                    processed.add(account.name)
        except Exception,e:
            print "Exception '%s' occured, aborting" % e
            user.close()
            exit(1)
        else:
            user.close()
        
        if not user.dryrun:
            file(spine_cache, 'w').write( str(server_id) )
    else:
        print "Synchronizing users (bulk) to changelog",server_id
        print "Options:",add and "add" or "", update and "update" or "",
        print delete and "delete" or ""
        try:
            for account in all_accounts:
                if account.posix_uid == None:
                    continue
                user.add(account, add, update)
        except Exception, e:
            print "Exception %s occured, aborting" % e
            user.close()
            exit(1)
        else:
            user.close(delete)
        # If we did a full bulk sync, we should update the changelog-id
        if add and update and delete and not user.dryrun:
            file(spine_cache, 'w').write( str(server_id) )
    
    print "Synchronization completed successfully"
        

if __name__ == "__main__":
    main()

