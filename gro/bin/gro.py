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

from Cerebrum.gro.classes import Scheduler
from Cerebrum.gro import Communication
from Cerebrum.gro import Gro


def main():
    com = Communication.get_communication()
    sched = Scheduler.get_scheduler()

    # starting the scheduler
    for i in range(cereconf.GRO_SCHEDULERS):
        print 'starting scheduler thread'
        thread.start_new_thread(sched.run, ())

    # creating server
    server = Gro.GroImpl()

    # binding server to Naming Service
    com.bind_object(server, cereconf.GRO_OBJECT_NAME)

    # starting communication
    print 'starting communication'
    com.start()


if __name__ == '__main__':        
    main()

# arch-tag: 5350ce72-260c-48d9-9d2e-a81daf8f861a
