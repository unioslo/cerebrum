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

import string

from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.EmailLDAP import EmailLDAP

class EmailLDAPFeideGvsMixin(EmailLDAP):
    """Methods specific for UiO."""

    def __init__(self, db):
        self.__super.__init__(db)
        self.a_id2name = {}
  
    def get_target(self, entity_id, target_id):
        tmp_addr = self.aid2addr[self.targ2prim[target_id]]
        lp, dom = string.split(tmp_addr, '@')
        target = self.acc2name[entity_id][0]
        return "%s@%s" % (target, dom)


    def read_misc_target(self):
        p = Factory.get('Person')(self._db)
        p_id2name = {}
        for row in p.list_persons_name():
            p_id2name[int(row['person_id'])] = row['name']
        a = Factory.get('Account')(self._db)
        for row in a.list_accounts_owner():
            a_id = row['account_id']
            o_id = row['owner_id']
            if p_id2name.has_key(o_id):
                self.a_id2name[a_id] = p_id2name[o_id]

    def get_misc(self, entity_id, target_id):
        if  self.a_id2name.has_key(entity_id):
            return "name: %s" % self.a_id2name[entity_id]
