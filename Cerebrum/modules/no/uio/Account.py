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
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.utils import BofhdRequests


class AccountUiOMixin(Account.Account):
    """Account mixin class providing functionality specific to UiO.

    The methods of the core Account class that are overridden here,
    ensure that any Account objects generated through
    Cerebrum.Utils.Factory.get() provide functionality that reflects
    the policies of the University of Oslo.

    """

    def add_spread(self, spread):
        #
        # Pre-add checks
        #
        spreads = [int(r['spread']) for r in self.get_spread()]
        # All users in the 'ifi' NIS domain must also exist in the
        # 'uio' NIS domain.
        if spread == self.const.spread_ifi_nis_user \
               and int(self.const.spread_uio_nis_user) not in spreads:
            raise self._db.IntegrityError, \
                  "Can't add ifi spread to an account without uio spread."
        #
        # (Try to) perform the actual spread addition.
        ret = self.__super.add_spread(spread)
        #
        # Additional post-add magic
        #        
        if spread == self.const.spread_uio_imap:
            # Unless this account already has been associated with an
            # Cyrus EmailServerTarget, we need to do so.
            est = Email.EmailServerTarget(self._db)
            es = Email.EmailServer(self._db)
            is_on_cyrus = False
            try:
                est.find_by_entity(self.entity_id)
                es.find(est.email_server_id)
                if es.email_server_type == self.const.email_server_type_cyrus:
                    is_on_cyrus = True
            except Errors.NotFoundError:
                pass
            old_server = None
            if not is_on_cyrus:
                # Randomly choose which IMAP server the user should
                # reside on.
                old_server = est.email_server_id
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
            reqid = br.add_request(None,        # Requestor
                                   br.now, self.const.bofh_email_create,
                                   self.entity_id, est.email_server_id)
            if old_server:
                # Move user iff we chose a new server.  Add a
                # dependency on the create above.
                br.add_request(None,	# Requestor
                               br.now, self.const.bofh_email_will_move,
                               self.entity_id, est.email_server_id,
                               state_data = {'depend_req': reqid,
                                             'source_server': old_server})
        return ret

    def delete_spread(self, spread):
        #
        # Pre-remove checks
        #
        spreads = [int(r['spread']) for r in self.get_spread()]
        # All users in the 'ifi' NIS domain must also exist in the
        # 'uio' NIS domain.
        if spread == self.const.spread_uio_nis_user \
               and int(self.const.spread_ifi_nis_user) in spreads:
            raise self._db.IntegrityError, \
                  "Can't remove uio spread to an account with ifi spread."
        #
        # (Try to) perform the actual spread removal.
        ret = self.__super.add_spread(spread)
        return ret
