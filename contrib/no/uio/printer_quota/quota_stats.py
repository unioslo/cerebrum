#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
#
# This file is part of Cerebrum.
#

import getopt
import sys
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
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

def user_type_stats(from_date, to_date, sort_by='total'):
    ac = Factory.get('Account')(db)
    ac_type = {}
    for r in ac.list(filter_expired=True):
        ac_type[int(r['account_id'])] = r['np_type']
    
    cols = ['jobs', 'free', 'paid', 'total']
    rows = ppq.get_pagecount_stats(from_date, to_date, group_by=('account_id',))
    stats = {}
    for r in rows:
        if r['account_id'] is None:
            t = 'unknown'
        else:
            t = ac_type.get(r['account_id'], 'deleted')
        if not stats.has_key(t):
            stats[t] = [0, 0, 0, 0]
        for c in range(len(cols)):
            stats[t][c] += int(r[cols[c]])

    format = "%-12s %-12s %-12s %-12s"
    t = ['type']
    t.extend(cols)
    print ("%-14s "+format) % tuple(t)
    format = format.replace('-', '')

    for k, v in stats.items():
        if k is None:
            k = 'personlig'
        else:
            k = co.Account(k)
        print "%-14s:" % k , format % tuple(
            [v[c] for c in range(len(cols))])
    
def printjob_stats(from_date, to_date, sted_level=None):
    cols = ['jobs', 'free', 'paid', 'total']
    if sted_level:
        if sted_level == 'fak':
            sted_level = 2
        elif sted_level == 'inst':
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
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'from=', 'to=', 'sted-level=', 'printjobs',
            'payments', 'top-user', 'sort-user-by=', 'user-rows=',
            'user-type'])
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
            user_sort_by = val
        elif opt in ('--user-rows',):
            num_user_rows = int(val)
        elif opt in ('--user-type',):
            user_type_stats(from_date, to_date)

def usage(exitcode=0):
    print """Usage: [options]

    Parameter options:
       --from date (YYYY-MM-DD)
       --to date
       --sted-level (fak|inst|gr) (default: none).  Group statistics by sted
       --sort-user-by (jobs|free|paid|total)                (default: jobs)
       --user-rows num: limit number of returned rows       (default: 10)


    Reports:
       --printjobs: show number of printjobs, pages etc
       --payments:  show number of payments
       --top-user:  show top users
       --user-type: show stats by np_type
       
    Example:
      Show top-20 users whos paid qouta was reduced from june to august:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --sort-user-by paid \\
         --user-rows 20 --top-user

      Show usage by faculty:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --sted-level fak --printjobs

      Show payment statistics:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --payments
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 5d825297-abe1-4774-addf-fdf829f4b3f8
