# -*- coding: iso-8859-1 -*-

import cereconf

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

from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum import Utils

from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import errors

PAGE_COST = {
    'fs': 0.30,
    'epay': 0.30
    }

def is_free_period(year, month, mday):
    if ((month, mday) >= cereconf.PQ_SPRING_FREE[0] and
        (month, mday) <= cereconf.PQ_SPRING_FREE[1]):
        return True
    elif ((month, mday) >= cereconf.PQ_FALL_FREE[0] and
        (month, mday) <= cereconf.PQ_FALL_FREE[1]):
        return True
    else:
        return False

def get_term_init_prefix(year, month, mday):
    if ((month, mday) >= cereconf.PQ_SPRING_START and
        (month, mday) < cereconf.PQ_FALL_START):
        term = 'V'
    else:
        term = 'H'
    return '%i-%s:init:' % (year, term)

class PPQUtil(object):
    FS = 'fs'
    EPAY = 'epay'

    def __init__(self, db):
        self.db = db
        self.const = Utils.Factory.get('Constants')(self.db)
        self.ppq = PaidPrinterQuotas.PaidPrinterQuotas(self.db)

    def round_up(n):
        """Round up to nearest integer"""
        if int(n) < n:
            return int(n) + 1
        return int(n)
    round_up = staticmethod(round_up)

    def add_payment(self, person_id, payment_type, bank_id, kroner,
                    description, payment_tstamp=None, update_by=None,
                    update_program=None):
        """Utility method that converts money to quota"""
        paid_pages = PPQUtil.round_up(kroner * (1/PAGE_COST[payment_type]))

        try:
            self.ppq.find(person_id)
        except Errors.NotFoundError:
            # We accept payments even if user has no quota, thus we
            # must make a quota_status entry for the person
            self.ppq.new_quota(person_id)

        self.ppq._add_transaction(
            self.const.pqtt_quota_fill_pay,
            person_id,
            pageunits_free=0,
            pageunits_paid=paid_pages,
            description=description,
            bank_id=bank_id,
            kroner=kroner,
            payment_tstamp=payment_tstamp,
            update_by=update_by,
            update_program=update_program)
        return paid_pages


    def _alter_free_pages(self, op, person_id, new_value, why,
                          update_by=None, update_program=None):
        if new_value < 0:
            raise errors.InvalidQuotaData, "Cannot %s negative quota" % op
        row = self.ppq.find(person_id)
        if op == 'set':
            new_value = new_value - int(row['free_quota'])
        if new_value == 0:
            raise errors.InvalidQuotaData, "quota already at that value"
        
        self.ppq._add_transaction(
            self.const.pqtt_quota_fill_free,
            person_id,
            pageunits_free=new_value,
            description=why,
            update_by=update_by,
            update_program=update_program)

    def set_free_pages(self, person_id, new_value, why,
                       update_by=None, update_program=None):
        self._alter_free_pages('set', person_id, int(new_value), why,
                               update_by=update_by,
                               update_program=update_program)

    def add_free_pages(self, person_id, increment, why,
                       update_by=None, update_program=None):
        self._alter_free_pages('add', person_id, int(increment), why,
                               update_by=update_by,
                               update_program=update_program)

    def undo_transaction(
        self, person_id, target_job_id, page_units, description,
        update_by=None, update_program=None,
        ignore_transaction_type=False):
        """Undo a transaction.  If page_units='', undo all pages in
        given job.

        ignore_transaction_type should be set if job is not a
        printjob."""

        if str(page_units) != '':
            try:
                page_units = int(page_units)
            except ValueError:
                raise errors.IllegalUndoRequest("page_units is not a number")
        if page_units != '' and not (page_units > 0):
            raise errors.IllegalUndoRequest("page_units must be > 0")
        rows = self.ppq.get_history(
            target_job_id=target_job_id)
        if len(rows) > 0:
            raise errors.IllegalUndoRequest, "Undo already registered for that job"
        rows = self.ppq.get_history(
            job_id=target_job_id)
        if len(rows) == 0:
            raise errors.IllegalUndoRequest, "Unknown target_job_id"
        if ((not ignore_transaction_type) and
            rows[0]['transaction_type'] != int(self.const.pqtt_printout)):
            raise errors.IllegalUndoRequest, "Can only undo print jobs"
        if rows[0]['person_id'] != person_id:
            raise errors.IllegalUndoRequest, "person_id doesn't match job_id"

        # Calculate change
        old_free, old_paid, old_total = [int(rows[0][x]) for x in (
            'pageunits_free', 'pageunits_paid', 'pageunits_total')]
        if page_units == '':
            delta_free, delta_paid, delta_total = (
                -old_free, -old_paid, -old_total)
        else:
            if ignore_transaction_type:
                # Don't know why we would need this
                raise errors.IllegalUndoRequest, "Not implemented"
            if page_units > -old_free + -old_paid:
                raise errors.IllegalUndoRequest, \
                      "Cannot undo more pages than was in the job"

            delta_total = -page_units
            delta_free = delta_paid = 0
            if old_paid < 0:                  # Paid for refered print-job
                delta = min(abs(old_paid), page_units)
                delta_paid = delta
                page_units -= delta
            if page_units and old_free < 0:  # old job had free pages
                delta = min(abs(old_free), page_units)
                delta_free = delta
                page_units -= delta
            if page_units != 0:
                raise ValueError, "oops, page_units=%i" % page_units

        self.ppq._add_transaction(
            self.const.pqtt_undo,
            person_id,
            pageunits_free=delta_free,
            pageunits_paid=delta_paid,
            target_job_id=target_job_id,
            description=description,
            update_by=update_by,
            update_program=update_program)

    def join_persons(self, old_id, new_id):
        """Join printjobs performed by old and new person, updating
        quota history and status.

        Returns True if changes were done."""

        # Note: this method has a race-condition if the old or new
        # person_id has its quota updated while we are executing.
        # Since this operation rarely should be used, we ignore this
        # problem for now.

        try:
            old_ppq = self.ppq.find(old_id)
        except Errors.NotFoundError:
            return False      # No data to convert
        try:
            new_ppq = self.ppq.find(new_id)
        except Errors.NotFoundError:
            self.ppq._change_history_owner(old_id, new_id)
            self.ppq._change_status_owner(old_id, new_id)
            return False

        had_quota = []
        if old_ppq['has_quota'] == 'T':
            had_quota.append(old_ppq)
        if new_ppq['has_quota'] == 'T':
            had_quota.append(new_ppq)

        tmp = {}
        # User has some quota information for old and new id
        if len(had_quota) == 1:
            # One had quota, and the other did not.  Keep the entry
            # with quota.
            #
            # A free/paid value != 0 for the person without quota
            # means that the once had has_quota=T, and thus has a
            # debt/credit.  Therefore we can sum the status columns
            # for these persons.
            #
            # Avoiding giving a person the same free-pages more than
            # once is not the responsibility of this method.
            
            # Keep these values from the entry that had quota
            for k in ('has_quota', 'has_blocked_quota', 'weekly_quota',
                      'max_quota'):
                tmp[k] = had_quota[0][k]
        else:
            # None or both of the persons had quota.  Simply change
            # owner and update status by using the sum of the printed
            # pages.  We ignore the weekly/max columns, leaving
            # updating of them to whatever magic set them in the first
            # place.
            pass  # Don't need to do anything special for this case
            
        self.ppq._change_history_owner(old_id, new_id)
        self.ppq._delete_status(old_id)
        for k in ('paid_quota', 'free_quota', 'total_pages'):
            tmp[k] = int(old_ppq[k] + new_ppq[k])
        self.ppq._set_status_attr(new_id, tmp)
        return True

# arch-tag: 46f32b24-2441-4162-be3e-d7392874318a
