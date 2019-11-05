# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.EmailLDAP import EmailLDAP

import re


class EmailLDAPUiAMixin(EmailLDAP):
    """Methods specific for UiA."""

    def __init__(self, db):
        super(EmailLDAPUiAMixin, self).__init__(db)
        self.target_hosts_cache = {}

    def get_target_info(self, row):
        """Return additional EmailLDAP-entry derived from L{row}.

        Return site-specific mail-ldap-information pertaining to the
        EmailTarget info in L{row}.

        @type row: db-row instance
        @param row:
          A db-row holding one result of L{list_email_targets_ext}.

        @rtype: dict
        @return:
          A dictinary mapping attributes to values for the specified
          EmailTarget in L{row}.
        """

        sdict = super(EmailLDAPUiAMixin, self).get_target_info(row)
        target_type = self.const.EmailTarget(int(row['target_type']))
        if target_type in (self.const.email_target_Sympa,):
            server_id = row["server_id"]
            if server_id is None:
                return sdict
            if server_id in self.target_hosts_cache:
                sdict['commandHost'] = self.target_hosts_cache[server_id]
            else:
                host = Factory.get("Host")(self._db)
                try:
                    host.find(server_id)
                    # XXX Postmaster said this was sufficient for now
                    if re.search('test', host.name):
                        sdict['commandHost'] = host.name + '.uio.no'
                    else:
                        sdict['commandHost'] = host.name + '.uia.no'
                    self.target_hosts_cache[server_id] = sdict['commandHost']
                except Errors.NotFoundError:
                    pass

        return sdict
