#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import time
import cerebrum_path
from mx import DateTime
from Cerebrum import Errors
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import PPQUtil
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
db.cl_init(change_program="skeleton")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)

logger = Factory.get_logger("cronjob")

def truncate_log(days, logfilename, person_id=None):
    pq_util = PPQUtil.PPQUtil(db)
    ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)
    to_date = time.strftime('%Y-%m-%d', time.localtime(
        time.time()-3600*24*days))
    to_date = DateTime.Date(*([ int(x) for x in (to_date+'-0-0-0').split('-')]))
    from_date = DateTime.Date(1980,1,1,1,1,1)
    persons = {}
    if person_id:
        persons[person_id] = True
    else:      # find potential victims
        for row in ppq.get_pagecount_stats(from_date, to_date,
                                           group_by=('person_id',)):
            if row['person_id'] is not None:
                persons[long(row['person_id'])] = True
        for row in ppq.get_payment_stats(from_date, to_date,
                                         group_by=('person_id',)):
            if row['person_id'] is not None:
                persons[long(row['person_id'])] = True
    out = open(logfilename, 'a')
    out.write("Truncate job started at %s\n" % time.asctime())
    for person_id in persons.keys() + [None]:
        removed, new_status = pq_util.truncate_log(
            person_id, to_date, 'quota_tools')
        if not removed:
            continue
        logger.debug("removed %i entries for %s" % (
            len(removed), db.pythonify_data(removed[0]['person_id'])))
        out.write("new balance: %s\n" % repr(new_status))
        for row in removed:
            row = dict([(k, db.pythonify_data(v)) for k, v in row.items()])
            row['tstamp'] = row['tstamp'].strftime('%Y-%m-%d %H:%M.%S')
            out.write("removed: %s\n" % repr(row))
        try:
            db.commit()
        except:
            out.write("WARNING: Commit threw exception for this person\n")
            raise
    out.close()

def noia_check():
    """Asserts that status matches history"""
    ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)

    # calculate total for 'free, paid and total' pages and compare
    # with status.  Unfortunately summing kroner has no meaning.

    person_stats = {}
    for row in ppq.get_quoata_status():
        pid = row['person_id'] and long(row['person_id']) or 'NULL'
        person_stats[pid] = {'free': int(row['free_quota']),
                             'paid': int(row['paid_quota']),
                             'total': int(row['total_pages'])}

    for row in (ppq.get_payment_stats(
        DateTime.Date(1980,1,1,1,1,1), DateTime.Date(2020,1,1,1,1,1),
        group_by=('person_id',))+ 
                ppq.get_pagecount_stats(
        DateTime.Date(1980,1,1,1,1,1), DateTime.Date(2020,1,1,1,1,1),
        group_by=('person_id',))):
        pid = row['person_id'] and long(row['person_id']) or 'NULL'
        tmp = person_stats[pid]
        tmp['free'] -= int(row['free'])
        tmp['paid'] -= int(row['paid'])
        tmp['total'] -= int(row['total'])

    for pid in person_stats.keys():
        for k in ('free', 'paid', 'total'):
            if person_stats[pid][k] != 0:
                # TODO: The total check will fail 
                logger.warn("noia check failed for %s: %s" % (
                    pid, repr(person_stats[pid])))

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'truncate=', 'truncate-log=', 'person-id=',
            'noia-check'])
    except getopt.GetoptError:
        usage(1)

    truncate_fname = person_id = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--truncate-log',):
            truncate_fname = val
        elif opt in ('--person-id',):
            person_id = int(val)
        elif opt in ('--noia-check',):
            noia_check()
        elif opt in ('--truncate',):
            if not truncate_log:
                usage(1)
            if val.find('-') != -1:
                val = (time.time() - time.mktime(
                    time.strptime(val, '%Y-%m-%d')))/(3600*24)
            truncate_log(int(val), truncate_fname, person_id=person_id)
    if not opts:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
    --truncate-log fname : log truncated data to this file [required]
    --person-id person_id : only remove this persons jobs (for debuging)
    --truncate days : truncate jobs older than this # of days
    --noia-check : assert that contents of paid_quota_status is correct
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 8f250c22-c3a6-11d9-82d1-5adceacf846e
