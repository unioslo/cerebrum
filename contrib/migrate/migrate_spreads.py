#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 University of Oslo, Norway
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
"""Migrate users from one spread, to another spread"""

# TODO: Generalize
# TODO: Multiprocess this. It takes forever for large amounts of users.

import getopt
import sys

import cerebrum_path
import cereconf
from mx.DateTime import now

from Cerebrum.Utils import Factory

def mangle(from_spread, to_spread, file,
           commit=False, events=False,
           disable_requests=True):
    print('%s: Starting to migrate spreads' % str(now()))

    if not events:
        cereconf.CLASS_CHANGELOG = \
                filter(lambda x: 'Event' not in x, cereconf.CLASS_CHANGELOG)
    db = Factory.get('Database')()
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    db.cl_init(change_program='migrate_spreads')
    
    from_spread = co.Spread(from_spread)
    to_spread = co.Spread(to_spread)


    # TODO: You whom are reading this in the future should make this more
    # generic!  You can for example replace 'ac' with 'locals()[object]', where
    # 'object' defines the object to act on. Then you should use __setattr__ to
    # replace the appropriate bofhd_request-generating method. If you dare!
    if disable_requests:
        ac._UiO_order_cyrus_action = lambda *args, **kwargs: True
    
    f = open(file, 'r')
    for line in f:
        ac.clear()
        ac.find_by_name(line.strip())
        ac.delete_spread(from_spread)
        ac.add_spread(to_spread)
        ac.write_db()
        print('%-9s: removed %s, added %s' % \
                (line.strip(), str(from_spread), str(to_spread)))
    f.close()

    if commit:
        db.commit()
        print 'Committed all changes'
    else:
        db.rollback()
        print 'Rolled back all changes'
    print('%s: Finished migrating spreads' % str(now()))


def usage(code=0):
    print('Usage: migrate_spreads.py -f IMAP@uio -t exchange_acc@uio -d '
            '-u <name>')
    print('    --from      (-f) spread to migrate from')
    print('    --to        (-t) spread to migrate to')
    print('    --commit    (-c) Commit-mode on')
    print('    --dis-reqs  (-d) Disable bofhd requests?')
    print('    --log-event (-e) Log events for spread removal and addition')
    print('    --users     (-u) File containig users to do this on')
    print('    --help      (-h) This help')
    sys.exit(code)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                    'f:t:cdeu:h',
                                    ['from=',
                                     'to=',
                                     'commit',
                                     'dis-reqs',
                                     'log-event',
                                     'users=',
                                     'help'])
    except getopt.GetoptError:
        usage(3)

    commit = False
    from_spread = None
    to_spread = None
    disable_requests = False
    log_events = False
    users_file = None
    for opt, val in opts:
        if opt in ('-c', '--commit'):
            commit = True
        elif opt in ('-f', '--from'):
            from_spread = val
        elif opt in ('-t', '--to'):
            to_spread = val
        elif opt in ('-c', '--commit', '--let-it-rip'):
            commit = True
        elif opt in ('-d', '--dis-reqs'):
            disable_requests = True
        elif opt in ('-e', '--log-event'):
            log_events = True
        elif opt in ('-u', '--users'):
            users_file = val
        elif opt in ('-h', '--help'):
            usage(0)
        else:
            print('Error: Unknown argument')
            usage(3)


    if not from_spread and not to_spread:
        print('Plz define from- and to-spread!!!')
        usage(3)

    if not users_file:
        print('Must have that list of users!')
        usage(3)

    mangle(from_spread, to_spread, users_file, commit, log_events,
            disable_requests)
