# -*- coding: utf-8 -*-

# Copyright 2004-2016 University of Oslo, Norway
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

"""Module that receives information about payment.  For security
resons it is recomended not to provide other commands in the same
bofhd instance.
"""

import cereconf

from Cerebrum import Errors

from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import bofhd_pq_utils
from Cerebrum.modules.no.uio.printer_quota import errors
from Cerebrum.modules.no.uio.printer_quota.PPQUtil import PPQUtil


class BofhdExtension(BofhdCommandBase):

    all_commands = {}

    @property
    def logger(self):
        try:
            return self.__pq_logger
        except AttributeError:
            self.__pq_logger = bofhd_pq_utils.SimpleLogger('pq_bofhd.log')
            return self.__pq_logger

    @property
    def bu(self):
        try:
            return self.__pq_utils
        except AttributeError:
            self.__pq_utils = bofhd_pq_utils.BofhdUtils(self.db, self.const)
            return self.__pq_utils

    @property
    def epay_user(self):
        try:
            return self.__epay_user
        except AttributeError:
            self.__epay_user = int(
                self.bu.get_account(cereconf.BOFHD_EPAY_USER).entity_id)
            return self.__epay_user

    @classmethod
    def get_help_strings(cls):
        # We don't provide help as we're only supposed to be used from scripts
        return ({}, {}, {})

    def _handle_epay(self, operator, data):
        if operator.remote_address[0] not in cereconf.BOFHD_EPAY_REMOTE_IP:
            raise PermissionDenied("Connection from unauthorized host")
        if operator.get_entity_id() != self.epay_user:
            raise PermissionDenied("Unauthorized user")
        for k in ('fnr', 'kroner', 'intern-betaling-id',
                  'ekstern-betaling-id', 'betaling-datostempel'):
            if k not in data:
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

    #
    # new_data
    #
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
    data = {
        'ekstern-betaling-id': '12345',
        'fnr': '12345678901',
        'kroner': 123.45,
        'intern-betaling-id': '12345',
        'bruker-ip': '123.123.123.123',
        'betaling-datostempel': '2004-05-05 14:32:00',
    }
    print svr.run_command(secret, 'new_data', PPQUtil.EPAY, data)
