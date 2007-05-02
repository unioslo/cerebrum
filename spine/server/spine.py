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

# Spine should be locale-aware since we're doing string.upper etc.
import locale
locale.setlocale(locale.LC_ALL, '')

import cerebrum_path
import cereconf

import sys
import sets
import thread
import traceback

def main(daemon=False):
    print 'Importing all classes...'
    from Cerebrum.spine.server import Communication
    from Cerebrum.spine.server import LockHandler
    from Cerebrum.spine.server import SessionHandler
    from Cerebrum.spine.server import Spine

    com = Communication.get_communication()
    session_handler = SessionHandler.get_handler()
    lock_handler = LockHandler.get_handler()

    # creating server
    print 'Creating server object...'
    server = com.servant_to_reference(Spine.SpineImpl())

    print 'Starting session handler...'
    session_handler.start()

    print 'Starting lock handler...'
    lock_handler.start()

    # Write server object IOR to file
    print 'IOR written to:', cereconf.SPINE_IOR_FILE
    ior = com.orb.object_to_string(server)
    fd = open(cereconf.SPINE_IOR_FILE, 'w')
    fd.write(ior)
    fd.close()

    # Starting communication
    print 'Running server...'
    if daemon: daemonize()
    
    try:
        com.start()
    except KeyboardInterrupt:
        print 'Interrupt caught! Shutting down...'
        pass
    except AssertionError, e:
        raise e # Asserts should make us die
    except:
        traceback.print_exc()
    print 'Stopping lock handler...'
    lock_handler.stop()
    print 'Stopping session handler...'
    session_handler.stop()
    print 'Spine is going down.'


def daemonize():
    import os
    import sys
    import resource

    try:
        pid=os.fork()
        if pid > 0:
            os._exit(0)
        os.chdir("/")
        os.setsid()
        os.umask(022)
        pid=os.fork()
        if pid > 0:
            os._exit(0)
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        if (maxfd == resource.RLIM_INFINITY):
            maxfd=256
        #Try to close all fds
        for fd in range(0, maxfd):
            try:
                os.close(fd)
            except OSError:
                pass
        os.open("/dev/null", os.O_RDWR)
        #Or a logfile
        os.dup2(0,1)
        os.dup2(0,2)
    except OSError, e:
        print >> sys.stderr, "Demonize failed: %s" % e.strerror



def check():
    from Cerebrum.spine.SpineLib import Builder, DatabaseClass
    from Cerebrum.Utils import Factory

    Builder.build_everything()

    db = Factory.get('Database')()

    checked = sets.Set()

    for cls in Builder.get_builder_classes(DatabaseClass.DatabaseClass):
        for table in cls._get_sql_tables():
            if table in checked:
                continue
            checked.add(table)
            if DatabaseClass._table_exists(db, table):
                print '+ exists:', table
            else:
                print '- WARNING table does not exists:', table

    for cls in DatabaseClass.get_sequence_classes():
        if cls.exists(db):
            print '+ exists:', cls.__name__
        else:
            print '- WARNING sequence does not exists:', cls.__name__


if __name__ == '__main__':        
    help = False
    if len(sys.argv) == 2:
        if sys.argv[1] == 'start' or sys.argv[1] == 'debug':
            main()
        elif sys.argv[1] == 'daemon':
            main(daemon=True)
        elif sys.argv[1] == 'check':
            check()
        else:
            help = True
    else:
        help = True
    
    if help:
        print """Spine!

Hello. Try one of these:

%s daemon   start the spine server
%s debug    start the spine server in the foreground
%s check    check all tables
""" % tuple(sys.argv[:1] * 3)

# arch-tag: c5bbf2ca-6dee-49e3-9774-a3f7487b9594
