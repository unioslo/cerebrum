# -*- coding: iso-8859-1 -*-

from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum import Utils

from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import errors

PAGE_COST = {
    'fs': 0.30,
    'epay': 0.30
    }

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
            new_value = new_value - row['free_quota']
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
        update_by=None, update_program=None):
        if not (page_units > 0):
            raise errors.IllegalUndoRequest("page_units must be > 0")
        rows = self.ppq.get_history(
            target_job_id=target_job_id)
        if len(rows) > 0:
            raise errors.IllegalUndoRequest, "Undo already registered for that job"
        rows = self.ppq.get_history(
            job_id=target_job_id)
        if len(rows) == 0:
            raise errors.IllegalUndoRequest, "Unknown target_job_id"
        if rows[0]['transaction_type'] != int(self.const.pqtt_printout):
            raise errors.IllegalUndoRequest, "Can only undo print jobs"

        # Calculate change
        old_free, old_pay = (rows[0]['pageunits_free'],
                             rows[0]['pageunits_paid'])

        if page_units > -old_free + -old_pay:
            raise errors.IllegalUndoRequest, "Cannot undo more pages than was in the job"

        pageunits_free = pageunits_paid = 0
        if old_pay < 0:                  # Paid for refered print-job
            delta = min(abs(old_pay), page_units)
            pageunits_paid = delta
            page_units -= delta
        if page_units and old_free < 0:  # old job had free pages
            delta = min(abs(old_free), page_units)
            pageunits_free = delta
            page_units -= delta
        if page_units != 0:
            raise ValueError, "oops, page_units=%i" % page_units

        self.ppq._add_transaction(
            self.const.pqtt_undo,
            person_id,
            pageunits_free=pageunits_free,
            pageunits_paid=pageunits_paid,
            target_job_id=target_job_id,
            description=description,
            update_by=update_by,
            update_program=update_program)
