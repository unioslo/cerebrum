#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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
import getopt
import sys

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum import Errors

def usage(exitcode=0):
    print """Usage: pq_update.py [--dryrun] -u
    Update printerquotas for users that already have the correct data
    in the printerquotas table.

    --dryrun: only report changes, don't perform them
    -u : update quota using weekly_quota
    """
    sys.exit(exitcode)

def update_quotas(dryrun):
    pq = PrinterQuotas.PrinterQuotas(db)
    for row in pq.list_quotas():
        if verbose:
            print "has: %s, acid= %i, pq=%i, wq=%i, mq=%i, tq=%i, ptm=%i" % (
                row['has_printerquota'], row['account_id'],
                row['printer_quota'], row['weekly_quota'],
                row['max_quota'], row['termin_quota'],
                row['pages_this_semester'])
        if row['has_printerquota'] not in ('1', 'T'):
            continue
        
        new_quota = min(row['printer_quota'] + row['weekly_quota'],
                        row['max_quota'])
        if False:   # temporarely disabled as termin_quota=0 for all entries in db
            if new_quota + row['pages_this_semester'] > row['termin_quota']:
                new_quota = row['termin_quota'] - row['pages_this_semester']
        try:
            pq.clear()
            pq.find(row['account_id'])
        except Errors.NotFoundError:
            print "ERROR: Was %i deleted after we started?" % row['account_id']
            continue
        if new_quota == pq.printer_quota:
            continue
        print "New quota for %i: %i (old=%i)" % (
            row['account_id'], new_quota, pq.printer_quota)
        if not dryrun:
            pq.printer_quota = new_quota
            pq.write_db()
            db.commit()

def main():
    global db, verbose
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'uv', ['dryrun'])
    except getopt.GetoptError:
        usage(1)
    dryrun = verbose = 0
    db = Factory.get('Database')()
    db.cl_init(change_program='pq_update')
    for opt, val in opts:
        if opt == '--dryrun':
            dryrun = 1
        elif opt == '-v':
            verbose += 1
        elif opt == '-u':
            update_quotas(dryrun)
    if not opts:
        usage(1)

if __name__ == '__main__':
    main()
