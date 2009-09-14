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
from Cerebrum.modules.bofhd.errors import PermissionDenied

from Cerebrum.Utils import Factory
Person_class = Factory.get("Person")
Account_class = Factory.get("Account")
Group_class = Factory.get("Group")
OU_class = Factory.get("OU")


class BofhdAuth(auth.BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for NTNU.
    """
    def _has_person_access(self, operator, target, operation, operation_attr=None):
        if not isinstance(target, Person_class):
            raise TypeError(
                "Can't handle target, expected type %s but got %s" % (Person_class, type(target)))

        return self._has_access(
            operator, target, self.const.auth_target_type_global_person,
            operation, operation_attr)

    def _has_account_access(self, operator, target, operation, operation_attr=None):
        if not isinstance(target, Account_class):
            raise TypeError(
                "Can't handle target, expected type %s but got %s" % (Account_class, type(target)))

        return self._has_access(
            operator, target, self.const.auth_target_type_global_account,
            operation, operation_attr)

    def _has_group_access(self, operator, target, operation, operation_attr=None):
        if not isinstance(target, Group_class):
            raise TypeError(
                "Can't handle target, expected type %s but got %s" % (Group_class, type(target)))

        return self._has_access(
            operator, target, self.const.auth_target_type_global_group,
            operation, operation_attr)

    def _has_ou_access(self, operator, target, operation, operation_attr=None):
        if not isinstance(target, OU_class):
            raise TypeError(
                "Can't handle target, expected type %s but got %s" % (OU_class, type(target)))

        if self._has_global_access(operator,
                                   operation,
                                   self.const.auth_target_type_global_ou,
                                   target.entity_id,
                                   operation_attr):
            return True
        
        return self._query_target_permissions(
            operator, operation, self.const.auth_target_type_ou, target.entity_id, None,
            operation_attr)

    def _has_access(self, operator, target, target_type, operation, operation_attr=None):
        if self.is_superuser(operator):
            return True

        if self._has_global_access(operator, operation, target_type,
                                   target.entity_id, operation_attr=operation_attr):
            return True

        return self._has_access_to_entity_via_ou(operator, operation,
                                                 target, operation_attr=operation_attr)

    def _has_entity_access(self, operator, target, operation, operation_attr=None):
        if isinstance(target, Person_class):
            return self._has_person_access(
                operator, target, operation, operation_attr=operation_attr)
        elif isinstance(target, Account_class):
            return self._has_account_access(
                operator, target, operation, operation_attr=operation_attr)
        elif isinstance(target, OU_class):
            return self._has_ou_access(
                operator, target, operation, operation_attr=operation_attr)
        elif isinstance(target, Group_class):
            return self._has_group_access(
                operator, target, operation, operation_attr=operation_attr)
        else:
            raise TypeError(
                "Can't handle target of type %s" % type(target))

    def _has_global_access(self, operator, operation, global_type, victim_id,
                           operation_attr=None):
        if self.is_superuser(operator):
            return True
        
        return super(BofhdAuth, self)._has_global_access(
            operator, operation, global_type, victim_id, operation_attr)

    def can_set_password(self, operator, target):
        operation = self.const.auth_set_password
        return self._has_account_access(operator, target, operation)

    def can_read_account(self, operator, target):
        operation = self.const.auth_account_read
        return self._has_account_access(operator, target, operation)

    def can_create_account(self, operator, target):
        operation = self.const.auth_account_create

        if isinstance(target, Person_class):
            return self._has_person_access(operator, target, operation)
        elif isinstance(target, Group_class):
            return self._has_group_access(operator, target, operation)
        else:
            raise TypeError(
                "Can't handle target of type %s" % type(target))

    def can_edit_account(self, operator, target):
        operation = self.const.auth_account_edit
        return self._has_account_access(operator, target, operation)

    def can_delete_account(self, operator, target):
        operation = self.const.auth_account_delete
        return self._has_account_access(operator, target, operation)

    def _get_ou(self, ou_id):
        ou = ou_id
        if isinstance(ou_id, str):
            ou_id = int(ou_id)

        if isinstance(ou_id, (int,long)):
            ou = OU_class(self._db)
            ou.find(ou_id)
        return ou

    def can_edit_affiliation(self, operator, target, ou_id, affiliation_id):
        operation = self.const.auth_affiliation_edit

        ou = self._get_ou(ou_id)
        affiliation = self.const.PersonAffiliation(affiliation_id)

        if not self._has_ou_access(operator, ou, operation, operation_attr=str(affiliation)):
            return False

        if isinstance(target, Person_class):
            if not target.get_affiliations():
                return True

            return self._has_person_access(operator, target, operation)
        elif isinstance(target, Account_class):
            return self._has_account_access(operator, target, operation)
        else:
            raise TypeError(
                "Can't handle target of unknown type (%s)" % type(target))

    def can_edit_external_id(self, operator, target, external_id_type):
        operation = self.const.auth_external_id_edit

        return self._has_entity_access(
                operator, target, operation, operation_attr=external_id_type)

    def can_read_external_id(self, operator, target, external_id_type):
        operation = self.const.auth_external_id_read

        return self._has_entity_access(
                operator, target, operation, operation_attr=external_id_type)

    def can_edit_homedir(self, operator, target, spread_id):
        return True

    def can_read_person(self, operator, target):
        operation = self.const.auth_person_read
        return self._has_person_access(operator, target, operation)

    def can_edit_person(self, operator, target):
        operation = self.const.auth_person_edit
        return self._has_person_access(operator, target, operation)

    def can_create_person(self, operator):
        return self._has_global_access(
            operator, self.const.auth_person_create,
            self.const.auth_target_type_global_person, None)

    def can_delete_person(self, operator, target):
        operation = self.const.auth_person_delete
        return self._has_person_access(operator, target, operation)

    def can_syncread_account(self, operator, spread, auth_method):
        if self._query_target_permissions(
            operator, self.const.auth_account_syncread,
            self.const.auth_target_type_spread, int(spread), None,
            operation_attr=str(auth_method)):
            return True
        raise PermissionDenied("Can't bulk read accounts")
    
    def can_syncread_group(self, operator, spread):
        if self._query_target_permissions(
            operator, self.const.auth_group_syncread,
            self.const.auth_target_type_spread, int(spread), None):
            return True
        if self._has_global_access(
            operator, self.const.auth_group_syncread,
            self.const.auth_target_type_global_group, None):
            return True
        raise PermissionDenied("Can't bulk read groups")
            
    
    def can_syncread_ou(self, operator, spread=None):
        if spread is not None:
            if self._query_target_permissions(
                operator, self.const.auth_ou_syncread,
                self.const.auth_target_type_spread, int(spread), None):
                return True
        if self._has_global_access(
            operator, self.const.auth_ou_syncread,
            self.const.auth_target_type_global_ou, None):
            return True
        raise PermissionDenied("Can't bulk read OUs")

    #def can_syncread_alias(self, operator, spread=None):
    #    return self._has_global_access(
    #        operator, self.const.auth_account_syncread,
    #        self.const.auth_target_type_global_alias, None)
    
    def can_syncread_person(self, operator, spread=None):
        if spread is not None:
            if self._query_target_permissions(
                operator, self.const.auth_person_syncread,
                self.const.auth_target_type_spread, int(spread), None):
                return True
        if self._has_global_access(
            operator, self.const.auth_person_syncread,
            self.const.auth_target_type_global_person, None):
            return True
        raise PermissionDenied("Can't bulk read Persons")
            
