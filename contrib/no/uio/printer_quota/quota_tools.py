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
from Cerebrum import Metainfo

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

    unknown = []
    for row in (ppq.get_payment_stats(
        DateTime.Date(1980,1,1,1,1,1), DateTime.Date(2020,1,1,1,1,1),
        group_by=('person_id',))+ 
                ppq.get_pagecount_stats(
        DateTime.Date(1980,1,1,1,1,1), DateTime.Date(2020,1,1,1,1,1),
        group_by=('person_id',))):
        pid = row['person_id'] and long(row['person_id']) or 'NULL'
        if not person_stats.has_key(pid):
            unknown.append(pid)
            continue
        tmp = person_stats[pid]
        tmp['free'] -= int(row['free'])
        tmp['paid'] -= int(row['paid'])
        tmp['total'] -= int(row['total'])

    if unknown:
        logger.debug("No paid_quota_status entry for %s" % unknown)

    ok_count = 0
    for pid in person_stats.keys():
        ok = True
        for k in ('free', 'paid', 'total'):
            if person_stats[pid][k] != 0:
                # TODO: The total check will fail 
                logger.warn("noia check failed for %s: %s" % (
                    pid, repr(person_stats[pid])))
                ok = False
        if ok:
            ok_count += 1
    logger.debug("Found %i OK records" % ok_count)

def migrate_to_1_1():
    # Add extra columns to tables
    for sql in (
        "ALTER TABLE paid_quota_status "
        "  ADD COLUMN accum_quota NUMERIC(8)",
        "ALTER TABLE paid_quota_status "
        "  ADD COLUMN kroner NUMERIC(7,2)",
        "ALTER TABLE paid_quota_history "
        "  ADD COLUMN pageunits_accum NUMERIC(6,0)",
        "ALTER TABLE paid_quota_history "
        "  ADD COLUMN kroner NUMERIC(7,2)"):
        print sql
        db.execute(sql)

    # Fill new columns with data
    for sql in (
        "UPDATE paid_quota_status SET kroner=paid_quota*0.3, accum_quota=0",
        # pageunits_paid -> kroner
        "UPDATE paid_quota_history "
        "SET kroner=0.3*pageunits_paid, pageunits_accum=0",
        # pageunits_paid skal ikke lenger røres ved betalinger
        "UPDATE paid_quota_history SET pageunits_paid=0 "
        "WHERE transaction_type=%i" % co.pqtt_quota_fill_pay,
        #
        # Innbetalinger kunne i teorien vært gjort som med søket
        # under, men da ville ikke summen gått opp med
        # paid_quota_status.paid_quota*0.3.  Vi 'faker' derfor det
        # innbetalte beløpet, slik at det er loggført 200.10 kr selv
        # om studenten kun betalte 200.00 kr.  Differansen er på
        # totalt ca 2400kr i studentenes favør.
        #
        # "UPDATE paid_quota_history SET kroner=t.kroner "
        # "FROM paid_quota_transaction t "
        # "WHERE paid_quota_history.job_id=t.job_id"
        ):
        print sql
        db.execute(sql)

    # Remove obsolete columns
    for sql in (
        "ALTER TABLE paid_quota_status DROP COLUMN paid_quota",
        "ALTER TABLE paid_quota_transaction DROP COLUMN kroner",
        "ALTER TABLE paid_quota_status"
        "  ALTER COLUMN accum_quota SET NOT NULL",
        "ALTER TABLE paid_quota_status"
        "  ALTER COLUMN kroner SET NOT NULL",
        "ALTER TABLE paid_quota_history"
        "  ALTER COLUMN pageunits_accum SET NOT NULL",
        "ALTER TABLE paid_quota_history"
        "  ALTER COLUMN kroner SET NOT NULL"):
        print sql
        db.execute(sql)

    meta = Metainfo.Metainfo(db)
    meta.set_metainfo('sqlmodule_%s' % 'printer_quota', '1.1')
    db.commit()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'truncate=', 'truncate-log=', 'person-id=',
            'noia-check', 'migrate-to-1-1'])
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
        elif opt in ('--migrate-to-1-1',):
            migrate_to_1_1()
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
