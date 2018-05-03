#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

import getopt
import sys

import mx

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas

__doc__ = """Usage: [options]

    Parameter options:
       --from date (YYYY-MM-DD) (inclusive)
       --to   date (YYYY-MM-DD) (exclusive)
       
       --sted-level   (fak|inst|gr)
         Group statistics by sted      (default: none)
         
       --sort-user-by (jobs|free|paid|total)
         Sort users by given column    (default: jobs)
         
       --user-rows    num
         Limit number of returned rows (default: 10)


    Reports:
       --printjobs:   show number of printjobs, pages etc
       --payments:    show number of payments
       --top-user:    show top users
       --user-type:   show stats by np_type
       --person-type: show stats by person-type

       
    Example:
      Show top-20 users whos paid qouta was reduced from june to august:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --sort-user-by paid \\
         --user-rows 20 --top-user

      Show usage by faculty:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --sted-level fak --printjobs

      Show payment statistics:
      quota_stats.py --from 2004-06-01 --to 2004-08-05 --payments

"""

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)


def sort_by_numjobs(a, b):
    """Sorting function for use by 'user_print_stats'"""
    return cmp(abs(b[stat_sort_key]), abs(a[stat_sort_key]))


def user_print_stats(from_date, to_date, sort_by='jobs', num=10):
    """Prints information about single user's printing.

    The top X users, determined by a given criterium are displayed,
    ordered by that criterium. Default is top 10 users by total number
    of pages printed. Other critera are 'jobs', 'free' and 'paid'.
    """
    print "\nUsage by single users (top %i by %s)" % (num, sort_by)
    
    global stat_sort_key
    cols = ['jobs', 'free', 'paid', 'total', 'person_id']
    stat_sort_key = cols.index(sort_by)
    rows = ppq.get_pagecount_stats(from_date, to_date, group_by=('person_id',))
    rows.sort(sort_by_numjobs)
    format = "%-8s %-8s %-8s %-8s %-8s"
    print format % tuple(cols)

    # Force integer display; floats make no sense in this context
    format = "%8i %8i %8i %8i %8s"
    n = 0
    for r in rows:
        print format % tuple(
            [r[c] for c in cols])
        n += 1
        if n > num:
            break


def user_type_stats(from_date, to_date):
    """Displays information about print statistics by user type,
    i.e. 'personlig', 'deleted', 'unknown', 'kursbruker' and
    'programvare'.
    """
    print "\nUsage by user type:"
    
    ac = Factory.get('Account')(db)
    ac_type = {}
    for r in ac.list():
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

    
def person_type_stats(from_date, to_date):
    """Group #jobs, #free, #paid and total# pages by person's
    affiliation.
    """
    print "\nUsage by person type/affiliation:"
    
    p = Factory.get('Person')(db)
    p_type = {}
    pri_order = {}
    num2aff = {}
    n = 0
    for c in [co.affiliation_ansatt, co.affiliation_tilknyttet,
              co.affiliation_student, co.affiliation_manuell]:
        pri_order[int(c)] = n
        num2aff[n] = c
        n += 1
    
    for r in p.list_affiliations(fetchall=False):
        p_type[int(r['person_id'])] = min(
            pri_order.get(int(r['affiliation']), 99),
            p_type.get(int(r['person_id']), 99))
    
    cols = ['jobs', 'free', 'paid', 'total']
    rows = ppq.get_pagecount_stats(from_date, to_date, group_by=('person_id',))
    stats = {}
    for r in rows:
        if r['person_id'] is None:
            t = 'unknown'
        else:
            t = p_type.get(int(r['person_id']), 'other')
        if not stats.has_key(t):
            stats[t] = [0, 0, 0, 0, 0]
        for c in range(len(cols)):
            stats[t][c] += int(r[cols[c]])
        stats[t][4] += 1

    format = "%-12s %-12s %-12s %-12s"
    t = ['PersonType']
    t.extend(cols)
    print ("%-14s "+format) % tuple(t)

    format = format.replace('-', '')
    for k, v in stats.items():
        if type(k) == int:
            k = num2aff[k]
        print "%-14s:" % k , format % tuple(
            [v[c] for c in range(len(cols))])

    
def printjob_stats(from_date, to_date, sted_level=None):
    """Displays information about #jobs, #free, #paid and total# pages
    printed, either in total or broken down by 'stedkode' on a given
    level; 'fakultet', 'institutt' or group.
    """    
    cols = ['jobs', 'free', 'paid', 'total']
    if sted_level:
        if sted_level == 'fak':
            sted_level = 2
        elif sted_level == 'inst':
            sted_level = 4
        else:
            sted_level = 6
        group_by=("stedkode",)
        print "\nUsage by 'stedkode':"
    else:
        group_by = ()
        print "\nTotal usage:"
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
    """Displays information about payment statistics."""
    print "\nPayment statistics:"
    
    cols = ['jobs', 'kroner', 'paid', 'free', 'transaction_type']
    format = "%-8s %-8s %-8s %-8s %-8s"
    print format % tuple(cols)
    
    # Force integer display; floats make no sense in this context
    format = "%8i %8i %8i %8i %8s"
    rows = ppq.get_payment_stats(from_date, to_date)
    for r in rows:
        for c in cols:
            if c == 'transaction_type':
                r[c] = "%s" % co.PaidQuotaTransactionTypeCode(int(r[c]))
        print format % tuple(
            [r[c] for c in cols])


def main():
    """Main processing function. Reads/checks options and calls
    reporting function(s) based on option(s) given.
    """
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'from=', 'to=', 'sted-level=', 'printjobs',
            'payments', 'top-user', 'sort-user-by=', 'user-rows=',
            'user-type', 'person-type'])
    except getopt.GetoptError:
        usage(1)

    if not opts:
        usage(1)

    sted_level = None
    user_sort_by = 'jobs'
    num_user_rows = 10

    # Do option-parsing in 2 steps, since the second group of options
    # rely on options in the first group.
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--from',):
            from_date = mx.DateTime.ISO.ParseDate(val)
        elif opt in ('--to',):
            to_date = mx.DateTime.ISO.ParseDate(val)
        elif opt in ('--sted-level',):
            sted_level = val
        elif opt in ('--sort-user-by',):
            user_sort_by = val
        elif opt in ('--user-rows',):
            num_user_rows = int(val)

    for opt, val in opts:
        if opt in ('--printjobs',):
            printjob_stats(from_date, to_date, sted_level=sted_level)
        elif opt in ('--payments',):
            payment_stats(from_date, to_date)
        elif opt in ('--top-user',):
            user_print_stats(from_date, to_date, sort_by=user_sort_by, num=num_user_rows)
        elif opt in ('--user-type',):
            user_type_stats(from_date, to_date)
        elif opt in ('--person-type',):
            person_type_stats(from_date, to_date)

    print ""


def usage(exitcode=0):
    """Prints module's __doc__-string, then exits with given exitcode"""
    print __doc__
    sys.exit(exitcode)


if __name__ == '__main__':
    main()


