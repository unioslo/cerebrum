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

import cerebrum_path
import cereconf

import thread

def main():
    print '- importing all classes'
    from Cerebrum.spine.SpineLib import Scheduler
    from Cerebrum.spine.server import Communication
    from Cerebrum.spine.server import Spine

    com = Communication.get_communication()
    sched = Scheduler.get_scheduler()

    # starting the scheduler
    print '- starting scheduler'
    for i in range(cereconf.SPINE_SCHEDULERS):
        thread.start_new_thread(sched.run, ())

    # creating server
    print '- creating server'
    server = com.servant_to_reference(Spine.SpineImpl())

    # binding server to ior file
    print '- writing ior to:', cereconf.SPINE_IOR_FILE
    ior = com.orb.object_to_string(server)
    fd = open(cereconf.SPINE_IOR_FILE, 'w')
    fd.write(ior)
    fd.close()

    # starting communication
    print 'All ok - starting server'
    com.start()


if __name__ == '__main__':        
    main()

# arch-tag: c5bbf2ca-6dee-49e3-9774-a3f7487b9594
