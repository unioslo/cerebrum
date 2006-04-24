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

"""
Site specific auth.py for UiO

"""

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth


class BofhdAuth(auth.BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for UiO.
    """

    # Temporary owner group is specified in trait_guest_owner trait,
    # and members of owner groups should be allowed to change password
    # for their guest users

    def _is_guest_owner(self, operator, account):
        # First check that account is a guest_account
        owner = account.get_trait(self.const.trait_guest_owner)
        if not owner or not owner['target_id']:
            return None
        # Let members of temporary owner group for guest accounts set password
        grp = Factory.get("Group")(self._db)
        grp.find(owner['target_id'])
        return self.is_group_member(operator, grp.group_name)
    
    def can_set_password(self, operator, account=None,
                         query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        if operator == account.entity_id:
            return True
        if self._no_account_home(operator, account):
           return True
        if self._is_guest_owner(operator, account):
            return True
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     account)
    
