# -*- coding: iso-8859-1 -*-

"""Module that receives information about payment.  For security
resons it is recomended not to provide other commands in the same
bofhd instance.
"""

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import bofhd_pq_utils
from Cerebrum.modules.no.uio.printer_quota.PPQUtil import PPQUtil

class InvalidData(CerebrumError):
    pass

class BofhdExtension(object):
    all_commands = {}

    def __init__(self, server):
        self.db = server.db
        self.bu = bofhd_pq_utils.BofhdUtils(server)

    def get_help_strings(self):
        # We don't provide help as we're only supposed to be used from scripts
        return ({}, {}, {})
    
    def get_commands(self, uname):
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct(self)
        return commands

    def _handle_epay(self, operator, data):
        # TODO: add restrictions on remote IP and operator
        if not operator.remote_address[0].startswith("12"):
            raise CerebrumError, "Connection from unauthorized host"
        for k in ('fnr', 'kroner', 'intern-betaling-id',
                  'ekstern-betaling-id', 'betaling-datostempel'):
            if not data.has_key(k):
                raise InvalidData("Missing data-field: %s" % k)
        if not data['kroner'] > 0:
            raise InvalidData("kroner must be > 0")
        person_id = self.bu.find_pq_person(data['fnr'])
        ppq = PaidPrinterQuotas.PaidPrinterQuotas(self.db)
        try:
            ppq_info = ppq.find(person_id)
        except Errors.NotFoundError:
            raise bofhd_pq_utils.UserHasNoQuota("No quota_status entry for person")
        # TODO: vi skal alltid godta betaling her

        if ppq_info['has_quota'] != 'T':
            raise bofhd_pq_utils.UserHasNoQuota("has_quota!='T'")
        
        description = "epay:%s [id:%s]" % (data.get('bruker-ip', ''),
                                           data['intern-betaling-id'])
        pq_util = PPQUtil(self.db)
        try:
            pq_util.add_payment(person_id,
                                PPQUtil.EPAY,
                                data['ekstern-betaling-id'],
                                data['kroner'],
                                description,
                                payment_tstamp=data['betaling-datostempel'],
                                update_by=operator.get_entity_id())
        except self.db.DatabaseError, msg:
            raise InvalidData("Input caused DatabaseError:%s" % msg)
        return "OK"

    all_commands['new_data'] = None
    def new_data(self, operator, data_type, data):
        if data_type == PPQUtil.EPAY:
            return self._handle_epay(operator, data)
        else:
            raise CerebrumError, "Unknown data type: '%s'" % data_type

if __name__ == '__main__':  # For testing
    import xmlrpclib
    svr = xmlrpclib.Server("http://127.0.0.1:8001", encoding='iso8859-1')
    secret = svr.login("bootstrap_account", "test")
    data = {
        'betaling-datostempel': xmlrpclib.DateTime(),
        'ekstern-betaling-id': 'ekst. bet-id',
        #'fnr': '15057446495',
        'fnr': '19066747592',
        'kroner': 123.45,
        'intern-betaling-id': 'int.betalings-id',
        'bruker-ip': '129.240.1.1'
        }
    data = {'ekstern-betaling-id': '12345', 'fnr': '19066747592', 'kroner': 123.45, 'intern-betaling-id': '12345', 'bruker-ip': '123.123.123.123', 'betaling-datostempel': '2004-05-05 14:32:00'}
    print svr.run_command(secret, 'new_data', PPQUtil.EPAY, data)
    # select * from person_external_id where source_system=(select code from authoritative_system_code where code_str='FS');
