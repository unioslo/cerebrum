# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
"""Bofhd_requests specific auth methods"""

from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.bofhd.errors import PermissionDenied


class RequestsAuth(BofhdAuth):

    def can_cancel_request(self, operator, req_id, query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        br = BofhdRequests(self._db, self.const)
        for r in br.get_requests(request_id=req_id):
            if r['requestee_id'] and int(r['requestee_id']) == operator:
                return True
        raise PermissionDenied("You are not requester")
