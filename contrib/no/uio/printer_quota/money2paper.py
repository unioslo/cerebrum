#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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
import time
import cerebrum_path

from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio.printer_quota import bofhd_pq_utils
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import PPQUtil
from Cerebrum.modules.no.uio.AutoStud.StudentInfo import GeneralDataParser

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Person.Person(db)
ppq = PaidPrinterQuotas.PaidPrinterQuotas(db)
pq_util = PPQUtil.PPQUtil(db)
logger = Factory.get_logger("cronjob")
# we don't want the log of payment statements to be cluttered with
# debug statements etc.
payment_logger = bofhd_pq_utils.SimpleLogger('pq_bofhd.log')

def import_data(fname):
    # Hent betalings-id'er hittil i år
    processed_payment_ids = {}
    for row in ppq.get_history_payments(
        transaction_type=co.pqtt_quota_fill_pay,
        bank_id_mask='FS:%%'):
        processed_payment_ids[row['bank_id']] = True    
    
    for attrs in GeneralDataParser(fname, "betaling"):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(attrs['fodselsdato']),
                                                  int(attrs['personnr'])))
        try:
            person.clear()
            person.find_by_external_id(
                co.externalid_fodselsnr, fnr, source_system=co.system_fs)
        except Errors.NotFoundError:
            logger.warn("Payment for unknown person: %s" % fnr)
            continue
        person_id = person.entity_id
        # Asert that person has a quota_status entry
        try:
            row = ppq.find(person_id)
        except Errors.NotFoundError:
            ppq.new_quota(person_id)

        ekstern_betaling_id = ":".join(('FS', attrs['fakturanr'], attrs['detaljlopenr']))
        if processed_payment_ids.has_key(ekstern_betaling_id):
            logger.debug("Already added: %s" % ekstern_betaling_id)
            continue
        description = 'FS-betaling'
        payment_tstamp = attrs.get('dato_betalt', None)
        try:
            logger.debug("Add payment %s for %s" % (attrs['belop'], fnr))
            pq_util.add_payment(person_id,
                                PPQUtil.PPQUtil.FS,
                                ekstern_betaling_id,
                                float(attrs['belop']),
                                description,
                                payment_tstamp=payment_tstamp,
                                update_program='money2paper')
            payment_logger.info("Registered %s kr for %i (id: %s)" % (
                attrs['belop'], person_id, ekstern_betaling_id))
        except db.DatabaseError, msg:
            db.rollback()
            logger.warn("Input %s caused DatabaseError:%s" % (attrs, msg))
            continue

        db.commit()
        
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:', ['help', 'paid-file='])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-p', '--paid-file'):
            import_data(val)
    if not opts:
        usage(1)

def usage(exitcode=0):
    print """Usage: [options]
    -p | --paid-file file:
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 5a06a3e2-f1e9-44ae-9fd9-8fdccee0b5bf
