# -*- coding: iso-8859-1 -*-
# Copyright 2003 University of Oslo, Norway
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

""""""

import random

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum import Email
from Cerebrum.modules.bofhd.utils import BofhdRequests


class AccountUiOMixin(Account.Account):
    """Account mixin class providing functionality specific to UiO.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies of The University of Oslo.

    """

    def add_spread(self, spread):
        self.__super.add_spread(spread)
        if spread == self.const.spread_uio_imap:
            # If there is no EmailServerTarget registered for this
            # account, we need to assign one.
            est = Email.EmailServerTarget(self._db)
            try:
                est.find_by_entity(self.entity_id)
            except Errors.NotFoundError:
                # Randomly choose which IMAP server the user should
                # reside on.
                es = Email.EmailServer(self._db)
                imap_servs = []
                for svr in es.list_email_server_ext():
                    if (svr['server_type']
                        <> self.const.email_server_type_cyrus):
                        continue
                    if svr['name'] == 'mail-sg0':
                        # Reserved for test users.
                        continue
                    imap_servs.append(svr['server_id'])
                svr_id = random.choice(imap_servs)
                est.populate(svr_id)
                est.write_db()

            # Set quota.
            eq = Email.EmailQuota(self._db)
            try:
                eq.find_by_entity(self.entity_id)
            except Errors.NotFoundError:
                eq.populate(90, 100)
                eq.write_db()

            # Register self.const.bofh_email_create BofhdRequest
            br = BofhdRequests(self._db, self.const)
            br.add_request(None,        # Requestor
                           br.now, self.const.bofh_email_create,
                           self.entity_id, est.email_server_id)
