#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import time
import cerebrum_path
from Cerebrum import Errors
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import PPQUtil
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
db.cl_init(change_program="skeleton")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)

logger = Factory.get_logger("console")

def truncate_log(days, logfilename, person_id=None):
    pq_util = PPQUtil.PPQUtil(db)
    ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)
    to_date = time.strftime('%Y-%m-%d', time.localtime(
        time.time()-3600*24*days))
    to_date = db.Date(*([ int(x) for x in (to_date+'-0-0-0').split('-')]))
    from_date = db.Date(1980,1,1,1,1,1)
    persons = {}
    if person_id:
        persons[person_id] = True
    else:      # find potential victims
        for row in ppq.get_pagecount_stats(from_date, to_date,
                                           group_by=('person_id',)):
            persons[long(row['person_id'])] = True
        for row in ppq.get_payment_stats(from_date, to_date,
                                         group_by=('person_id',)):
            persons[long(row['person_id'])] = True
        
    for person_id in persons.keys():
        removed, new_status = pq_util.truncate_log(person_id, to_date, 'quota_tools')
        logger.debug("NS: %s" % repr(new_status))
        for row in removed:
            row = dict([(k, db.pythonify_data(v)) for k, v in row.items()])
            row['tstamp'] = row['tstamp'].strftime('%Y-%m-%d %H:%M.%S')
            logger.debug("removed: %s" % repr(row))
        db.commit()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'truncate=', 'truncate-log=', 'person-id='])
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
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
