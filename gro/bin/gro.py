#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

import cerebrum_path
import cereconf

import thread

def main():
    print '- importing all classes'
    from Cerebrum.gro.classes import Scheduler
    from Cerebrum.gro import Communication
    from Cerebrum.gro import Gro

    com = Communication.get_communication()
    sched = Scheduler.get_scheduler()

    # starting the scheduler
    print '- starting scheduler'
    for i in range(cereconf.GRO_SCHEDULERS):
        thread.start_new_thread(sched.run, ())

    # creating server
    print '- creating server'
    server = com.servant_to_reference(Gro.GroImpl())

    # binding server to Naming Service
    print '- writing ior to:', cereconf.GRO_IOR_FILE
    ior = com.orb.object_to_string(server)
    fd = open(cereconf.GRO_IOR_FILE, 'w')
    fd.write(ior)
    fd.close()

    # starting communication
    print 'All ok - starting server'
    com.start()


if __name__ == '__main__':        
    main()

# arch-tag: 5350ce72-260c-48d9-9d2e-a81daf8f861a
