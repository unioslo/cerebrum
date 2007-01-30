# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.auth import *
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode as AuthRoleOpCode

from Cerebrum.spine.Email import *
from Cerebrum.spine.EntityExternalId import EntityExternalId
from Cerebrum.spine.Entity import Entity
from Cerebrum.spine.Account import Account
from Cerebrum.spine.Person import Person
from Cerebrum.spine.Group import Group
from Cerebrum.spine.Types import CodeType
from Cerebrum.spine.Commands import Commands
from Cerebrum.spine.EntityAuth import EntityAuth
from Cerebrum.spine.SpineLib import Database

class Authorization(object):
    def __init__(self, account, database=None):
        self._db = database or Database.SpineDatabase()
        self.bofhdauth = BofhdAuth(self._db)
        self.account = account
        self.superuser = self.is_superuser()

    def __del__(self):
        self._db.close()

    def is_superuser(self):
        if self.bofhdauth.is_superuser(self.account.get_id()):
            return True
        
    def has_user_access(self, target, operation, *args):
        """Checks if the logged in user is trying to access his own account
        or person object.  In that case, he can do the operations defined in
        the *mySelf* operation set.
        """
        ok = False

        account_id = self.account.get_id()
        owner_id = self.account.get_owner().get_id() 
        if isinstance(target, Account):
            ok = account_id == target.get_id() 
        elif isinstance(target, Person):
            ok = owner_id == target.get_id()
        elif isinstance(target, EntityExternalId):
            ok = owner_id == target.get_entity().get_id()
        elif isinstance(target, EmailTarget):
            ok = account_id == target.get_entity().get_id()

        if ok:
            op_set = BofhdAuthOpSet(self._db)
            op_set.find_by_name('mySelf')
            operations = [AuthRoleOpCode(x[0]) for x in op_set.list_operations()]
            if operation in operations:
                return True

    def has_access(self, target, operation, *args):
        """Check if the session owner (logged in user) has permission to run
        operation(args) on the target."""

        # Returns a list containing the id of the account and the groups the
        # account is a member of.
        auth_entities = self.bofhdauth._get_users_auth_entities(self.account.get_id())

        bar = BofhdAuthRole(self._db)
        roles = bar.list(entity_ids=auth_entities)
        if roles:
            op_set = BofhdAuthOpSet(self._db)
            for role_id, set_id, target_id in roles:
                op_set.find(set_id)
                operations = [AuthRoleOpCode(x[0]) for x in op_set.list_operations()]
                if operation in operations:
                    aot = BofhdAuthOpTarget(self._db)
                    aot.find(target_id)
                    if aot.target_type == 'ou':
                        if self.has_access_through_ou(target_id, target):
                            return True
                    elif aot.target_type == 'account':
                        if target.get_id() == target_id:
                            return True
                    return True

    def has_access_through_ou(self, operation, target):
        """Check if the session owner (logged in user) has permission to 
        target through the ou."""
        # FIXME: What does this really do?
        if isinstance(target, Account):
            ceTarget = Factory.get("Account")(self._db)
        elif isinstance(target, Person):
            ceTarget = Factory.get("Person")(self._db)
        else:
            return False

        ceTarget.find(target.get_id())

        if self.bofhdauth._has_access_to_entity_via_ou(
                self.account.get_id(), operation, ceTarget):
            return True

    def is_public(self, target, method_name, operation, *args):
        """Helper method that returns true if the method is considered public,
        i.e. everyone is allowed to run it."""

        method = getattr(target, method_name) 
        if hasattr(method, 'signature_public'):
            if method.signature_public is True:
                return True
            else:    # method.signature_public is False, which
                pass # overrides target.signature_public
        elif getattr(target, 'signature_public', False) is True:
            return True
        # CodeTypes are public.
        if issubclass(target.__class__, CodeType):
            return True

        op_set = BofhdAuthOpSet(self._db)
        op_set.find_by_name('public')
        operations = [AuthRoleOpCode(x[0]) for x in op_set.list_operations()]
        if operation in operations:
            return True

    def has_permission(self, target, method_name, *args):
        """Checks whether the owner of the session has access to run the
        specified method on the given object with the args provided.  See
        https://www.itea.ntnu.no/fuglane/index.php/Spine:Autorisasjonskravsdesign
        for a description (in Norwegian)"""

        if self.superuser: return True

        # Could the method escalate the righs of account?
        # FIXME: A TEST MUST BE IMPLEMENTED!

        operation = AuthRoleOpCode("%s.%s" % (target.__class__ .__name__, method_name))

        if self.is_public(target, method_name, operation, *args): return True
        if self.has_user_access(target, operation, *args): return True
        if self.has_access(target, operation, *args): return True

        return False 

    def can_return(self, value):
        """Filter out objects the currently logged in user is not allowed to return.
        Currently this is only Struct-values, and only the superuser is allowed to
        return these.
        """
        if self.superuser: return True

        if type(value) == type([]):
            for v in value[:]:
                if not self.can_return(v):
                    value.remove(v)
            # We've removed the values that can't be returned from the value list, so
            # it should be safe to return it.  (It's been changed in place).
            return True 
        elif value.__class__.__name__.endswith('Struct'):
            # Structs contain data and must be filtered before they can be
            # returned to users.  Not implemented yet.
            return False
        else:
            return True

# vim: se sw=4 sts=4 et :
