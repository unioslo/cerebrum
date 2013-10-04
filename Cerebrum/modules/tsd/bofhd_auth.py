# -*- coding: iso-8859-1 -*-
# Copyright 2013 University of Oslo, Norway
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
"""The access control in TSD.

In TSD, you have the user groups:

- superusers: The system administrators.

- Project Administrators (PA): Those who could administrate their own project.

- Project Members (PM): Those who are only members of a project. Should only
  be able to modify some of their own information.

"""

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum.modules.bofhd.auth import BofhdAuth

class TSDBofhdAuth(BofhdAuth):
    """The BofhdAuth class for TSD."""

    def can_generate_otpkey(self, operator, account, query_run_any=False):
        """If the operator is allowed to generate a new OTP key for a given
        account."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        # TODO: give the user itself access to regenerate the OTP key
        raise PermissionDenied('Only superusers could regenerate OTP keys')
