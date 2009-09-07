# -*- coding: iso-8859-1 -*-

# Copyright 2009 University of Oslo, Norway
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
Site specific auth.py for NTNU

"""

from Cerebrum.modules.bofhd import auth


class BofhdAuth(auth.BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for NTNU.
    """
    def can_set_password(self, operator, target):
        return True

    def can_read_account(self, operator, account):
        return True

    def can_create_account(self, operator):
        return True

    def can_edit_account(self, operator, target):
        return True

    def can_delete_account(self, operator, target):
        return True

    def can_edit_affiliation(self, operator, target, ou_id, affiliation_id):
        return True

    def can_edit_external_id(self, operator, target, external_id_type):
        return True

    def can_read_external_id(self, operator, target, external_id_type):
        return True

    def can_edit_homedir(self, operator, target, spread_id):
        return True

    def can_read_person(self, operator, person):
        return True

    def can_edit_person(self, operator, person):
        return True

    def can_create_person(self, operator):
        return True

    def can_delete_person(self, operator, person):
        return True

    def can_haz_cheezeburger(self, lol, cat):
        return True

    def can_syncread_account(self, operator, spread, auth_method):
        return self._query_target_permissions(
            operator, self.const.auth_account_syncread,
            self.const.auth_target_type_spread, int(spread), None,
            operation_attr=str(auth_method))
    
    def can_syncread_group(self, operator, spread):
        return self._query_target_permissions(
            operator, self.const.auth_account_syncread,
            self.const.auth_target_type_spread, int(spread), None)
    
    def can_syncread_ou(self, operator, spread=None):
        if spread is not None:
            return self._query_target_permissions(
                operator, self.const.auth_account_syncread,
                self.const.auth_target_type_spread, int(spread), None)
        else:
            return self._has_global_access(
                operator, self.const.auth_account_syncread,
                self.const.auth_target_type_global_ou, None)

    #def can_syncread_alias(self, operator, spread=None):
    #    return self._has_global_access(
    #        operator, self.const.auth_account_syncread,
    #        self.const.auth_target_type_global_alias, None)
    
    def can_syncread_person(self, operator, spread=None):
        if spread is not None:
            return self._query_target_permissions(
                operator, self.const.auth_account_syncread,
                self.const.auth_target_type_spread, spread, None)
        else:
            return self._has_global_access(
                operator, self.const.auth_account_syncread,
                self.const.auth_target_type_global_person, None)
