#!/usr/bin/env  python
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
