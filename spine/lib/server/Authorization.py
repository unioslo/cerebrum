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

import sys
import cerebrum_path
from Cerebrum import Utils
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
import unittest
import sets

class Authorization(object):
    def __init__(self, user, database=None):
        self.db = database or Database.SpineDatabase()
        self.user = user
        self.user_owner = self.user.get_owner()
        self.groups = user.get_groups()
        cereweb_self = Commands(self.db).get_group_by_name('cereweb_self')
        cereweb_public = Commands(self.db).get_group_by_name('cereweb_public')
        self.groups.append(cereweb_self)
        self.groups.append(cereweb_public)
        self.credentials = [i.get_id() for i in [self.user]+self.groups]
        self.update_auths(self.credentials)
        self.is_superuser = self._is_superuser()

    def __del__(self):
        self.db.close()

    def has_permission(self, operation, target, attr=None):
        """Checks whether the owner of the session has access to run the
        specified operation on the given object with the provided attributes.
        See www.itea.ntnu.no/fuglane/index.php/Spine:Autorisasjonskravsdesign
        for a description (in Norwegian)"""

        if self.is_superuser:
            return True

        if self._is_unrestricted_operation(target, operation, attr):
            return True

        has_entity = is_entity = attribute = None
        operation_full_name = "%s.%s" % (target.__class__.__name__, operation)

        try:
            if '%s\n' % operation_full_name in open('/tmp/alfborge/spine_breakfile'):
                import pdb
                pdb.set_trace()
        except IOError:
            pass

        if not isinstance(target, Entity):
            attribute = target
            if hasattr(target, 'get_entity'):
                target = attribute.get_entity()
            elif hasattr(target, 'get_person'):
                target = attribute.get_person()
            elif hasattr(target, 'get_account'):
                target = attribute.get_account()
            else:
                attribute = None

        if isinstance(target, Entity):
            target_type = target.get_type().get_name()
            target_id = target.get_id()
            is_entity = True
        
        if is_entity:
            if self._check_type(operation_full_name, attr, target_type):
                return True
            if self._check_direct(operation_full_name, attr, target_id, target_type):
                return True
            if self._check_by_org(operation_full_name, attr, target, target_type):
                return True
            if self._is_self(target) and self._check_self(operation_full_name, attr, target_type):
                return True

    def update_auths(self, credentials):
        authrows = self.db.query(
            """SELECT
            target.entity_id AS target_id,
            target.target_type AS target_type,
            target.attr AS target_attr,
            oc.code_str AS operation,
            NULL AS operation_attr
            FROM
            auth_role role,
            auth_op_target target,
            auth_op_code oc,
            auth_operation op
            -- auth_op_attrs op_attr XXX LEFT JOIN
            WHERE role.entity_id IN ( %s )
            AND op.op_code = oc.code
            AND role.op_target_id = target.op_target_id
            AND op.op_set_id = role.op_set_id"""
            % ", ".join([str(i) for i in credentials]))
        self.auths = sets.Set([tuple(row) for row in authrows])

    def _is_self(self, target):
        if target.get_id() == self.user.get_id():
            return True
        if target.get_id() == self.user_owner.get_id():
            return True
        return False

    def _is_unrestricted_operation(self, target, operation, attr):
        """Helper method that returns true if the method is considered public,
        i.e. everyone is allowed to run it."""

        method = getattr(target, operation) 
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

        operation_full_name = "%s.%s" % (target.__class__.__name__, operation)
        return self._check_global(operation_full_name, attr)

    def _check_global(self, operation, attr):
        return self._query_auth(operation, attr, None, 'global')

    def _check_direct(self, operation, attr, target_id, target_type):
        return self._query_auth(operation, attr, target_id, target_type)

    def _check_type(self, operation, attr, target_type):
        return self._query_auth(operation, attr, None, target_type)

    def _check_self(self, operation, attr, target_type):
        return self._query_auth(operation, attr, None, "my_"+target_type)
    
    def _check_by_org(self, operation, attr, target, target_type):
        if isinstance(target, Person) or isinstance(target, Account):
            affs=[(a.get_ou().get_id(), a.get_affiliation().get_name())
                  for a in target.get_affiliations()]
            for (ou, aff) in affs:
                if self._query_auth(operation, attr, ou, target_type, target_attr=aff):
                    return True
        return False

    def _query_auth(self, operation, op_attr, target, target_type,
                   target_attr=None):
        """We first check if the user has access to run the operation with
        the given arguments.  Then we check if the user has access to run
        the operation without arguments."""
        op_attr = op_attr or None
        attr = (target, target_type, target_attr,
                operation, op_attr) in self.auths
        no_attr = (target, target_type, target_attr,
                operation, None) in self.auths
        return attr or no_attr
    
    def _is_superuser(self):
        bofhdauth = BofhdAuth(self.db)
        if bofhdauth.is_superuser(self.user.get_id()):
            return True

class AuthTest(unittest.TestCase):
    def __init__(self, *args, **vargs):
        super(AuthTest, self).__init__(*args, **vargs)

        self.my_person = 15971
        self.my_account = 15972
        self.ou_person = 36 # Person in an ou that my_account has orakel access to.
        self.ou_account = 37 # Account in an ou that my_account has orakel access to.
        self.db = Utils.Factory.get('Database')()
        self.db.cl_init(change_program='test')

        self.user=Account(self.db, self.my_account) # Hardcoded.
        self.auth=Authorization(self.user, self.db)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test__is_self(self):
        """Make sure _is_self works even when we operate against
        different database cursors."""
        new_db = Utils.Factory.get('Database')()
        assert new_db != self.db

        my_account = Account(new_db, self.my_account)
        my_person = Person(new_db, self.my_person)
        assert self.auth._is_self(my_account)
        assert self.auth._is_self(my_person)

    def test__check_self(self):
        """_check_self failed when called with attr = () instead of attr = None"""
        assert self.auth._check_self('Account.get_id', (), 'account')
        assert self.auth._check_self('Account.set_password', ('new',), 'account')

    def test__check_global(self):
        assert self.auth._check_global('Account.get_name', None)

    def test_orakel(self):
        assert self.auth.has_permission("set_password", Account(self.db, self.ou_account))
        assert self.auth.has_permission("set_password", Account(self.db, self.ou_account))
        assert self.auth.has_permission("set_description", Person(self.db, self.ou_person))
        assert not self.auth.has_permission("add_note", Person(self.db, self.ou_person))
        assert self.auth.has_permission("set_description", Person(self.db, self.ou_person))

    def test_my_types(self):
        my_account = Account(self.db, self.my_account)
        my_person = Person(self.db, self.my_person)
        my_external_id = my_person.get_external_ids()[0]
        account_operations = ['get_name', 'get_id', 'set_password']
        person_operations = ['get_external_ids']
        external_id_operations = ['get_id_type']

        for operation in account_operations:
            assert self.auth.has_permission(operation, my_account), operation

        for operation in person_operations:
            assert self.auth.has_permission(operation, my_person), operation

        for operation in external_id_operations:
            assert self.auth.has_permission(operation, my_external_id), operation

    def test_public(self):
        assert not self.auth.has_permission("get_external_ids",
                Person(self.db, self.ou_person))
        assert self.auth.has_permission("get_account_by_name",
                Commands(self.db))

if __name__ == '__main__':
    unittest.main()

# vim: se sw=4 sts=4 et :
