#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
#
# This file is part of Cerebrum.
#

import getopt
import sys
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.printer_quota import PPQUtil
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
pu = PPQUtil.PPQUtil(db)
ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)

def sort_by_numjobs(a, b):
    return cmp(abs(b[stat_sort_key]), abs(a[stat_sort_key]))

def user_print_stats(from_date, to_date, sort_by='total', num=10):
    global stat_sort_key
    cols = ['jobs', 'free', 'paid', 'total', 'person_id']
    stat_sort_key = cols.index(sort_by)
    rows = ppq.get_pagecount_stats(from_date, to_date, group_by=('person_id',))
    rows.sort(sort_by_numjobs)
    format = "%-8s %-8s %-8s %-8s %-8s"
    print format % tuple(cols)
    format = format.replace('-', '')

    n = 0
    for r in rows:
        print format % tuple(
            [r[c] for c in cols])
        n += 1
        if n > num:
            break
    
def printjob_stats(from_date, to_date, sted_level=None):
    cols = ['jobs', 'free', 'paid', 'total']
    if sted_level:
        if sted_level == 'fak':
            sted_level = 2
        elif sted_level == 'gr':
            sted_level = 4
        else:
            sted_level = 6
        group_by=("stedkode",)
    else:
        group_by = ()
    cols.extend(group_by)
    format = "%-8s %-8s %-8s %-8s"
    for t in group_by:
        format += " %-8s"

    print format % tuple(cols)
    format = format.replace('-', '')
    rows = ppq.get_pagecount_stats(from_date, to_date, group_by=group_by)
    if sted_level:
        # We could have done substr in SQL, but I'm not sure how
        # standard SQL it is, and we would have to find the total anyway
        tmp_cols = cols[:]
        tmp_cols.remove('stedkode')
        tmp = {'total': {'stedkode': 'total'}}
        for c in tmp_cols:
            tmp['total'][c] = 0
        for r in rows:
            sted = r['stedkode']
            if sted is None:
                sted = 'Ukjent'
            else:
                sted = sted[:sted_level]
            if not tmp.has_key(sted):
                tmp[sted] = {'stedkode': sted}
                for c in tmp_cols:
                    tmp[sted][c] = 0
            for c in tmp_cols:
                tmp[sted][c] += int(r[c])
                tmp['total'][c] += int(r[c])
        rows = tmp.values()
    for r in rows:
        print format % tuple(
            [r[c] for c in cols])

def payment_stats(from_date, to_date):
    cols = ['jobs', 'kroner', 'paid', 'free', 'transaction_type']
    format = "%-8s %-8s %-8s %-8s %-8s"
    print format % tuple(cols)
    format = format.replace('-', '')
    rows = ppq.get_payment_stats(from_date, to_date)
    for r in rows:
        for c in cols:
            if c == 'transaction_type':
                r[c] = "%s" % co.PaidQuotaTransactionTypeCode(int(r[c]))
        print format % tuple(
            [r[c] for c in cols])

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['help', 'from=', 'to=', 'sted-level=', 'printjobs', 'payments', 'top-user', 'sort-user-by=', 'user-rows='])
    except getopt.GetoptError:
        usage(1)

    if not opts:
        usage(1)

    sted_level = None
    user_sort_by = 'total'
    num_user_rows = 10
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--from',):
            from_date = db.Date(*([ int(x) for x in (val+'-0-0-0').split('-')]))
        elif opt in ('--to',):
            to_date = db.Date(*([ int(x) for x in (val+'-0-0-0').split('-')]))
        elif opt in ('--sted-level',):
            sted_level = val
        elif opt in ('--printjobs',):
            printjob_stats(from_date, to_date, sted_level=sted_level)
        elif opt in ('--payments',):
            payment_stats(from_date, to_date)
        elif opt in ('--top-user',):
            user_print_stats(from_date, to_date, sort_by=user_sort_by, num=num_user_rows)
        elif opt in ('--sort-user-by',):
            sort_by = val
        elif opt in ('--user-rows',):
            num_user_rows = int(val)

def usage(exitcode=0):
    print """Usage: [options]

    Parameter options:
       --from date (YYYY-MM-DD)
       --to date
       --sted-level (fak|gr|inst) (default: none).  Group statistics by sted
       --sort-user-by (jobs|free|paid|total)                (default: jobs)
       --user-rows num: limit number of returned rows       (default: 10)


    Reports:
       --printjobs: show number of printjobs, pages etc
       --payments:  show number of payments
       --top-user:  show top users

    Example:
      Show top-20 users whos paid qouta was reduced from june to august:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --sort-user-by paid \
         --user-rows 20--top-user

      Show usage by faculty:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --sted-level fak --printjobs

      Show payment statistics:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --payments
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
