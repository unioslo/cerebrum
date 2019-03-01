#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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
""" Tool for manipulating the change-handler data.

This script is only manipulating the db table "change_handler_data".

The change-handler is giving Cerebrum's various quicksyncs the functionality for
storing what change-log-events have been processed or not. This script overrides
and manipulates this.

Future requests:

- Add possibility for unchecking a given change_id, to rerun it in a sync

"""

import sys

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import CLHandler
try:
    import argparse
except ImportError:
    from Cerebrum.extlib import argparse

logger = Factory.get_logger('cronjob')

def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-d', '--dryrun', dest='dryrun', action='store_true',
        default=False, help="Do not commit the changes to db")
    parser.add_argument('--list-handlers', action='store_true',
        help="List defined change handlers from the db and quit")
    parser.add_argument('--print-handlers', action='store_true',
        help="Print all change handler data and quit")
    parser.add_argument('-k', '--key',
        help="Set what change handler key you want to work on")
    parser.add_argument('--force-last-id', type=int, default=0,
        help="""Force last_id to the given number. The key argument must be
        specified. If the change handler key doesn't exist, it gets created.
        Note: This forces the last_id and removes all gaps in the range before
        this, setting every change to "completed". Use with care!""")
    args = parser.parse_args()

    db = Factory.get('Database')(client_encoding='UTF-8')
    db.cl_init(change_program="change-handler-manipulator")
    co = Factory.get('Constants')(db)
    clh = CLHandler.CLHandler(db)

    logger.info("change_handler_manipulate.py started")

    if args.dryrun:
        # Force rollback to be sure, since CLHandler forces commits itself
        db.commit = db.rollback

    if args.list_handlers:
        handlers = {}
        for row in clh.list_handler_data():
            handlers.setdefault(row['evthdlr_key'], []).append(row)

        for key in sorted(handlers):
            first = None
            last = None

            ids = handlers[key]
            for i in ids:
                if first is None or i['first_id'] < first:
                    first = i['first_id']
                if last is None or i['last_id'] > last:
                    last = i['last_id']

            print "'%s' (%d handlers):" % (key, len(handlers[key]))
            print "  First first_id: %20d" % first
            print "  Last last_id:   %20d" % last
            print
    elif args.print_handlers:
        handlers = {}
        for row in clh.list_handler_data():
            handlers.setdefault(row['evthdlr_key'], []).append(row)
        print "%20s %10s %10s" % ('Key', 'first_id', 'last_id')
        for key in sorted(handlers):
            for r in handlers[key]:
                print "%20s %10d %10d" % (key, r['first_id'], r['last_id'])
    elif args.force_last_id > 0:
        if not args.key:
            raise Exception("Missing --key argument")
        logger.info("Forcing change handler key '%s' to last_id = %d", args.key,
                    args.force_last_id)
        clh._update_ranges(args.key, [[-1, args.force_last_id],])
    else:
        print "No action given. Quits"

    if args.dryrun:
        logger.info("Rolled back changes")
        db.rollback()
    else:
        logger.info("Commiting changes")
        db.commit()
    logger.info("change_handler_manipulate.py finished")

if __name__ == '__main__':
    main()
