from Cerebrum import Constants
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory

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
                      max_quota, paid_quota, free_quota
            FROM [:table schema=cerebrum name=paid_quota_status]
            WHERE person_id=:person_id""", {'person_id': person_id})

    def new_quota(self, person_id, has_quota=False,
                  has_blocked_quota=False):
        """Register person in the paid_quota_status table"""
        binds = {
            'person_id': person_id,
            'has_quota': has_quota and 'T' or 'F',
            'has_blocked_quota': has_blocked_quota and 'T' or 'F',
            'paid_quota': 0,
            'free_quota': 0,
            'total_pages': 0}

        self.execute("""
        INSERT INTO [:table schema=cerebrum name=paid_quota_status]
          (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                 ", ".join([":%s" % k for k in binds.keys()])),
                                 binds)

    def set_status_attr(self, person_id, attrs):
        set = []
        binds = {'person_id': person_id}
        for k in attrs.keys():
            set.append("%s=:%s" % (k, k))
            if k in ('has_quota', 'has_blocked_quota'):
                binds[k] = attrs[k] and 'T' or 'F'
            else:
                binds[k] = attrs[k]                
        set = ", ".join(set)
        self.execute("""
        UPDATE [:table schema=cerebrum name=paid_quota_status]
        SET %s
        WHERE person_id=:person_id""" % set, binds)

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
                           tstamp=None):

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
        description=None, bank_id=None, kroner=0, payment_tstamp=None):
        """Register an entry in the paid_quota_transaction table.
        Should not be called directly.  Use
        PPQUtil. add_payment/undo_transaction"""

        if ((not (update_by or update_program)) or
            (update_by and update_program)):
            raise CerebrumError, "Must set update_by OR update_program"

        # Update quota
        self._alter_quota(person_id, pageunits_free=pageunits_free,
                          pageunits_paid=pageunits_paid)

        # register history entries
        id = self._add_quota_history(
            transaction_type, person_id, pageunits_free,
            pageunits_paid, pageunits_free+pageunits_paid,
            update_by=update_by, update_program=update_program)

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
            'pageunits_free': pageunits_free,
            'pageunits_paid': pageunits_paid,
            'pageunits_total': pageunits_total})

    def delete_history(self, job_id):
        pass

    def get_history_payments(self, transaction_type=None, desc_mask=None,
                             bank_id_mask=None, fetchall=False):
        binds = {
            'transaction_type': int(transaction_type or 0),
            'description': desc_mask,
            'bank_id': bank_id_mask
            }
        where = []
        if transaction_type:
            where.append("transaction_type=:transaction_type")
        if desc_mask:
            where.append("description LIKE :description")
        if bank_id_mask:
            where.append("bank_id LIKE :bank_id")
        if where:
            where = "AND "+" AND ".join(where)
        else:
            where = ""
        return self.query(
            """SELECT transaction_type, person_id, description, bank_id
            FROM [:table schema=cerebrum name=paid_quota_transaction] pqt,
                 [:table schema=cerebrum name=paid_quota_history] pqh
            WHERE pqh.job_id=pqt.job_id %s""" % where, binds, fetchall=fetchall)

    def get_history(self, job_id=None, person_id=None, tstamp=None,
                    target_job_id=None):
        # In theory we could have one big LEFT JOIN search, but there
        # is a chance that it would give us a performance hit with
        # +1 million records in the database
        binds = {'job_id': job_id,
                 'person_id': person_id,
                 'tstamp': tstamp,
                 'target_job_id': target_job_id}
        where = []
        if person_id:
            where.append("person_id=:person_id")
        if job_id:
            where.append("pqh.job_id=:job_id")
        if target_job_id:
            where.append("target_job_id=:target_job_id")
        if tstamp:
            where.append("tstamp >= :tstamp")
        if where:
            where = "AND "+" AND ".join(where)
        else:
            where = ""
        
        ret = [r for r in self.query(
            """SELECT pqh.job_id, transaction_type, person_id, tstamp,
                  update_by, update_program, pageunits_free,
                  pageunits_paid, target_job_id, description, bank_id,
                  kroner
            FROM [:table schema=cerebrum name=paid_quota_history] pqh,
                 [:table schema=cerebrum name=paid_quota_transaction] pqt
            WHERE pqh.job_id=pqt.job_id %s""" % where, binds,
            fetchall=False)]

        if not target_job_id:
            for r in self.query(
                """SELECT pqh.job_id, transaction_type, person_id, tstamp,
                      update_by, update_program, pageunits_free,
                      pageunits_paid, job_name, printer_queue, stedkode,
                      spool_trace, priss_queue_id, paper_type, pages
                FROM [:table schema=cerebrum name=paid_quota_history] pqh,
                     [:table schema=cerebrum name=paid_quota_printjob] pqp
                WHERE pqh.job_id=pqp.job_id %s""" % where, binds,
                fetchall=False):
                ret.append(r)

        ret.sort(lambda x,y: cmp(x[0], y[0]))

        return ret

    def get_pagecount_stats(self, tstamp_from, tstamp_to, group_by=('stedkode',)):
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
        WHERE pqh.job_id=pqp.job_id AND tstamp >= :tstamp_from AND tstamp < :tstamp_to
        %s""" % (extra_cols, group_by)
        return self.query(qry, binds)

    def get_payment_stats(self, tstamp_from, tstamp_to):
        binds = {'tstamp_from': tstamp_from,
                 'tstamp_to': tstamp_to}
        qry = """SELECT count(*) AS jobs, sum(pageunits_free) AS free,
            sum(pageunits_paid) AS paid, sum(kroner) AS kroner, transaction_type
        FROM [:table schema=cerebrum name=paid_quota_history] pqh,
             [:table schema=cerebrum name=paid_quota_transaction] pqt
        WHERE pqh.job_id=pqt.job_id AND tstamp >= :tstamp_from AND tstamp < :tstamp_to
        GROUP BY transaction_type"""
        return self.query(qry, binds)
    
