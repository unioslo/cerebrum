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

from Cerebrum import Constants
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory

"""PaidPrinterQuotas and PPQUtil contains routines for updating the
paid_quota_* tables.  They should not provide any public methods that
makes it possible to violate the invariant stating that
paid_quota_status can be calculated from paid_quota_history."""

class _PaidQuotaTransactionTypeCode(Constants._CerebrumCode):
    "Mappings stored in the paid_quota_transaction_type_code table"
    _lookup_table = '[:table schema=cerebrum name=paid_quota_transaction_type_code]'
    pass

class Constants(Constants.Constants):
    pqtt_balance = _PaidQuotaTransactionTypeCode(
        'balance', 'Balance - used when cleaning out old data')
    pqtt_printout = _PaidQuotaTransactionTypeCode(
        'print', 'Normal print job')
    pqtt_quota_fill_pay = _PaidQuotaTransactionTypeCode(
        'pay', 'Quota fill')
    pqtt_quota_fill_free = _PaidQuotaTransactionTypeCode(
        'free', 'Quota fill')
    pqtt_undo = _PaidQuotaTransactionTypeCode(
        'undo', 'Undo of a previous job')
    PaidQuotaTransactionTypeCode = _PaidQuotaTransactionTypeCode

def parse_bool(val):
    """Parse boolean value as T/F or 1/0.
    TODO: find a proper way to deal with booleans in Cerebrum"""
    if isinstance(val, str):
        if val == 'T':
            return True
        return False
    if val:
        return True
    return False

class PaidPrinterQuotas(DatabaseAccessor):
    # Because multiple sources may attempt to update the quota_status
    # at the same time, we do not want to use the populate framework
    # here as that framework explicitly sets values while we for
    # quotas only want to increas/decrease values through SQL.
    #
    # Note that if two simultaneous updates occour there is a chance
    # that free_quota gets negative.
    
    def __init__(self, database):
        super(PaidPrinterQuotas, self).__init__(database)
        self.co = Factory.get('Constants')(database)

    def find(self, person_id):
        return self.query_1(
            """SELECT has_quota, has_blocked_quota, weekly_quota,
                      max_quota, paid_quota, free_quota, total_pages
            FROM [:table schema=cerebrum name=paid_quota_status]
            WHERE person_id=:person_id""", {'person_id': person_id})

    def list(self):
        return self.query("""
        SELECT has_quota, has_blocked_quota, person_id
        FROM [:table schema=cerebrum name=paid_quota_status]""")

    def new_quota(self, person_id, has_quota=False,
                  has_blocked_quota=False):
        """Register person in the paid_quota_status table"""
        binds = {
            'person_id': person_id,
            'has_quota': parse_bool(has_quota) and 'T' or 'F',
            'has_blocked_quota': parse_bool(has_blocked_quota) and 'T' or 'F',
            'paid_quota': 0,
            'free_quota': 0,
            'total_pages': 0}

        self.execute("""
        INSERT INTO [:table schema=cerebrum name=paid_quota_status]
          (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                 ", ".join([":%s" % k for k in binds.keys()])),
                                 binds)

    def _set_status_attr(self, person_id, attrs):
        set = []
        binds = {'person_id': person_id}
        for k in attrs.keys():
            set.append("%s=:%s" % (k, k))
            if k in ('has_quota', 'has_blocked_quota'):
                binds[k] = parse_bool(attrs[k]) and 'T' or 'F'
            else:
                binds[k] = attrs[k]
        set = ", ".join(set)
        self.execute("""
        UPDATE [:table schema=cerebrum name=paid_quota_status]
        SET %s
        WHERE person_id=:person_id""" % set, binds)

    def set_status_attr(self, person_id, attrs):
        """Update attrs in paid_quota_status directly.  Direct access
        to counting attrs is denied."""
        for k in attrs.keys():
            if k not in ('has_quota', 'has_blocked_quota',
                         'weekly_quota', 'max_quota'):
                raise ValueError, "Access to attr %s denied" % k
        self._set_status_attr(person_id, attrs)

    # We could get update_by, update_program from the changelog, but
    # then usage of this class would be required.

    def add_printjob(self, person_id, account_id, printer_queue,
                     pageunits, update_program, stedkode=None,
                     job_name=None, spool_trace=None,
                     priss_queue_id=None, paper_type=None, pages=None,
                     tstamp=None, update_quota=True):
        """Register an entry in the paid_quota_history table."""
        pageunits = int(pageunits)
        pageunits_total = pageunits
        # Determine how much to subtract from free and paid quota
        pageunits_free = pageunits_paid = 0
        if update_quota:
            row = self.find(person_id)
            old_free, old_pay = (row['free_quota'], row['paid_quota'])
            if old_free > 0:
                delta = min(old_free, pageunits)
                #new_free -= delta
                pageunits_free = -delta
                pageunits -= delta
            if pageunits:
                pageunits_paid = -pageunits
                #new_paid = old_pay - pageunits

        # Update quota_status.  Note that if update_quota=False,
        # free/paid will be 0
        self._alter_quota(
            person_id, pageunits_free=pageunits_free,
            pageunits_paid=pageunits_paid, pageunits_total=pageunits_total)

        # register history entries
        job_id = self._add_quota_history(
            self.co.pqtt_printout, person_id, pageunits_free,
            pageunits_paid, pageunits_total, update_program=update_program,
            tstamp=tstamp)
        if job_name is not None:
            job_name = job_name[:128]
        binds = {
            'account_id': account_id,
            'job_id': job_id,
            'job_name': job_name,
            'printer_queue': printer_queue,
            'stedkode': stedkode,
            'spool_trace': spool_trace,
            'priss_queue_id': priss_queue_id,
            'paper_type': paper_type,
            'pages': pages
            }
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=paid_quota_printjob]
          (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                 ", ".join([":%s" % k for k in binds.keys()])),
                                 binds)
        return job_id
    
    def _add_quota_history(self, transaction_type, person_id,
                           pageunits_free, pageunits_paid, pageunits_total,
                           update_by=None, update_program=None,
                           tstamp=None, _override_job_id=None):
        if _override_job_id:
            id = _override_job_id
        else:
            id = int(self.nextval('printer_log_id_seq'))
        binds = {
            'job_id': id,
            'transaction_type': int(transaction_type), 
            'person_id': person_id, 
            'update_by': update_by,
            'update_program': update_program, 
            'pageunits_free': pageunits_free,
            'pageunits_paid': pageunits_paid,
            'pageunits_total': pageunits_total}
        if tstamp:                  # Should only used when importing data
            binds['tstamp'] = tstamp
        
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=paid_quota_history]
          (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                 ", ".join([":%s" % k for k in binds.keys()])),
                                 binds)
        return id
        

    def _add_transaction(
        self, transaction_type, person_id, update_by, update_program,
        pageunits_free=0, pageunits_paid=0, target_job_id=None,
        description=None, bank_id=None, kroner=0, payment_tstamp=None,
        tstamp=None, _do_not_alter_quota=False, _override_job_id=None,
        _override_pageunits_total=None):
        """Register an entry in the paid_quota_transaction table.
        Should not be called directly.  Use
        PPQUtil. add_payment/undo_transaction"""

        if ((not (update_by or update_program)) or
            (update_by and update_program)):
            raise CerebrumError, "Must set update_by OR update_program"

        # Update quota
        if not _do_not_alter_quota:
            self._alter_quota(person_id, pageunits_free=pageunits_free,
                              pageunits_paid=pageunits_paid)

        if _override_pageunits_total is not None:
            pageunits_total = _override_pageunits_total
        else:   # pageunits_total should normaly only count printjobs
            pageunits_total = 0
        # register history entries
        id = self._add_quota_history(
            transaction_type, person_id, pageunits_free,
            pageunits_paid, pageunits_total,
            update_by=update_by, update_program=update_program,
            tstamp=tstamp,
            _override_job_id=_override_job_id)

        binds = {
            'job_id': id,
            'target_job_id': target_job_id,
            'description': description,
            'payment_tstamp': payment_tstamp,
            'bank_id': bank_id,
            'kroner': kroner
            }
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=paid_quota_transaction]
          (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                 ", ".join([":%s" % k for k in binds.keys()])),
                                 binds)


    def _alter_quota(self, person_id, pageunits_free=0, pageunits_paid=0,
                     pageunits_total=0):
        """Updates paid_quota_status.  Should not be called outside
        this class.  Use add_printjob/add_transaction so that the
        history table is also updated."""
        # pageunits should be negative for printjobs
        self.execute("""
        UPDATE [:table schema=cerebrum name=paid_quota_status]
        SET free_quota = free_quota + :pageunits_free,
            paid_quota = paid_quota + :pageunits_paid,
            total_pages = total_pages + :pageunits_total
        WHERE person_id=:person_id""", {
            'person_id': person_id,
            'pageunits_free': int(pageunits_free),  # Avoid db-driver 0 = NULL
            'pageunits_paid': int(pageunits_paid),
            'pageunits_total': int(pageunits_total)})

    def _change_history_owner(self, old_id, new_id):
	self.execute("""
        UPDATE [:table schema=cerebrum name=paid_quota_history]
        SET person_id=:new_id
        WHERE person_id=:old_id""", {
            'old_id': old_id,
	    'new_id': new_id})

    def _change_status_owner(self, old_id, new_id):
	self.execute("""
        UPDATE [:table schema=cerebrum name=paid_quota_status]
        SET person_id=:new_id
        WHERE person_id=:old_id""", {
            'old_id': old_id,
	    'new_id': new_id})

    def _delete_status(self, person_id):
	self.execute("""
	DELETE FROM [:table schema=cerebrum name=paid_quota_status]
	WHERE person_id=:person_id""",{
	    'person_id': int(person_id)})

    def _delete_history(self, job_id, entry_type):
        if entry_type == 'printjob':
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=paid_quota_printjob]
            WHERE job_id=:job_id""",{
                'job_id': int(job_id)})
        elif entry_type == 'transaction':
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=paid_quota_transaction]
            WHERE job_id=:job_id""",{
                'job_id': int(job_id)})
        else:
            raise ValueError("This method is private for a reason")
	self.execute("""
	DELETE FROM [:table schema=cerebrum name=paid_quota_history]
	WHERE job_id=:job_id""",{
	    'job_id': int(job_id)})
        

    def get_quoata_status(self, has_quota_filter=None):
        if has_quota_filter is not None:
            if has_quota_filter:
                where = "WHERE has_quota='T'"
            else:
                where = "WHERE has_quota='F'"
        else:
            where = ""
        return self.query(
            """SELECT person_id, has_quota, has_blocked_quota, weekly_quota,
                      max_quota, paid_quota, free_quota, total_pages
            FROM [:table schema=cerebrum name=paid_quota_status] %s""" % where)

    def get_history_payments(self, transaction_type=None, desc_mask=None,
                             bank_id_mask=None, fetchall=False,
                             person_id=None, order_by_job_id=False):
        binds = {
            'transaction_type': int(transaction_type or 0),
            'description': desc_mask,
            'bank_id': bank_id_mask,
            'person_id': person_id
            }
        where = []
        if transaction_type is not None:
            where.append("transaction_type=:transaction_type")
        if desc_mask is not None:
            where.append("description LIKE :description")
        if bank_id_mask is not None:
            where.append("bank_id LIKE :bank_id")
        if person_id is not None:
            where.append("person_id=:person_id")
        order_by = ""
        if order_by_job_id:
            order_by = "ORDER BY pqh.job_id"
        if where:
            where = "AND "+" AND ".join(where)
        else:
            where = ""
        return self.query(
            """SELECT pqh.job_id, transaction_type, person_id, description,
               bank_id, target_job_id, kroner
            FROM [:table schema=cerebrum name=paid_quota_transaction] pqt,
                 [:table schema=cerebrum name=paid_quota_history] pqh
            WHERE pqh.job_id=pqt.job_id %s %s""" % (where, order_by),
            binds, fetchall=fetchall)

    def get_history(self, job_id=None, person_id=None, tstamp=None,
                    target_job_id=None, before=None, after_job_id=None,
                    transaction_type=None):
        # In theory we could have one big LEFT JOIN search, but there
        # is a chance that it would give us a performance hit with
        # +1 million records in the database
        binds = {'job_id': job_id,
                 'after_job_id': after_job_id,
                 'transaction_type': transaction_type,
                 'person_id': person_id,
                 'tstamp': tstamp,
                 'before': before,
                 'target_job_id': target_job_id}
        where = []
        if isinstance(person_id, str) and person_id == 'NULL':   # TODO: We need a generic way for this
            where.append("person_id is NULL")            
        elif person_id:
            where.append("person_id=:person_id")
        if job_id:
            where.append("pqh.job_id=:job_id")
        elif after_job_id:
            where.append("pqh.job_id > :after_job_id")            
        if transaction_type:
            where.append("transaction_type=:transaction_type")
        if target_job_id:
            where.append("target_job_id=:target_job_id")
        if tstamp:
            where.append("tstamp >= :tstamp")
        if before:
            where.append("tstamp < :before")
        if where:
            where = "AND "+" AND ".join(where)
        else:
            where = ""
        ret = [r for r in self.query(
            """SELECT pqh.job_id, transaction_type, person_id, tstamp,
                  update_by, update_program, pageunits_free,
                  pageunits_paid, pageunits_total, target_job_id, description,
                  bank_id, kroner, payment_tstamp
            FROM [:table schema=cerebrum name=paid_quota_history] pqh,
                 [:table schema=cerebrum name=paid_quota_transaction] pqt
            WHERE pqh.job_id=pqt.job_id %s""" % where, binds,
            fetchall=False)]

        if not target_job_id:
            for r in self.query(
                """SELECT pqh.job_id, transaction_type, person_id,
                      tstamp, update_by, update_program, account_id,
                      pageunits_free, pageunits_paid, pageunits_total,
                      job_name, printer_queue, stedkode, spool_trace,
                      priss_queue_id, paper_type, pages
                FROM [:table schema=cerebrum name=paid_quota_history] pqh,
                     [:table schema=cerebrum name=paid_quota_printjob] pqp
                WHERE pqh.job_id=pqp.job_id %s""" % where, binds,
                fetchall=False):
                ret.append(r)

        ret.sort(lambda x,y: cmp(x[0], y[0]))

        return ret

    def get_pagecount_stats(self, tstamp_from, tstamp_to,
                            group_by=('stedkode',)):
        binds = {'tstamp_from': tstamp_from,
                 'tstamp_to': tstamp_to}
        if group_by:
            extra_cols = ", " + ", ".join(group_by)
            group_by = "GROUP BY " + ", ".join(group_by)
        else:
            group_by = extra_cols = ""
        qry = """SELECT count(*) AS jobs, sum(pageunits_free) AS free,
                  sum(pageunits_paid) AS paid, sum(pageunits_total) AS total %s
        FROM [:table schema=cerebrum name=paid_quota_history] pqh,
             [:table schema=cerebrum name=paid_quota_printjob] pqp
        WHERE pqh.job_id=pqp.job_id AND tstamp >= :tstamp_from AND
              tstamp < :tstamp_to
        %s""" % (extra_cols, group_by)
        return self.query(qry, binds)

    def get_payment_stats(self, tstamp_from, tstamp_to,
                          group_by=('transaction_type',)):
        binds = {'tstamp_from': tstamp_from,
                 'tstamp_to': tstamp_to}
        if group_by:
            extra_cols = ", " + ", ".join(group_by)
            group_by = "GROUP BY " + ", ".join(group_by)
        else:
            group_by = extra_cols = ""
        qry = """SELECT count(*) AS jobs, sum(pageunits_free) AS free,
            sum(pageunits_paid) AS paid, sum(kroner) AS kroner,
            sum(pageunits_total) AS total %s
        FROM [:table schema=cerebrum name=paid_quota_history] pqh,
             [:table schema=cerebrum name=paid_quota_transaction] pqt
        WHERE pqh.job_id=pqt.job_id AND tstamp >= :tstamp_from AND
              tstamp < :tstamp_to
        %s""" % (extra_cols, group_by)
        return self.query(qry, binds)

    
# arch-tag: 3e72fdb7-3f9f-41ca-bc3e-6d626b02ed45
