# -*- coding: utf-8 -*-
# Copyright 2004-2018 University of Oslo, Norway
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

from Cerebrum.modules.bofhd.errors import CerebrumError

class UnknownDataType(CerebrumError):
    # bad parameter to bohfd_pq_payment.new_data
    pass

class InvalidPaymentData(CerebrumError):
    # Illegal data to PPQUtil.add_payment
    pass

class InvalidQuotaData(CerebrumError):
    # The specified quota data values are illegal
    pass

class MissingData(CerebrumError):
    # bofhd exception: some required data was missing
    pass

class IllegalUndoRequest(CerebrumError):
    # Some data to the undo call was illegal
    pass

class UserHasNoQuota(CerebrumError):
    # The user in question has no quota.  Returned by pquota_status
    pass

class NotFoundError(CerebrumError):
    # The person etc. was not found
    pass
