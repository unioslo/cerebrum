# -*- coding: iso-8859-1 -*-

"""Module that receives information about payment.  For security
resons it is recomended not to provide other commands in the same
bofhd instance.
"""

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import bofhd_pq_utils
from Cerebrum.modules.no.uio.printer_quota import errors
from Cerebrum.modules.no.uio.printer_quota.PPQUtil import PPQUtil

class BofhdExtension(object):
    all_commands = {}

    def __init__(self, server):
        self.db = server.db
        self.bu = bofhd_pq_utils.BofhdUtils(server)
        self.epay_user = int(
            self.bu.get_account(cereconf.BOFHD_EPAY_USER).entity_id)
        self.logger = bofhd_pq_utils.SimpleLogger('pq_bofhd.log')

    def get_help_strings(self):
        # We don't provide help as we're only supposed to be used from scripts
        return ({}, {}, {})
    
    def get_commands(self, uname):
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct(self)
        return commands

    def _handle_epay(self, operator, data):
        if operator.remote_address[0] not in cereconf.BOFHD_EPAY_REMOTE_IP:
            raise PermissionDenied, "Connection from unauthorized host"
        if operator.get_entity_id() != self.epay_user:
            raise PermissionDenied, "Unauthorized user"
        for k in ('fnr', 'kroner', 'intern-betaling-id',
                  'ekstern-betaling-id', 'betaling-datostempel'):
            if not data.has_key(k):
                raise errors.MissingData("Missing data-field: %s" % k)
        if not data['kroner'] > 0:
            raise errors.InvalidPaymentData("kroner must be > 0")
        person_id = self.bu.find_pq_person(data['fnr'])
        ppq = PaidPrinterQuotas.PaidPrinterQuotas(self.db)
        try:
            ppq.find(person_id)
        except Errors.NotFoundError:
            # We allways accept payments as our callee may have
            # trouble reversing the payment transaction at this point.
            ppq.new_quota(person_id)

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
            raise errors.InvalidPaymentData(
                "Input caused DatabaseError:%s" % msg)
        self.logger.info("_handle_epay: %s" % str(data))
        return "OK, data with intern-betaling-id=%s registered" % (
            data['intern-betaling-id'])

    all_commands['new_data'] = None
    def new_data(self, operator, data_type, data):
        if data_type == PPQUtil.EPAY:
            return self._handle_epay(operator, data)
        else:
            raise errors.UnknownDataType("Unknown data type: '%s'" % data_type)

if __name__ == '__main__':  # For testing
    import xmlrpclib
    svr = xmlrpclib.Server("http://127.0.0.1:8001", encoding='iso8859-1')
    secret = svr.login("bofhdepay", "test")
    data = {'ekstern-betaling-id': '12345', 'fnr': '12345678901', 'kroner': 123.45, 'intern-betaling-id': '12345', 'bruker-ip': '123.123.123.123', 'betaling-datostempel': '2004-05-05 14:32:00'}
    print svr.run_command(secret, 'new_data', PPQUtil.EPAY, data)
    # select * from person_external_id where source_system=(select code from authoritative_system_code where code_str='FS');

# arch-tag: 1ae465b8-d991-4437-ba55-b6b1ab947ec9
