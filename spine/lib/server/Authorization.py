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
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthOpSet, BofhdAuthRole
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode as AuthRoleOpCode
Entity = Factory.get("Entity")
Account = Factory.get("Account")
Person = Factory.get("Person")
Group = Factory.get("Group")

from Cerebrum.spine.Types import CodeType
from Cerebrum.spine.Commands import Commands
from Cerebrum.spine.EntityAuth import EntityAuth
from Cerebrum.spine.SpineLib import Database
import sets

class Authorization(object):
    def __init__(self, account, database=None):
        self._db = database or Database.SpineDatabase()
        self.account = account

    def __del__(self):
        self._db.close()

    def is_superuser(self, bofhdauth):
        if bofhdauth.is_superuser(self.account.entity_id):
            return True

    def is_public(self, cls, obj, m):
        # Is the method public?
        if hasattr(m, 'signature_public'):
            if m.signature_public is True:
                return True
            else:    # m.signature_public is False, which
                pass # overrides obj.signature_public
        elif getattr(obj, 'signature_public', False) is True:
            return True
        # CodeTypes are public.
        if issubclass(cls, CodeType):
            return True

    def check_permission(self, obj, method_name, *args):
        """Checks whether the owner of the session has access to run the
        specified method on the given object with the args provided.  See
        https://www.itea.ntnu.no/fuglane/index.php/Spine:Autorisasjonskravsdesign
        for en dokumentasjon av autorisasjonssjekken"""

        return True # Disablet p� grunn av programmeringsfeil.
        bofhdauth = BofhdAuth(self._db)
        if self.is_superuser(bofhdauth): return True

        m = getattr(obj, method_name) 
        cls = obj.__class__ 
        operation = AuthRoleOpCode("%s.%s" % (cls.__name__, method_name))

        if self.is_public(cls, obj, m): return True

        # Could the method escalate the righs of account?
        # FIXME: A TEST MUST BE IMPLEMENTED!

        # Command objects are not entities and must be handled separately.
        if isinstance(object, Commands) and has_access_to_command(operation):
            return True
        
        # Does self.account have user access to this object?
        if self.has_user_access(operation, obj, bofhdauth):
            return True

        # Har brukeren tilgang til å utføre operasjonen som konsekvens av tilgangsnivå
        ## Har brukeren tilgang til objektet som følge av tilknytning? True = Success. 

        if self.has_access(operation, obj, bofhdauth=bofhdauth):
            return True

        return False 

    def has_access_to_command(self, operation):
        # Test public commands.
        op_set = BofhdAuthOpSet(self._db)
        op_set.find_by_name('public')
        operations = [AuthRoleOpCode(x[0]) for x in op_set.list_operations()]
        if operation in operations:
            return True

        op_role = BofhdAuthRole(self._db)
        roles = op_role.list(entity_ids=self.account.entity_id)
        for s, set, t in roles:
            op_set.find(set)
            operations = [AuthRoleOpCode(x[0]) for x in op_set.list_operations()]
            if operation in operations:
                return True
        
    def has_user_access(self, operation, target):
        ok = False

        if isinstance(target, Account):
            ok = target.entity_id == self.account.entity_id
            # account.owner_id() == group && self.account.entity_id in group.members
        elif isinstance(target, Person):
            ok = self.account.owner_id == target.entity_id

        if ok:
            op_set = BofhdAuthOpSet(self._db)
            op_set.find_by_name('own_account')
            operations = [AuthRoleOpCode(x[0]) for x in op_set.list_operations()]
            if operation in operations:
                return True

    def has_access(self, operation, target, bofhdauth):
        # Find out who has access to target
        # Intersect with self.account and it's groups, etc.
        # If not null, find out what operations self.account has access to on target
        # Intersect with operation
        if isinstance(target, Account) or isinstance(target, Person):
            # Is operator allowed to perform 'operation' on one of the OUs
            # associated with the target?
            if bofhdauth._has_access_to_entity_via_ou(
                    self.account.entity_id, operation, target):
                return True


# arch-tag: d6e64578-943c-11da-98e6-fad2a0dc4525
