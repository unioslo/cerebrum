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

# Other errors:
# PermissionDenied

################# OLD JUNK ######################

##    raise InvalidData("Missing data-field: %s" % k)
##    raise InvalidData("kroner must be > 0")
##    raise bofhd_pq_utils.UserHasNoQuota("No quota_status entry for person")
##    raise bofhd_pq_utils.UserHasNoQuota("has_quota!='T'")
##    raise InvalidData("Input caused DatabaseError:%s" % msg)
##    raise CerebrumError, "Unknown data type: '%s'" % data_type

##    raise ValueError, "Cannot %s negative quota" % op
##    raise ValueError, "quota already at that value"
##    raise ValueError("page_units must be > 0")
##    raise CerebrumError, "Undo already registered for that job"
##    raise CerebrumError, "Unknown target_job_id"
##    raise CerebrumError, "Can only undo print jobs"
##    raise CerebrumError, "Cannot undo more pages than was in the job"
##    raise ValueError, "oops, page_units=%i" % page_units

## bofhd_pq_cmds.py:  raise bofhd_pq_utils.BadQuotaValue(msg)
## bofhd_pq_cmds.py:  raise bofhd_pq_utils.BadQuotaValue(msg)
## bofhd_pq_payment.py:  raise CerebrumError, "Connection from unauthorized host"
## bofhd_pq_payment.py:  raise InvalidData("Missing data-field: %s" % k)
## bofhd_pq_payment.py:  raise InvalidData("kroner must be > 0")
## bofhd_pq_payment.py:  raise bofhd_pq_utils.UserHasNoQuota("No quota_status entry for person")
## bofhd_pq_payment.py:  raise bofhd_pq_utils.UserHasNoQuota("has_quota!='T'")
## bofhd_pq_payment.py:  raise InvalidData("Input caused DatabaseError:%s" % msg)
## bofhd_pq_payment.py:  raise CerebrumError, "Unknown data type: '%s'" % data_type
## bofhd_pq_utils.py:  raise UserHasNoQuota("User has no quota")
## bofhd_pq_utils.py: raise NotFound("No person with fnr=%s" % fnr)
## bofhd_pq_utils.py: raise CerebrumError, "Unknown person_id type"
## bofhd_pq_utils.py:  raise NotFound, "Unknown id_type"
## bofhd_pq_utils.py:  raise NotFound, "Could not find person with %s=%s" % (
## bofhd_pq_utils.py:  raise CerebrumError, "ID not unique %s=%s" % (id_type, id_data)
## bofhd_pq_utils.py:  raise NotImplementedError, "unknown id_type: '%s'" % id_type
## bofhd_pq_utils.py:  raise CerebrumError(
## PaidPrinterQuotas.py:  raise CerebrumError, "Must set update_by OR update_program"
## PPQUtil.py:  raise ValueError, "Cannot %s negative quota" % op
## PPQUtil.py:  raise ValueError, "quota already at that value"
## PPQUtil.py:  raise ValueError("page_units must be > 0")
## PPQUtil.py:  raise CerebrumError, "Undo already registered for that job"
## PPQUtil.py:  raise CerebrumError, "Unknown target_job_id"
## PPQUtil.py:  raise CerebrumError, "Can only undo print jobs"
## PPQUtil.py:  raise CerebrumError, "Cannot undo more pages than was in the job"
## PPQUtil.py:  raise ValueError, "oops, page_units=%i" % page_units

# arch-tag: 1856266e-803a-4667-af3b-ac4c4a657110
