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

from Cerebrum.spine.Types import CodeType
from Cerebrum.spine.Entity import Entity
from Cerebrum.spine.Account import Account
from Cerebrum.spine.Person import Person
from Cerebrum.spine.Commands import Commands
from Cerebrum.spine.EntityAuth import EntityAuth
from Cerebrum.spine.SpineLib import Database
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd import auth, utils
import sets

class Authorization(object):
    def __init__(self, account):
        self._db = Database.SpineDatabase()
        self.account = account
        self.account_id = self.account.get_id()

    def __del__(self):
        self._db.close()

    def check_permission(self, obj, method_name, *args):
        """Checks whether the owner of the session has access to run the
        specified method on the given object with the args provided.  See
        https://www.itea.ntnu.no/fuglane/index.php/Spine:Autorisasjonskravsdesign
        for en dokumentasjon av autorisasjonssjekken"""

        bofhdauth = auth.BofhdAuth(self._db)

        if self.account.is_superuser() or bofhdauth.is_superuser(self.account):
            return True

        m = getattr(obj, method_name) 
        cls = obj.__class__ 
        operation = utils._AuthRoleOpCode("%s.%s" % (cls.__name__, method_name))

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

        # Could the method escalate the righs of account?
        # FIXME: A TEST MUST BE IMPLEMENTED!

        ## Does the object have it's own check_permission?
        ## m.check_permission overrides obj.check_permission
        ## FIXME: Should these be able to DENY permission?
        ## FIXME: We need to define an interface for this.
        #if hasattr(m, 'check_permission'):
        #    m.check_permission(self.account, args) and return True
        #elif hasattr(obj, 'check_permission'):
        #    obj.check_permission(self.account, method_name) and return True

        # Does self.account have user access to this object?
        if self.has_user_access(operation, obj):
            return True

        # Har brukeren tilgang til å utføre operasjonen som konsekvens av tilgangsnivå
        ## Har brukeren tilgang til objektet som følge av tilknytning? True = Success. 

        if self.has_access(operation, obj):
            return True
        return False 

    def has_user_access(self, operation, object):
        ok = False

        if isinstance(object, Account):
            ok = object.get_id() == self.account_id
            # account.owner_id() == group && self.account_id in group.members
        elif isinstance(object, Person):
            ok = self.account.get_owner().get_id() == object.get_id()
        elif isinstance(object, Commands): # A subset of Commands is public.
            ok = True

        if ok:
            op_set = auth.BofhdAuthOpSet(self._db)
            op_set.find_by_name('own_account')
            if operation in [utils._AuthRoleOpCode(x[0]) for x in op_set.list_operations()]:
                return True

    def has_access(self, operation, object):
        if isinstance(object, Entity):
            return False
        elif isinstance(object, Commands):
            return False
        else:
            return False
# arch-tag: d6e64578-943c-11da-98e6-fad2a0dc4525
