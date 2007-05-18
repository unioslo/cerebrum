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
import cereconf
from Cerebrum import Utils
from Cerebrum.Entity import EntityName
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.auth import *
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode as AuthRoleOpCode

from Cerebrum.spine.Email import *
from Cerebrum.spine.EntityExternalId import EntityExternalId
from Cerebrum.spine.Entity import Entity
from Cerebrum.spine.Account import Account
from Cerebrum.spine.Person import Person
from Cerebrum.spine.OU import OU
from Cerebrum.spine.Group import Group
from Cerebrum.spine.Types import CodeType, OUPerspectiveType
from Cerebrum.spine.Commands import Commands
from Cerebrum.spine.EntityAuth import EntityAuth
from Cerebrum.spine.SpineLib import Database, SearchClass, DumpClass, SpineExceptions
import unittest
import sets

class Authorization(object):
    def __init__(self, user, database=None, credentials=None):
        import time
        t = time.time()
        self.db = database or Database.SpineDatabase()
        bofhdauth = BofhdAuth(self.db)
        self.uid = user.get_id()
        self.is_superuser = bofhdauth.is_superuser(self.uid)
        if not self.is_superuser:
            # Get the owner id of this account.
            account = Utils.Factory.get('Account')(self.db)
            account.find(self.uid)
            self.oid = account.owner_id

            # Make a list of the users credentials.
            credentials = credentials or bofhdauth._get_users_auth_entities(self.uid)

            # Add the magic groups cereweb_self and cereweb_public
            # to our list of credentials.
            group = Utils.Factory.get('Group')(self.db)
            group.find_by_name('cereweb_self')
            credentials.append(group.entity_id)
            group.clear()
            group.find_by_name('cereweb_public')
            credentials.append(group.entity_id)
            self.update_auths(credentials)

    def __del__(self):
        self.db.close()

    def has_permission(self, operation, target, attr=None):
        """Checks whether the owner of the session has access to run the
        specified operation on the given object with the provided attributes.
        See www.itea.ntnu.no/fuglane/index.php/Spine:Autorisasjonskravsdesign
        for a description (in Norwegian)"""

        if self.is_superuser:
            return True

        operation_full_name = "%s.%s" % (target.__class__.__name__, operation)

        # For debugging pursposes only.
        try:
            if '%s\n' % operation_full_name in open('/tmp/alfborge/spine_breakfile'):
                import pdb
                pdb.set_trace()
        except IOError:
            pass

        if self._is_unrestricted(target, operation, attr):
            return True

        if self._check_global(operation_full_name, attr):
            return True

        entity = self._get_entity(target)
        if entity:
            if self._check_entity(operation_full_name, attr, entity):
                return True

            if self._is_self(entity) and self._check_self(operation_full_name, attr):
                return True

        return False

    def _get_entity(self, target):
        """Find the entity of this target."""

        if isinstance(target, Entity):
            return target
        # Searchers and Dumpers have no entities.
        elif isinstance(target, SearchClass.SearchClass) or \
             isinstance(target, DumpClass.DumpClass):
            return None
        elif hasattr(target, 'get_auth_entity'):
            return target.get_auth_entity()
        else:
            return None

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
        tid = target.get_id()
        if tid == self.uid or tid == self.oid:
            return True
        return False

    def _is_unrestricted(self, target, operation, attr):
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

    def _check_global(self, operation, attr):
        return self._query_auth(operation, attr, None, 'global')

    def _check_self(self, operation, attr):
        return self._query_auth(operation, attr, None, 'self')

    def _check_entity(self, operation, attr, target):
        direct = self._check_direct(operation, attr, target.get_id())
        by_org = self._check_by_org(operation, attr, target)
        return direct or by_org

    def _check_direct(self, operation, attr, target_id):
        return self._query_auth(operation, attr, target_id, 'entity')
    
    def _check_by_org(self, operation, attr, target):
        perspective = OUPerspectiveType(self.db,
            name=cereconf.AUTH_OU_RECURSIVE_PERSPECTIVE)

        if isinstance(target, OU):
            if self._check_org_recursive(operation, attr, target, perspective, None):
                return True

        if isinstance(target, Account):
            # Accounts belong to a person or a group.  We don't use the
            # affiliations of the account.
            #
            # Do not use Account.get_owner since it takes about 30 seconds the
            # first time it's called.  We can't afford this if we want to run
            # the unit tests.
            account = Utils.Factory.get('Account')(self.db)
            account.find(target.get_id())
            person_id = account.owner_id
            target = Person(self.db, person_id)

        if isinstance(target, Person):
            for affiliation in target.get_affiliations():
                affiliation_type = affiliation.get_affiliation().get_name()
                ou = affiliation.get_ou()
                if self._check_org_recursive(operation, attr, ou, perspective, affiliation_type):
                    return True
        return False

    def _check_org_recursive(self, operation, attr, ou, perspective, affiliation_type):
        if not ou:
            return False

        if self._query_auth(operation, attr, ou.get_id(), 'entity', target_attr=affiliation_type):
            return True

        try:
            parent_ou = ou.get_parent(perspective)
        except SpineExceptions.NotFoundError, e:
            return False

        return self._check_org_recursive(operation, attr, parent_ou, perspective, affiliation_type)

    def _query_auth(self, operation, op_attr, target, target_type, target_attr=None):
        """We check if the user has access to run the operation with
        the given arguments or with no arguments (which means all arguments)."""
        op_attrs = [op_attr, None]
        target_attrs = [target_attr, None]
        for op_attr in op_attrs:
            for target_attr in target_attrs:
                if (target, target_type, target_attr,
                        operation, op_attr) in self.auths:
                    return True
        return False
    
class AuthTest(unittest.TestCase):
    credentials = []
    def __init__(self, *args, **vargs):
        super(AuthTest, self).__init__(*args, **vargs)

        self.db = Utils.Factory.get('Database')()
        self.db.cl_init(change_program='test')

        c_account = Utils.Factory.get('Account')(self.db)

        c_account.find_by_name('authtest')
        self.my_uid = c_account.entity_id
        self.my_oid = c_account.owner_id
        c_account.clear()

        c_account.find_by_name('authtes2')
        self.other_uid = c_account.entity_id
        self.other_oid = c_account.owner_id
        c_account.clear()

        group = Utils.Factory.get('Group')(self.db)
        credentials = []
        for credential in self.credentials:
            group.find_by_name(credential)
            credentials.append(group.entity_id)
            group.clear()

        s_account=Account(self.db, self.my_uid) # Hardcoded.
        self.auth=Authorization(s_account, self.db, credentials=credentials)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test__is_self(self):
        """Make sure _is_self works even when we operate against
        different database cursors."""
        new_db = Utils.Factory.get('Database')()
        assert new_db != self.db

        my_account = Account(new_db, self.my_uid)
        my_person = Person(new_db, self.my_oid)
        assert self.auth._is_self(my_account)
        assert self.auth._is_self(my_person)

    def test__attribute(self):
        assert self.auth._check_self('Account.set_shell', ('bash',))

    def test__check_self(self):
        """_check_self failed when called with attr = () instead of attr = None"""
        assert self.auth._check_self('Account.get_id', ())
        assert self.auth._check_self('Account.set_password', ('new',))

    def test__check_global(self):
        assert self.auth._check_global('Account.get_name', None)

    def test_my_types(self):
        my_account = Account(self.db, self.my_uid)
        my_person = Person(self.db, self.my_oid)
        my_external_ids = my_person.get_external_ids()
        account_operations = ['get_name', 'get_id', 'set_password']
        person_operations = ['get_external_ids']
        external_id_operations = ['get_id_type']

        for operation in account_operations:
            assert self.auth.has_permission(operation, my_account), operation

        for operation in person_operations:
            assert self.auth.has_permission(operation, my_person), operation

        for my_external_id in my_external_ids:
            for operation in external_id_operations:
                assert self.auth.has_permission(operation, my_external_id), operation

    def test_public(self):
        assert not self.auth.has_permission("get_external_ids",
                Person(self.db, self.other_oid))
        assert self.auth.has_permission("get_account_by_name",
                Commands(self.db))

class OrakelTest(AuthTest):
    credentials = ['cereweb_orakel']

    def __init__(self, *args, **vargs):
        super(OrakelTest, self).__init__(*args, **vargs)
        c_account = Utils.Factory.get('Account')(self.db)

        c_account.find_by_name('authtes3')
        self.ou_uid = c_account.entity_id
        self.ou_oid = c_account.owner_id
        c_account.clear()

        c_ou = Utils.Factory.get('OU')(self.db)
        self.ou_id = c_ou.search(name='OuTest')[0][0]
        self.child_ou_ids = [x[0] for x in c_ou.list_children(c_ou.const.perspective_kjernen, self.ou_id, recursive=True)]

    def test_orakel(self):
        assert self.auth.has_permission("set_password", Account(self.db, self.ou_uid))
        assert self.auth.has_permission("set_password", Account(self.db, self.ou_uid))
        assert self.auth.has_permission("set_description", Person(self.db, self.ou_oid))
        assert self.auth.has_permission("add_note", Person(self.db, self.ou_oid))
        assert self.auth.has_permission("set_description", Person(self.db, self.ou_oid))

    def test_create_person(self):
        assert self.auth.has_permission("create_person", OU(self.db, self.ou_id))
        for child_id in self.child_ou_ids:
            assert self.auth.has_permission("create_person", OU(self.db, child_id))


if __name__ == '__main__':
    unittest.main()

# vim: se sw=4 sts=4 et :
