# -*- coding: iso-8859-1 -*-

import time

from Cerebrum import Account
from Cerebrum import Cache
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.cmd_param import Command, PersonId, SimpleString, FormatSuggestion, Integer
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.uio.printer_quota import PPQUtil
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import bofhd_pq_utils
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode

class Constants(Constants.Constants):
    auth_pquota_list_history = _AuthRoleOpCode(
        'pq_list_hist', 'List printer quota history')
    auth_pquota_off = _AuthRoleOpCode(
        'pq_off', 'Turn off printerquota')
    auth_pquota_undo = _AuthRoleOpCode(
        'pq_undo', 'Undo printjob')
    auth_pquota_update = _AuthRoleOpCode(
        'pq_update', 'Update printerquota')

class PQBofhdAuth(auth.BofhdAuth):

    # TBD: the current practice of auth.py to send operator as
    # entity-id for the authenticated user rather than the session
    # object should probably be changed to send the session object.
    # This way we can get access to the person_id of the authenticated
    # user, and perform checks based on this.

    def _query_person_permission(self, operator, operation, person_id, query_run_any):
        if not query_run_any:
            # get_commands (which uses query_run_any=True) is called
            # with account_id as argument.
            operator = operator.get_entity_id()
        if (self.is_superuser(operator) or
            self._has_operation_perm_somewhere(
            operator, operation)):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("permission denied")

    def can_pquota_list_history(self, operator, person=None, query_run_any=False):
        if query_run_any:
            return True
        if operator.get_owner_id() == person:
            # Everyone can list their own history
            return True
        return self._query_person_permission(operator,
                                             self.const.auth_pquota_list_history,
                                             person,
                                             query_run_any)

    def can_pquota_off(self, operator, person=None, query_run_any=False):
        if query_run_any:
            # Since our current permission criteria is not tied to a
            # target, we use the same check for any vs a specific
            # person
            pass
        return self._query_person_permission(operator,
                                             self.const.auth_pquota_off,
                                             person,
                                             query_run_any)

    def can_pquota_undo(self, operator, person=None, query_run_any=False):
        return self._query_person_permission(operator,
                                             self.const.auth_pquota_undo,
                                             person,
                                             query_run_any)

    def can_pquota_update(self, operator, person=None, query_run_any=False):
        return self._query_person_permission(operator,
                                             self.const.auth_pquota_update,
                                             person,
                                             query_run_any)

def format_time(field):
    fmt = "yyyy-MM-dd HH:mm"            # 16 characters wide
    return ':'.join((field, "date", fmt))

class BofhdExtension(object):
    all_commands = {}

    def __init__(self, server):
        self.server = server
        self.logger = bofhd_pq_utils.SimpleLogger('pq_bofhd.log')
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.tt_mapping = {}
        for c in self.const.fetch_constants(
            self.const.PaidQuotaTransactionTypeCode):
            self.tt_mapping[int(c)] = "%s" % c
        self.bu = bofhd_pq_utils.BofhdUtils(server)
        self.ba = PQBofhdAuth(self.db)
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*30)
        
    def get_help_strings(self):
        group_help = {
            'pquota': "Commands for administrating printer quotas",
            }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'pquota': {
            'pquota_status': 'Returnerer status for skriverkvoten',
            'jbofh_pquota_history': 'Returnerer 7 dagers historikk for utskrifter',
            'pquota_off': 'Turns off quota for a person',
            'pquota_update': 'Updates a persons free quota',
            'pquota_undo': 'Undo a whole, or part of a job',
            },
            }
        
        arg_help = {
            'person_id':
            ['person_id', 'Enter person id',
             """Enter person id as idtype:id.
If idtype=fnr, the idtype does not have to be specified.
The currently defined id-types are:
  - fnr : norwegian fødselsnummer."""],
            'quota_date': ['from_date', 'Enter from date'],
            'int_new_quota': ['new_quota', 'Enter new value for free_pages.'],
            'job_id': ['job_id', 'Enter job_id of job to undo'],
            'subtr_pages': ['num_pages', 'Number of pages to undo',
                            'To undo the entire job, leave blank'],
            'undo_why': ['why', 'Why', 'Why do you want to undo this job?']
            
            }
        return (group_help, command_help,
                arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()
    
    def get_commands(self, account_id):
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for k in self.all_commands.keys():
            tmp = self.all_commands[k]
            if tmp is not None:
                if tmp.perm_filter:
                    if not getattr(self.ba, tmp.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands

    # pquota status
    all_commands['pquota_status'] = Command(
        ("pquota", "status"), PersonId(),
        fs=FormatSuggestion("Has quota Blocked   Paid   Free\n"+
                            "%-9s %-9s %-6i %i",
                            ('has_quota', 'has_blocked_quota',
                            'paid_quota', 'free_quota')))
    def pquota_status(self, operator, person_id):
        # Everyone can access quota-status for anyone
        ppq_info = self.bu.get_pquota_status(
            self.bu.find_person(person_id))
        return {
            'has_quota': ppq_info['has_quota'],
            'has_blocked_quota': ppq_info['has_blocked_quota'],
            'paid_quota': ppq_info['paid_quota'],
            'free_quota': ppq_info['free_quota']
            }

    # We provide two methods for history data, one for jbofh, and one
    # for scripts
    def _pquota_history(self, operator, person_id, when):
        # when is number of days in the past
        self.ba.can_pquota_list_history(operator, person_id)
        ppq_info = self.bu.get_pquota_status(person_id)
        if when:
            when = self.db.Date(*( time.localtime(time.time()-3600*24*when)[:3]))

        ret = []
        ppq = PaidPrinterQuotas.PaidPrinterQuotas(self.db)
        for row in ppq.get_history(person_id=person_id, tstamp=when):
            t = dict([(k, row[k]) for k in row._keys()])
            t['transaction_type'] = self.tt_mapping[int(t['transaction_type'])]
            if t['update_by']:
                t['update_by'] = self.bu.get_uname(int(t['update_by']))
            ret.append(t)
        
        return ret
        
    all_commands['pquota_history'] = None
    def pquota_history(self, operator, person, when=None):
        return self._pquota_history(
            operator, self.bu.find_pq_person(person), when)

    all_commands['jbofh_pquota_history'] = Command(
        ("pquota", "history"), PersonId(),
        fs=FormatSuggestion("%8i %-7s %16s %-10s %-20s %5i %5i",
                            ('job_id', 'transaction_type',
                             format_time('tstamp'), 'update_by',
                             'data', 'pageunits_free',
                             'pageunits_paid'),
                            hdr="%-8s %-7s %-16s %-10s %-20s %-5s %-5s" %
                            ("JobId", "Type", "When", "By", "Data", "#Free",
                             "#Paid")),
        perm_filter='can_pquota_list_history')
    def jbofh_pquota_history(self, operator, person_id):
        when = 7              # Max days for cmd-client
        ret = []
        for r in self._pquota_history(
            operator, self.bu.find_person(person_id), when):
            tmp = {
                'job_id': r['job_id'],
                'transaction_type': r['transaction_type'],
                'tstamp': r['tstamp'],
                'pageunits_free': r['pageunits_free'],
                'pageunits_paid': r['pageunits_paid']}
            if not r['update_by']:
                r['update_by'] = r['update_program']
            tmp['update_by'] = r['update_by'][:10]
            if r['transaction_type'] == str(self.const.pqtt_printout):
                tmp['data'] = (
                    "%s:%s" % (r['printer_queue'][:10], r['job_name']))[:20]
            elif r['transaction_type'] == str(self.const.pqtt_quota_fill_pay):
                tmp['data'] = "%s:%s kr" % (r['description'][:10], r['kroner'])
            elif r['transaction_type'] == str(self.const.pqtt_quota_fill_free):
                tmp['data'] = r['description']
            elif r['transaction_type'] == str(self.const.pqtt_undo):
                tmp['data'] = "undo %s: %s" % (r['target_job_id'], r['description'])
            elif r['transaction_type'] == str(self.const.pqtt_quota_balance):
                tmp['data'] = "balance"
            ret.append(tmp)
        return ret

    all_commands['pquota_off'] = Command(
        ("pquota", "off"), PersonId(),
        perm_filter='can_pquota_off')
    def pquota_off(self, operator, person_id):
        person_id = self.bu.find_person(person_id)
        self.ba.can_pquota_off(operator, person_id)
        self.bu.get_pquota_status(person_id)
        ppq = PaidPrinterQuotas.PaidPrinterQuotas(self.db)
        ppq.set_status_attr(person_id, {'has_quota': False})
        self.logger.info("pquota_off for %i by %i" % (
            person_id, operator.get_entity_id()))
        return "OK, turned off quota for person_id=%i" % person_id

    all_commands['pquota_update'] = Command(
        ("pquota", "update"), PersonId(), Integer(help_ref='int_new_quota'),
        SimpleString(help_ref='undo_why'),
        perm_filter='can_pquota_update')
    def pquota_update(self, operator, person_id, new_value, why):
        try:
            new_value = int(new_value)
        except ValueError:
            raise CerebrumError, "%s is not a number" % new_value
        person_id = self.bu.find_person(person_id)
        self.ba.can_pquota_update(operator, person_id)
        self.bu.get_pquota_status(person_id)
        pu = PPQUtil.PPQUtil(self.db)
        # Throws subclass for CerebrumError, which bofhd.py will handle
        pu.set_free_pages(person_id, new_value, why,
                          update_by=operator.get_entity_id())
        self.logger.info("pquota_update for %i -> %i by %i (%s)" % (
            person_id, new_value, operator.get_entity_id(), repr(why)))
        return "OK, set free quota for %i to %s" % (person_id, new_value)

    all_commands['pquota_undo'] = Command(
        ("pquota", "undo"), PersonId(), Integer(help_ref='job_id'),
        Integer(help_ref='subtr_pages'), SimpleString(help_ref='undo_why'),
        perm_filter='can_pquota_undo')
    def pquota_undo(self, operator, person_id, job_id, num_pages, why):
        person_id = self.bu.find_person(person_id)
        self.ba.can_pquota_undo(operator, person_id)
        pu = PPQUtil.PPQUtil(self.db)
        # Throws subclass for CerebrumError, which bofhd.py will handle
        pu.undo_transaction(person_id, job_id, num_pages,
                            why, update_by=operator.get_entity_id())
        self.logger.info("pquota_undo for %i, job %s with %s pages by %i (%s)" % (
            person_id, job_id, num_pages, operator.get_entity_id(), repr(why)))
        return "OK"


if __name__ == '__main__':  # For testing
    import xmlrpclib
    svr = xmlrpclib.Server("http://127.0.0.1:8000", encoding='iso8859-1')
    secret = svr.login("bootstrap_account", "test")
    print svr.run_command(secret, 'pquota_status', '05107747682')
    print svr.run_command(secret, 'pquota_history', '05107747682')
    print svr.run_command(secret, 'pquota_status', '15035846422')
