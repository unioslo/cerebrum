# -*- coding: utf-8 -*-

# Copyright 2018 University of Oslo, Norway
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

"""Constants for the PaidPrinterQuotas and PPQUtil modules."""


class _PaidQuotaTransactionTypeCode(Constants._CerebrumCode):
    """Mappings stored in the paid_quota_transaction_type_code table"""
    _lookup_table = \
        '[:table schema=cerebrum name=paid_quota_transaction_type_code]'
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
