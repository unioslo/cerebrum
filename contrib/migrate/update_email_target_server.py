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

"""Bulk-update server_id on email targets"""

import getopt
import sys

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailServer



def mangle(from_server, to_server, commit):
    db = Factory.get('Database')()
    et = Factory.get('EmailTarget')(db)
    db.cl_init(change_program='update_email_target_server')
    # Yes yes yes, it is quite pretty
    es = EmailServer(db)

    es.clear()
    es.find_by_name(from_server)
    from_server_id = es.entity_id

    es.clear()
    es.find_by_name(to_server)
    to_server_id = es.entity_id

    for row in et.list_email_server_targets():
        if row.has_key('server_id') and row['server_id'] == from_server_id:
            et.clear()
            et.find(row['target_id'])
            old_sid = et.email_server_id
            et.email_server_id = to_server_id
            et.write_db()
            print('Moved %d from %d to %d' % \
                    (et.entity_id, old_sid, to_server_id))

    if commit:
        db.commit()
        print 'Committed all changes'
    else:
        db.rollback()
        print 'Rolled back all changes'


def usage(code=0):
    print('Usage: update_email_target_server.py -t to_server -f from_server' +
            '[-c]')
    print('         -t (--to) email server to migrate targets to' +
            ' (i.e. \'mail\')')
    print('         -f (--from) email server to migrate targets from ' +
            '(i.e. \'mail.uio.no\')')
    print('         -c (--commit) run in commit mode')

    sys.exit(code)

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:t:c',
                                   ['from=',
                                    'to=',
                                    'commit'])
    except getopt.GetoptError:
        usage()

    commit = False
    from_server = None
    to_server = None
    for opt, val in opts:
        if opt in ('-c', '--commit'):
            commit = True
        elif opt in ('-f', '--from'):
            from_server = val
        elif opt in ('-t', '--to'):
            to_server = val

    if not from_server and not to_server:
        print('Plz define from- and to-server!!!')
        usage(1)

    mangle(from_server, to_server, commit)
