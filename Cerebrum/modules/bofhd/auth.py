# -*- coding: iso-8859-1 -*-

# Copyright 2003-2010 University of Oslo, Norway
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
"""The functionality to be used for bofhd and other services for handling access
control for viewing and editing data in Cerebrum. The control could be quite
fine grained, with the downside of being a bit complex.

Overview
========

The auth module consists of the parts:

- Operations that should be allowed or not for given operators. Operations are
  Cerebrum Constants, and the base constants are located in
  Cerebrum/modules/bofhd/utils.py. The operations are not used directly, but is
  handled by BofhdAuth through different auth-methods.

- Operation Sets (OpSets) that contain operations that fits together, e.g. all
  operations that is needed for Local IT accounts. Authorization is delegated
  through OpSets and not directly by single operations. An OpSet is therefore
  linking to different operation constants.

  OpSets can be seen in bofhd through `access list_opsets` and to see all
  operations in an OpSet run `access show_opset OPSET`.

  The different Cerebrum instances have their own OpSets.

- Roles are given to entities, which means that the entitiy is authorized for a
  given OpSet. The roles could be given global access, but most of them are set
  for a certain *target*, e.g. for a given OU, group or disk.

  An example could be that the group matnat-drift is granted access to the
  LocalIT OpSet, but only for the OU of MatNat. This means that all members of
  the group matnat-drift are authorized for the LocalIT operations, but only for
  the accounts and persons located at MatNat.

  Roles are manipulated by `access grant` and `access revoke` in bofhd. The
  entity that executes an access command needs to be authorized to execute it
  through a role.

  Note that roles given to groups means that every member of the group is
  authorized for the OpSet. Also note that superusers are not authorized through
  roles and OpSets, but instead the superuser group is given hardcoded access in
  the different auth commands. You would therefore not find any superuser role.

Operations (BofhdAuth)
----------------------

The different operations for what is allowed to be done. The operations are only
handled inside the BofhdAuth methods. Services that uses BofhdAuth would only
see different auth methods, e.g. can_view_trait(), which is itself making use of
operations to check if the operator have the requested access.

An example is the bofhd command 'user_history', which calls
BofhdAuth.can_show_history(). The auth method will check if the operator has
access to the user by the operation 'auth_view_history' (or 'view_history')
through either an OU or a disk.

Some operations have the need for *attributes*. An example of this is the
operation 'modify_spread', where the attribute decide what kind of spread it
should be allowed to modify. Note that the attributes could change between the
OpSets.

The different auth methods rely on some common methods for querying for the
permissions. The methods start with '_query', in addition to methods like
_list_target_permissions.

Operation Sets (BofhdAuthOpSet)
-------------------------------

Sets of operations for making it easier to delegate access control. For
instance, a specific group or account could be delegated an OpSet 'LocalIT',
which could be an operation set with all the different operations the staff at
local IT would need in their work.

OpSets are handled by BofhdAuthOpSet, and is stored in the table
*auth_operation_set*, while the operations that belongs to an OpSet is
referenced to in the table L{auth_operation}. Operation attributes, e.g. for
setting constraints for an operation, is put in L{auth_op_attrs}.

Roles (BofhdAuthRole)
---------------------

Roles are authorizations given to entities. The role gives an entity access to a
given OpSet for either a given target or globally. The entity could for instance
be an account or a group (which gives all direct members of the group access),
and the target could for instance be an OU, group or a disk.

In the database
===============

The operations are Cerebrum constants, but is also put in the table
L{auth_operation}

- Operations are put in L{auth_operation}. Some operations have certain
  attributes, which are put in L{auth_op_attrs}.

- OpSets are put in L{auth_operation_set}.

- Roles are put in L{auth_role}, and their targets are put in L{auth_op_target}.

"""

import re

import cerebrum_path
import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Constants
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import Factory, mark_update
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests



class AuthConstants(Constants._CerebrumCode):
    # TODO: this looks like a duplicate of utils._AuthRoleOpCode.  Cleanup!
    _lookup_table = '[:table schema=cerebrum name=auth_op_code]'
    pass


class BofhdAuthOpSet(DatabaseAccessor):
    """Methods for updating auth_operation_set, auth_operation and
    auth_op_attrs which specifies what operations may be performed."""
    __metaclass__ = mark_update
    __read_attr__ = ('__in_db', 'const')
    __write_attr__ = ('op_set_id', 'name')
    dontclear = ('const',)

    def __init__(self, database):
        super(BofhdAuthOpSet, self).__init__(database)
        self.const = Factory.get('Constants')(database)

    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)

    def clear(self):
        self.clear_class(BofhdAuthOpSet)
        self.__updated = []

    def find(self, id):
        self.name, self.op_set_id = self.query_1("""
        SELECT name, op_set_id
        FROM [:table schema=cerebrum name=auth_operation_set]
        WHERE op_set_id=:id""", {'id': id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        id = self.query_1("""
        SELECT op_set_id
        FROM [:table schema=cerebrum name=auth_operation_set]
        WHERE name=:name""", {'name': name})
        self.find(id)

    def populate(self, name):
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.name = name

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.op_set_id = int(self.nextval('entity_id_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=auth_operation_set]
            (op_set_id, name) VALUES (:os_id, :name)""", {
                'os_id': self.op_set_id, 'name': self.name})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=auth_operation_set]
            SET name=:name
            WHERE op_set_id=:os_id""", {
                'os_id': self.op_set_id, 'name': self.name})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_operation_set]
        WHERE op_set_id=:os_id""", {'os_id': self.op_set_id})
        self.clear()

    def add_operation(self, op_code):
        op_id = int(self.nextval('entity_id_seq'))
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_operation]
        (op_code, op_id, op_set_id)
        VALUES (:code, :op_id, :op_set_id)""", {
            'code': int(op_code), 'op_id': op_id, 'op_set_id': self.op_set_id})
        return op_id

    def del_operation(self, op_code, op_id=-1):
        extra = ''
        if op_id != -1:
            extra = ' AND op_id=:op_id'

        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_operation]
        WHERE op_code=:op_code AND op_set_id=:op_set_id%s""" % extra, {
            'op_code': int(op_code),
            'op_set_id': self.op_set_id,
            'op_id': int(op_id)
        })

    def add_op_attrs(self, op_id, attr):
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_op_attrs] (op_id, attr)
        VALUES (:op_id, :attr)""", {
            'op_id': op_id, 'attr': attr})

    def del_op_attrs(self, op_id, attr):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_op_attrs]
        WHERE op_id=:op_id AND attr=:attr""", {
            'op_id': int(op_id), 'attr': attr})
    
    def list(self):
        return self.query("""
        SELECT op_set_id, name
        FROM [:table schema=cerebrum name=auth_operation_set]""")

    def list_operations(self):
        return self.query("""
        SELECT op_code, op_id, op_set_id
        FROM [:table schema=cerebrum name=auth_operation]
        WHERE op_set_id=:op_set_id""", {'op_set_id': self.op_set_id})

    def list_operation_attrs(self, op_id):
        return self.query("""
        SELECT attr
        FROM [:table schema=cerebrum name=auth_op_attrs]
        WHERE op_id=:op_id""", {'op_id': op_id})


class BofhdAuthOpTarget(DatabaseAccessor):
    """Methods for updating auth_op_target with information
    identifying targets which operations may be performed on."""

    __metaclass__ = mark_update
    __read_attr__ = ('__in_db', 'const')
    __write_attr__ = ('entity_id', 'target_type', 'attr', 'op_target_id')
    dontclear = ('const',)

    def __init__(self, database):
        super(BofhdAuthOpTarget, self).__init__(database)
        self.const = Factory.get('Constants')(database)

    def clear_class(self, cls):
        for attr in cls.__read_attr__:
            if hasattr(self, attr):
                if attr not in getattr(cls, 'dontclear', ()):
                    delattr(self, attr)
        for attr in cls.__write_attr__:
            if attr not in getattr(cls, 'dontclear', ()):
                setattr(self, attr, None)

    def clear(self):
        self.clear_class(BofhdAuthOpTarget)
        self.__updated = []

    def delete(self):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_op_target]
        WHERE op_target_id=:id""", {'id': self.op_target_id})
        self.clear()

    def find(self, id):
        self.op_target_id, self.entity_id, self.target_type, self.attr = \
        self.query_1("""
        SELECT op_target_id, entity_id, target_type, attr
        FROM [:table schema=cerebrum name=auth_op_target]
        WHERE op_target_id=:id""", {'id': id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def populate(self, entity_id, target_type, attr=None):
        self.__in_db = False
        self.entity_id = entity_id
        self.target_type = target_type
        self.attr = attr

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.op_target_id = int(self.nextval('entity_id_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=auth_op_target]
            (op_target_id, entity_id, target_type, attr) VALUES
            (:t_id, :e_id, :t_type, :attr)""", {
                't_id': self.op_target_id, 'e_id': self.entity_id,
                't_type': self.target_type, 'attr': self.attr})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=auth_op_target]
            SET target_type=:t_type, attr=:attr, entity_id=:e_id
            WHERE op_target_id=:t_id""", {
                't_id': self.op_target_id, 'e_id': self.entity_id,
                't_type': self.target_type, 'attr': self.attr})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def list(self, target_id=None, target_type=None, entity_id=None, attr=None):
        ewhere = []
        if entity_id is not None:
            ewhere.append("entity_id=:entity_id")
        if target_id not in (None, [], (),):
            if isinstance(target_id, (list, tuple)):
                tmp = " IN (%s)" % ", ".join([str(int(x)) for x in target_id])
            else:
                tmp = " = %d" % target_id
            ewhere.append("op_target_id %s" % tmp)
        if target_type is not None:
            ewhere.append("target_type=:target_type")
        if attr is not None:
            ewhere.append("attr=:attr")
        if ewhere:
            ewhere = "WHERE %s" % " AND ".join(ewhere)
        else:
            ewhere = ""
        return self.query("""
        SELECT op_target_id, entity_id, target_type, attr
        FROM [:table schema=cerebrum name=auth_op_target]
        %s
        ORDER BY entity_id""" % ewhere, {
            'entity_id': entity_id,
            'target_id': target_id,
            'target_type': target_type,
            'attr': attr})

class BofhdAuthRole(DatabaseAccessor):
    """Methods for updating the auth_role table with information
    about who has certain permissions to certain targets."""

    def __init__(self, database):
        super(BofhdAuthRole, self).__init__(database)

    def grant_auth(self, entity_id, op_set_id, op_target_id):
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_role]
        (entity_id, op_set_id, op_target_id)
        VALUES (:e_id, :os_id, :t_id)""", {
            'e_id': entity_id, 'os_id': op_set_id, 't_id': op_target_id})

    def revoke_auth(self, entity_id, op_set_id, op_target_id):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_role]
        WHERE entity_id=:e_id AND op_set_id=:os_id AND op_target_id=:t_id""", {
            'e_id': entity_id, 'os_id': op_set_id, 't_id': op_target_id})

    def list(self, entity_ids=None, op_set_id=None, op_target_id=None):
        """Return info about where entity_id has permissions.
        entity_id may be a list of entities """
        ewhere = []
        if entity_ids is not None:
            if not isinstance(entity_ids, (list, tuple)):
                entity_ids = [entity_ids]
            ewhere.append("entity_id IN (%s)" % 
                          ", ".join(["%i" % int(i) for i in entity_ids]))
        if op_set_id is not None:
            ewhere.append("op_set_id=:op_set_id")
        if op_target_id is not None:
            ewhere.append("op_target_id=:op_target_id")
        sql = """
        SELECT DISTINCT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role]"""
        if ewhere:
            sql += " WHERE (%s) " % " AND ".join(ewhere)

        return self.query(sql, {'op_set_id': op_set_id,
                                'op_target_id': op_target_id, })

    def list_owners(self, target_ids):
        """Return info about who owns the given target_ids"""
        if not isinstance(target_ids, (list, tuple)):
            target_ids = [target_ids]
        if not target_ids:
            return ()
        return self.query("""
        SELECT DISTINCT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role]
        WHERE op_target_id IN (%s)""" % ", ".join(["%i" % i for i in target_ids]))


class BofhdAuth(DatabaseAccessor):
    """Defines methods that are used by bofhd to determine whether an operator
    is allowed to perform a given action.

    The query_run_any parameter is used to determine if operator has this
    permission somewhere. It is used to filter available commands in bofhds
    get_commands(), and if it is True, the method should return either True or
    False, and not throw PermissionDenied exceptions. Note that this variable
    should NOT be used a security measure!

    """

    def __init__(self, database):
        super(BofhdAuth, self).__init__(database)
        self.const = Factory.get('Constants')(database)
        self._group_member_cache = Cache.Cache(mixins = [Cache.cache_timeout],
                                               timeout = 60)
        self._users_auth_entities_cache = Cache.Cache(mixins = [Cache.cache_timeout],
                                               timeout = 60)
        group = Factory.get('Group')(self._db)
        group.find_by_name(cereconf.BOFHD_SUPERUSER_GROUP)
        self._superuser_group = group.entity_id
        self._any_perm_cache = Cache.Cache(mixins=[Cache.cache_mru,
                                                   Cache.cache_slots,
                                                   Cache.cache_timeout],
                                           size=500,
                                           timeout=60*60)

    def _get_uname(self, entity_id):
        """Return a human-friendly representation of entity_id."""

        try:
            account = Factory.get("Account")(self._db)
            account.find(int(entity_id))
            return account.account_name
        except Errors.NotFoundError:
            return "id=" + str(entity_id)
    # end _get_uname


    def _get_gname(self, entity_id):
        try:
            group = Factory.get("Group")(self._db)
            group.find(int(entity_id))
            return group.group_name
        except Errors.NotFoundError:
            return "id=" + str(entity_id)
    # end _get_gname
        

    def is_superuser(self, operator_id, query_run_any=False):
        if operator_id in self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP):
            return True
        return False

    def is_schoolit(self, operator, query_run_any=False):
        if self.is_superuser(operator, query_run_any):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator,
                                              self.const.auth_set_password)
        return False

    def is_postmaster(self, operator, query_run_any=False):
        # Rather than require an operation as an argument, we pick a
        # suitable value which all postmasters ought to have.
        # auth_email_create seems appropriate.
        if self.is_superuser(operator, query_run_any):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator,
                                              self.const.auth_email_create)
        return self._has_target_permissions(operator,
                                            self.const.auth_email_create,
                                            self.const.auth_target_type_global_maildomain,
                                            None, None)
    
    def is_studit(self, operator, query_run_any=False):
        if operator in self._get_group_members(cereconf.BOFHD_STUDADM_GROUP):
            return True
        return False

    def is_group_owner(self, operator, operation, entity, operation_attr=None):
        if self._has_target_permissions(operator, operation,
                                        self.const.auth_target_type_group,
                                        int(entity.entity_id), None,
                                        operation_attr=operation_attr):
            return True
        if self._has_global_access(operator, operation,
                                   self.const.auth_target_type_global_group,
                                   entity.entity_id,
                                   operation_attr=operation_attr):
            return True

        raise PermissionDenied("%s has no access to group %s" %
                               (self._get_uname(operator),
                                self._get_gname(entity.entity_id)))
    # end is_group_owner
        
    def is_group_member(self, operator, groupname):
        if operator in self._get_group_members(groupname):
            return True
        return False

    def is_account_owner(self, operator, operation, entity, operation_attr=None):
        """See if operator has access to entity.  entity can be either
        a Person or Account object.  First check if operator is
        allowed to perform operation on one of the OUs associated with
        Person or Account.  If that fails, and the entity is an
        Account, check if the account is owned by a group and if the
        operator is a member of that group. If that fails check operator's
        access to the account's disk. Returns True for success and raises
        exception PermissionDenied for failure."""

        if self._has_access_to_entity_via_ou(operator, operation, entity,
                                             operation_attr=operation_attr):
            return True
        if not isinstance(entity, Factory.get('Account')):
            raise PermissionDenied("No access to person")
        if entity.owner_type == self.const.entity_group:
            grp = Factory.get("Group")(self._db)
            grp.find(entity.owner_id)
            if self.is_group_member(operator, grp.group_name):
                return True
        disk = self._get_user_disk(entity.entity_id)
        if disk and disk['disk_id']:
            return self._query_disk_permissions(operator, operation,
                                                self._get_disk(disk['disk_id']),
                                                entity.entity_id,
                                                operation_attr=operation_attr)
        else:
            if self._has_global_access(operator, operation,
                                       self.const.auth_target_type_global_host,
                                       entity.entity_id, operation_attr=operation_attr):
                return True
            raise PermissionDenied("No access to account")

    def can_set_disk_quota(self, operator, account=None, unlimited=False,
                           forever=False, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_disk_quota_set)
        if forever:
            self.is_account_owner(operator, self.const.auth_disk_quota_forever,
                                  account)
        if unlimited:
            self.is_account_owner(operator, self.const.auth_disk_quota_unlimited,
                                  account)
        return self.is_account_owner(operator, self.const.auth_disk_quota_set,
                                     account)

    def can_set_disk_default_quota(self, operator, host=None, disk=None,
                                   query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_disk_def_quota_set)
        if ((host is not None and self._has_target_permissions(
            operator, self.const.auth_disk_def_quota_set,
            self.const.auth_target_type_host, host.entity_id, None))
            or
            (disk is not None and self._has_target_permissions(
            operator, self.const.auth_disk_def_quota_set,
            self.const.auth_target_type_disk, disk.entity_id, None))):
            return True
        raise PermissionDenied("No access to disk")

    def can_show_disk_quota(self, operator, account=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_disk_quota_show)
        return self.is_account_owner(operator, self.const.auth_disk_quota_show,
                                     account)

    def can_set_person_user_priority(self, operator, account=None,
                                     query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator) or operator == account.entity_id:
            return True
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     account)

    def can_set_trait(self, operator, trait=None, ety=None, target=None,
                      query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        raise PermissionDenied("Not allowed to set trait")

    def can_clear_name(self, operator, person=None, source_system=None,
                       query_run_any=False):
        """If operator is allowed to remove a person's name from a given source
        system."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied('Not allowed to clear name')

    def can_remove_trait(self, operator, trait=None, ety=None, target=None,
                         query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        raise PermissionDenied("Not allowed to remove trait")

    def can_view_trait(self, operator, trait=None, ety=None, target=None,
                       query_run_any=False):
        """Access to view traits. Default is that operators can see their own
        person's and user's traits."""
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        if ety and ety.entity_id == operator:
            return True
        account = Factory.get('Account')(self._db)
        account.find(operator)
        if ety and ety.entity_id == account.owner_id:
            return True        
        raise PermissionDenied("Not allowed to see trait")

    def can_get_student_info(self, operator, person=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        # auth_view_studentinfo is not tied to a target
        if self._has_operation_perm_somewhere(
            operator, self.const.auth_view_studentinfo):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not authorized to view student info")

    def can_get_contact_info(self, operator, person=None, contact_type=None,
                             query_run_any=False):
        """If an operator is allowed to see contact information for a given
        person, i.e. phone numbers."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        # check for permission through opset
        if self._has_target_permissions(operator,
                                        self.const.auth_view_contactinfo,
                                        self.const.auth_target_type_host,
                                        person.entity_id, person.entity_id):
            return True
        # The person itself should be able to see it:
        account = Factory.get('Account')(self._db)
        account.find(operator)
        if person.entity_id == account.owner_id:
            return True
        raise PermissionDenied("Not allowed to see contact info")

    def can_add_contact_info(self, operator, entity_id=None, 
                             contact_type=None, query_run_any=False):
        """Checks if an operator is allowed to manually add contact information
        to an entity."""
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        # Hide command if not in the above groups
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to add contact info")

    def can_remove_contact_info(self, operator, entity_id=None, 
                                contact_type=None, source_system=None,
                                query_run_any=False):
        """Checks if an operator is allowed to remove contact information."""
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        # Hide command if not in the above groups
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to remove contact info")

    def can_create_person(self, operator, ou=None, affiliation=None,
                          query_run_any=False):
        if (self.is_superuser(operator) or
            self._has_target_permissions(operator,
                                         self.const.auth_create_user,
                                         self.const.auth_target_type_host,
                                         None, None) or
            self._has_target_permissions(operator,
                                         self.const.auth_create_user,
                                         self.const.auth_target_type_disk,
                                         None, None) or
            self._query_ou_permissions(operator,
                                     self.const.auth_create_user,
                                     ou, affiliation, None)):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to create persons")

    def can_set_person_id(self, operator, person=None, idtype=None,
                          query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        if person.get_external_id(id_type=idtype):
            raise PermissionDenied("Already has a value for that idtype")
        account = Factory.get('Account')(self._db)
        account.find(operator)
        if person.entity_id == account.owner_id:
            return True
        return self.is_account_owner(operator, self.const.auth_create_user,
                                     account)

    def can_alter_printerquota(self, operator, account=None,
                               query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_alter_printerquota)
        return self.is_account_owner(operator,
                                     self.const.auth_alter_printerquota,
                                     account)
    
    def can_query_printerquota(self, operator, account=None,
                              query_run_any=False):
        if self.is_superuser(operator):
            return True
        return True                     # Anyone can query quota

    def can_disable_quarantine(self, operator, entity=None,
                               qtype=None, query_run_any=False):
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_quarantine_disable)
        if str(qtype) in getattr(cereconf, 'QUARANTINE_STRICTLY_AUTOMATIC', ()):
            raise PermissionDenied('Not allowed to modify automatic quarantine')
        if self.is_superuser(operator):
            return True

        # Special rule for guestusers. Only superuser are allowed to
        # alter quarantines for these users.
        if self._entity_is_guestuser(entity):
            raise PermissionDenied("No access")            
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        return self.is_account_owner(
            operator, self.const.auth_quarantine_disable, entity)

    def can_remove_quarantine(self, operator, entity=None, qtype=None,
                              query_run_any=False):
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_quarantine_remove)
        if str(qtype) in getattr(cereconf, 'QUARANTINE_STRICTLY_AUTOMATIC', ()):
            raise PermissionDenied('Not allowed to modify automatic quarantine')
        # TBD: should superusers be allowed to remove automatic quarantines?
        if self.is_superuser(operator):
            return True
        if str(qtype) in getattr(cereconf, 'QUARANTINE_AUTOMATIC', ()):
            raise PermissionDenied('Not allowed to modify automatic quarantine')

        # Special rule for guestusers. Only superuser are allowed to
        # alter quarantines for these users.
        if self._entity_is_guestuser(entity):
            raise PermissionDenied("No access")            
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        # this is a hack
        else:
            if self._no_account_home(operator, entity):
                return True
        return self.is_account_owner(
            operator, self.const.auth_quarantine_remove, entity)

    def can_set_quarantine(self, operator, entity=None, qtype=None,
                           query_run_any=False):
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_quarantine_set)
        if str(qtype) in getattr(cereconf, 'QUARANTINE_STRICTLY_AUTOMATIC', ()):
            raise PermissionDenied('Not allowed to set automatic quarantine')
        if self.is_superuser(operator):
            return True
        if str(qtype) in getattr(cereconf, 'QUARANTINE_AUTOMATIC', ()):
            raise PermissionDenied('Not allowed to set automatic quarantine')

        # TODO 2003-07-04: Bård is going to comment this
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        else:
            if self._no_account_home(operator, entity):
                return True
        return self.is_account_owner(operator, self.const.auth_quarantine_set,
                                     entity)

    def can_show_quarantines(self, operator, entity=None,
                             query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_set_password)
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        # this is a hack
        else:
            if self._no_account_home(operator, entity):
                return True       
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     entity)

    def can_create_disk(self, operator, host=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator,
                                                      self.const.auth_add_disk)
        if host is not None:
            host = int(host.entity_id)
        if self._has_target_permissions(operator, self.const.auth_add_disk,
                                        self.const.auth_target_type_host,
                                        host, None):
            return True
        raise PermissionDenied("No access to host")

    def can_remove_disk(self, operator, host=None, query_run_any=False):
        return self.can_create_disk(operator, host=host,
                                    query_run_any=query_run_any)

    def can_create_host(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        # auth_create_host is not tied to a target
        if self._has_operation_perm_somewhere(
            operator, self.const.auth_create_host):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_remove_host(self, operator, query_run_any=False):
        return self.can_create_host(operator, query_run_any=query_run_any)

    def can_alter_group(self, operator, group=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_alter_group_membership)
        if self._has_target_permissions(operator,
                                        self.const.auth_alter_group_membership,
                                        self.const.auth_target_type_group,
                                        group.entity_id, group.entity_id):
            return True

        raise PermissionDenied("%s has no access to group %s" %
                               (self._get_uname(operator),
                                group is None and "N/A" or
                                self._get_gname(group.entity_id)))
    # end can_alter_group


    def can_add_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_remove_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_show_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(operator, self.const.auth_set_password):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")


    def list_alterable_entities(self, operator, target_type):
        """Find all entities of L{target_type} that can be
        moderated/administered by L{operator}.

        'Moderated' in this context is equivalent with auth_operation_set
        defined in cereconf: BOFHD_AUTH_GROUPMODERATOR.

        @param operator:
          The account on behalf of which the query is to be executed.

        @type target_type: basestring (yes, a basestring).
        @param target_type:
          The kind of entities for which permissions are checked. The only
          permissible values are 'group', 'disk', 'host' and 'maildom'.
        """

        legal_target_types = ('group', 'disk', 'host', 'maildom')

        if target_type not in legal_target_types:
            raise ValueError("Illegal target_type <%s>" % target_type)

        operator_id = int(operator)
        opset = BofhdAuthOpSet(self._db)
        opset.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)
                    #bofhd_auth_groupmoderator

        sql = """
        SELECT aot.entity_id
        FROM [:table schema=cerebrum name=auth_op_target] aot,
             [:table schema=cerebrum name=auth_role] ar
        WHERE (ar.entity_id = :operator_id OR
               -- do NOT replace with EXISTS, it's much more expensive
               ar.entity_id IN (SELECT gm.group_id
                                FROM [:table schema=cerebrum name=group_member] gm
                                WHERE gm.member_id = :operator_id)) AND
              ar.op_target_id = aot.op_target_id AND
              aot.target_type = :target_type AND
              ar.op_set_id = :op_set_id
        """

        return self.query(sql, {"operator_id": operator_id,
                                "target_type": target_type,
                                "op_set_id": opset.op_set_id})
    # end list_alterable_entities
    

    def can_create_group(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        # auth_create_group is not tied to a target
        if self._has_operation_perm_somewhere(
            operator, self.const.auth_create_group):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_create_personal_group(self, operator, account=None,
                                  query_run_any=False):
        if query_run_any or self.is_superuser(operator):
            return True
        if operator == account.entity_id:
            return True
        return self.is_account_owner(operator, self.const.auth_create_user,
                                     account)

    def can_delete_group(self, operator, group=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")
    
    def can_search_group(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        # auth_search_group is not tied to a target
        if self._has_operation_perm_somewhere(operator,
                                              self.const.auth_search_group):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_add_spread(self, operator, entity=None, spread=None,
                       query_run_any=False):
        """Each spread that an operator may modify is stored in
        auth_op_attrs as the code_str value."""
        if spread is not None:
            spread = str(self.const.Spread(spread))

        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_modify_spread)
        if entity.entity_type == self.const.entity_group:
            self.is_group_owner(operator, self.const.auth_modify_spread,
                                entity, spread)
        else:
            self.is_account_owner(operator, self.const.auth_modify_spread,
                                  entity, operation_attr=spread)
        return True

    def can_remove_spread(self, operator, entity=None, spread=None,
                          query_run_any=False):
        return self.can_add_spread(operator, entity, spread,
                                   query_run_any=query_run_any)
    
    def can_add_account_type(self, operator, account=None, ou=None, aff=None,
                             aff_status=None, query_run_any=False):
        """If operator is same person as account, allow him to add any
        of the person's existing affiliation, but only allow him to
        remove an affiliation if at least one other account still has
        it.

        If the operator has create_user access to the account's disk,
        as above, but also allow the last affiliation to be removed."""

        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        op_acc = Factory.get("Account")(self._db)
        op_acc.find(operator)
        myself = False
        if (op_acc.owner_id == account.owner_id and
            op_acc.owner_type == account.owner_type):
            myself = True
        else:
            self.can_set_password(operator, account=account)

        if account.owner_type != self.const.entity_person:
            raise PermissionDenied, \
                  "Can't manipulate account not owned by a person"

        others = False
        exists = False
        for r in account.get_account_types(all_persons_types=True):
            if r['ou_id'] == ou.entity_id and r['affiliation'] == aff:
                if r['account_id'] == account.entity_id:
                    exists = True
                else:
                    others = True

        # aff_status is only None when removing account_type.
        removing = aff_status is None
        if not exists and removing:
            raise PermissionDenied, "No such affiliation"
        if myself and removing:
            if others:
                return True
            raise PermissionDenied, \
                  "Can't remove affiliation from last account"

        person = Person.Person(self._db)
        person.find(account.owner_id)
        for tmp_aff in person.get_affiliations():
            if (tmp_aff['ou_id'] == ou.entity_id and
                tmp_aff['affiliation'] == aff and
                (aff_status is None or tmp_aff['status'] == aff_status)):
                return True
        # The person lacks the affiliation we try to add/remove.
        # We applaud removing such affiliations.
        if removing:
            return True
        raise PermissionDenied("No access")

    def can_remove_account_type(self, operator, account=None, ou=None,
                                aff=None, query_run_any=False):
        return self.can_add_account_type(operator, account=account, ou=ou,
                                         aff=aff, query_run_any=query_run_any)
    
    def can_add_affiliation(self, operator, person=None, ou=None, aff=None,
                            aff_status=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        # TODO (at a later time): Determine how 'auth_add_affiliation' and
        # 'auth_remove_affiliation' should be connected to ou etc.
        if query_run_any:
            if self._has_operation_perm_somewhere(operator,
                                                  self.const.auth_add_affiliation):
                return True
            return False
        if self._has_target_permissions(operator,
                                        self.const.auth_add_affiliation,
                                        self.const.auth_target_type_ou,
                                        person.entity_id, person.entity_id,
                                        aff):
            return True
        raise PermissionDenied("No access for that person affiliation combination")

    def can_remove_affiliation(self, operator, person=None, ou=None,
                               aff=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            if self._has_operation_perm_somewhere(operator,
                                                  self.const.auth_remove_affiliation):
                return True
            return False
        if self._has_target_permissions(operator, self.const.auth_remove_affiliation,
                                        self.const.auth_target_type_ou,
                                        person.entity_id, person.entity_id,
                                        aff):
            return True
        raise PermissionDenied("No access for that person affiliation combination")

    def can_create_user(self, operator, person=None, disk=None,
                        query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator,
                                                      self.const.auth_create_user)
        if disk:
            return self._query_disk_permissions(operator,
                                                self.const.auth_create_user,
                                                self._get_disk(disk),
                                                None)
        if person:
            return self.is_account_owner(operator, self.const.auth_create_user,
                                         person)
        raise PermissionDenied, "No access"

    def can_delete_user(self, operator, account=None,
                        query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_remove_user)
        return self.is_account_owner(operator, self.const.auth_remove_user,
                                     account)

    def can_set_default_group(self, operator, account=None,
                              group=None, query_run_any=False):
        if query_run_any or self.is_superuser(operator):
            return True
        if account.account_name == group.group_name:
            return True # personal group: TODO need better detection
        self.can_alter_group(operator, group)
        self.can_give_user(operator, account)
        return True
        
    def can_set_gecos(self, operator, account=None,
                      query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return (self._has_operation_perm_somewhere(operator,
                                                  self.const.auth_set_gecos) or
                    self._has_operation_perm_somewhere(operator,
                                                  self.const.auth_create_user))
        if self._is_owner_of_nonpersonal_account(operator, account):
            return True
        return self.is_account_owner(operator, self.const.auth_set_gecos,
                                     account)

    def can_move_user(self, operator, account=None, dest_disk=None,
                      query_run_any=False):
        if self.is_superuser(operator):
            return True
        return (self.can_give_user(operator, account,
                                   query_run_any=query_run_any)
                and
                self.can_receive_user(operator, account, dest_disk,
                                      query_run_any=query_run_any))

    def can_give_user(self, operator, account=None,
                      query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_move_from_disk)
        return self.is_account_owner(operator, self.const.auth_move_from_disk,
                                     account)

    def can_receive_user(self, operator, account=None, dest_disk=None,
                         query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_move_to_disk)
        return self._query_disk_permissions(operator,
                                            self.const.auth_move_to_disk,
                                            self._get_disk(dest_disk),
                                            account.entity_id)

    # hack (fix for users with no registered home at UiO)
    def _no_account_home(self, operator, account=None):
        try:
            aff_stud = int(self.const.affiliation_student)
        except AttributeError, e:
            return False
        if not self.is_studit(operator):
            return False
        for r in account.get_account_types():
            if r['affiliation'] == aff_stud:
                break
        else:
            return False
        spreads = [int(r['spread']) for r in account.get_spread()]
        for s in ([int(getattr(self.const, x)) for x in cereconf.HOME_SPREADS]):
            if s in spreads:
                return False
        return True
    # end hack

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
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     account)

    def can_set_shell(self, operator, account=None, shell=None,
                      query_run_any=False):
        if query_run_any:
            return True
        # TBD: auth_op_attrs may contain legal shells
        if self.is_superuser(operator):
            return True
        # A bit of a hack: Restrict the kinds of shells a normal user
        # can select based on the pathname of the shell.  He can still
        # choose "sync" ("/bin/sync"), though.
        # TODO: add a Boolean to _PosixShellCode() signifying whether
        # it should be user selectable or not.
        if (operator == account.entity_id and shell and
            shell.description.find("/bin/") <> -1):
            return True
        # TODO 2003-07-04: Bård is going to comment this
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     account)

    def can_show_history(self, operator, entity=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator,
                    self.const.auth_view_history)
        if entity.entity_type == self.const.entity_account:
            if self._no_account_home(operator, entity):
                return True
            return self.is_account_owner(operator, self.const.auth_view_history,
                                         entity)
        elif entity.entity_type == self.const.entity_group:
            return self.is_group_owner(operator, self.const.auth_view_history,
                                       entity)
        raise PermissionDenied("no access for that entity_type")

    def can_cancel_request(self, operator, req_id, query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        req_operator = None
        br = BofhdRequests(self._db, self.const)
        for r in br.get_requests(request_id=req_id):
            if r['requestee_id'] and int(r['requestee_id']) == operator:
                return True
        raise PermissionDenied("You are not requester")

    def can_grant_access(self, operator, operation=None, target_type=None,
                         target_id=None, opset=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            for op in (self.const.auth_grant_disk,
                       self.const.auth_grant_group,
                       self.const.auth_grant_host,
                       self.const.auth_grant_maildomain,
                       self.const.auth_grant_dns,
                       self.const.auth_grant_ou):
                if self._has_operation_perm_somewhere(operator, op):
                    return True
            return False
        if opset is not None:
            opset = opset.name
        if self._has_target_permissions(operator, operation,
                                        target_type, target_id,
                                        None, operation_attr=opset):
            return True
        raise PermissionDenied("No access to %s" % target_type)

    def can_request_guests(self, operator, groupname=None, query_run_any=False):
        if self.is_superuser(operator): 
            return True
        if not self._has_operation_perm_somewhere(operator,
                                                  self.const.auth_guest_request):
            return False
        if query_run_any:
            return True
        if self.is_group_member(operator, groupname):
            return True
        raise PermissionDenied("Can't request guest accounts")

    def can_release_guests(self, operator, groupname=None, query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        if self.is_group_member(operator, groupname):
            return True
        raise PermissionDenied("Can't release guest account")

    def can_create_guests(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Can't create guest accounts")

    # Guest users
    # The new guest user regime, where the guests can be created by end users
    # and not the IT staff.
    def can_create_personal_guest(self, operator, query_run_any=False):
        """Can the operator create a personl guest user?"""
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        # check person affiliations
        ac = Factory.get('Account')(self._db)
        ac.find(operator)
        if ac.owner_type == self.const.entity_person:
            pe = Factory.get('Person')(self._db)
            for row in pe.list_affiliations(person_id=ac.owner_id,
                                affiliation=self.const.affiliation_ansatt):
                return True
        raise PermissionDenied(
                "Guest accounts can only be created by employees")

    #
    # TODO: the can_email_xxx functions do not belong in core Cerebrum

    # everyone can see basic information
    def can_email_info(self, operator, account=None, query_run_any=False):
        return True

    # detailed information about tripnotes etc. is available to
    # the user's local sysadmin and helpdesk operators.
    def can_email_info_detail(self, operator, account=None,
                              query_run_any=False):
        if query_run_any or account and operator == account.entity_id:
            return True
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_info_detail,
                                     account, None, query_run_any):
            return True
        raise PermissionDenied("Currently limited to postmasters")


    # the user, local sysadmin, and helpdesk can ask for migration
    def can_email_migrate(self, operator, account=None, query_run_any=False):
        if query_run_any or account and operator == account.entity_id:
            return True
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_migrate,
                                     account, None, query_run_any):
            return True
        raise PermissionDenied("Currently limited to postmasters")

    # not even the user is allowed this operation
    def can_email_move(self, operator, account=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_set_quota(self, operator, account=None, query_run_any=False):
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_quota_set,
                                     account, None, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")
    
    # not even the user is allowed this operation
    def can_email_pause(self, operator, account=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    # the user and local sysadmin is allowed to turn forwarding and
    # tripnote on/off
    def can_email_forward_toggle(self, operator, account=None,
                                 query_run_any=False):
        if query_run_any or account and operator == account.entity_id:
            return True
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_forward_off,
                                     account, None, query_run_any):
            return True
        raise PermissionDenied("Currently limited to superusers")

    def can_email_spam_settings(self, operator, account=None, target=None,
                                query_run_any=False):
        if query_run_any or account:
            return self.can_email_forward_toggle(operator, account,
                                                 query_run_any)
        # typically Mailman lists
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        raise PermissionDenied("Currently limited to superusers")

    def can_email_tripnote_toggle(self, operator, account=None,
                                  query_run_any=False):
        if query_run_any or account and operator == account.entity_id:
            return True
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_vacation_off,
                                     account, None, query_run_any):
            return True
        raise PermissionDenied("Currently limited to superusers")

    # only the user may add or remove forward addresses.
    def can_email_forward_edit(self, operator, account=None, domain=None,
                                query_run_any=False):
        if query_run_any:
            return True
        if account and operator == account.entity_id:
            return True
        # TODO: make a separate authentication operation for this!
        if self._is_local_postmaster(operator,
                                     self.const.auth_email_forward_off,
                                     account, domain, query_run_any):
            return True
        raise PermissionDenied("Currently limited to superusers")

    # or edit the tripnote messages or add new ones.
    def can_email_tripnote_edit(self, operator, account=None,
                                query_run_any=False):
        return self.can_email_forward_edit(operator, account,
                                           query_run_any=query_run_any)

    # TODO: when Mailman is better integrated with Cerebrum, we can
    # allow local postmasters to create lists, but today creating a
    # list requires shell access to mailman@lister.uio.no, so there's
    # no point.
    def can_email_list_create(self, operator, domain=None,
                              query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_list_delete(self, operator, domain=None,
                              query_run_any=False):
        return self.can_email_list_create(operator, domain, query_run_any)

    def can_email_archive_create(self, operator, domain=None,
                                 query_run_any=False):
        return self.can_email_list_create(operator, domain, query_run_any)

    def can_email_archive_delete(self, operator, domain=None,
                                 query_run_any=False):
        return self.can_email_archive_create(operator, domain, query_run_any)

    def can_email_pipe_create(self, operator, domain=None,
                                 query_run_any=False):
        return self.can_email_list_create(operator, domain, query_run_any)

    def can_email_pipe_edit(self, operator, domain=None,
                                 query_run_any=False):
        return self.can_email_pipe_create(operator, domain, query_run_any)

    def can_email_set_failure(self, operator, account=None,
                              query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_domain_create(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")
        
    def can_email_list_create(self, operator, domain=None,
                              query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    # create/delete e-mail targets of type "multi"
    def can_email_multi_create(self, operator, domain=None, group=None,
                               query_run_any=False):
        # not sure if we'll ever look at the group
        if self._is_local_postmaster(operator, self.const.auth_email_create,
                                     None, domain, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to postmasters")

    def can_email_multi_delete(self, operator, domain=None, group=None,
                               query_run_any=False):
        if self._is_local_postmaster(operator, self.const.auth_email_delete,
                                     None, domain, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    # create/delete e-mail targets of type "forward"
    def can_email_forward_create(self, operator, domain=None,
                                 query_run_any=False):
        if self._is_local_postmaster(operator, self.const.auth_email_create,
                                     None, domain, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    # associate a new e-mail address with an account, or other target.
    def can_email_address_add(self, operator, account=None, domain=None,
                              query_run_any=False):
        if self._is_local_postmaster(operator, self.const.auth_email_create,
                                     account, domain, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_address_delete(self, operator, account=None, domain=None,
                                 query_run_any=False):
        # TBD: should the full email address be added to the parameters, instead
        #      of just its domain?
        if self._is_local_postmaster(operator, self.const.auth_email_delete,
                                     account, domain, query_run_any):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_email_address_reassign(self, operator, account=None, domain=None,
                                   query_run_any=False):
        if query_run_any:
            return True
        # Allow a user to manipulate his own accounts
        if account:
            owner_acc = Factory.get("Account")(self._db)
            owner_acc.find(operator)
            if (owner_acc.owner_id == account.owner_id and
                owner_acc.owner_type == account.owner_type):
                return True
        if self._is_local_postmaster(operator,
                                         self.const.auth_email_reassign,
                                         account, domain, query_run_any):
            return True
        raise PermissionDenied("Currently limited to superusers")

    def can_email_mod_name(self, operator_id, person=None, firstname=None,
                           lastname=None, query_run_any=False):
        """If someone is allowed to modify a person's name. Only postmasters are
        allowed to do this by default."""
        if not self.is_postmaster(operator_id, query_run_any=query_run_any):
            raise PermissionDenied("Currently limited to superusers")

    def _is_local_postmaster(self, operator, operation, account=None,
                             domain=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self.is_postmaster(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator, operation)
        if domain:
            self._query_maildomain_permissions(operator, operation,
                                               domain, None)
        if account:
            self.is_account_owner(operator, operation, account)
        return True

    def _is_owner_of_nonpersonal_account(self, operator, account):
        """Return True if account is non-personal and operator is a
        member of the group owning the account."""
        if (account.np_type is None or
            account.owner_type != self.const.entity_group):
            return False
        owner_group = Factory.get("Group")(self._db)
        owner_group.find(account.owner_id)
        # TODO: check groups recursively (should be done by Group API)
        return owner_group.has_member(operator)

    def _query_disk_permissions(self, operator, operation, disk, victim_id,
                                operation_attr=None):
        """Permissions on disks may either be granted to a specific
        disk, a complete host, or a set of disks matching a regexp"""
                
        if self._has_target_permissions(operator, operation,
                                        self.const.auth_target_type_disk,
                                        disk.entity_id, victim_id,
                                        operation_attr=operation_attr):
            return True
        if self._has_global_access(operator, operation,
                                   self.const.auth_target_type_global_host,
                                   victim_id, operation_attr=operation_attr):
            return True
        # Check regexp on host targets
        for r in self._list_target_permissions(operator, operation,
                                               self.const.auth_target_type_host,
                                               disk.host_id,
                                               operation_attr=operation_attr):
            if not r['attr']:
                return True
            m = re.compile(r['attr']).match(disk.path.split("/")[-1])
            if m != None:
                return True
        raise PermissionDenied("No access to disk checking for '%s'" % operation)

    def _query_maildomain_permissions(self, operator, operation, domain,
                                      victim_id):
        """Permissions on e-mail domains are granted specifically."""
        if self._has_global_access(operator, operation,
                                   self.const.auth_target_type_global_maildomain,
                                   victim_id):
            return True
        if self._has_target_permissions(operator, operation,
                                        self.const.auth_target_type_maildomain,
                                        domain.entity_id, victim_id):
            return True
        raise PermissionDenied("No access to '%s' for e-mail domain %s" %
                               (operation.description,
                                domain.email_domain_name))

    def _query_ou_permissions(self, operator, operation, ou, affiliation,
                              victim_id):
        """Permissions on OUs are granted specifically."""
        ou_id = None
        if ou:
            ou_id = ou.entity_id
        for r in self._list_target_permissions(operator, operation,
                                               self.const.auth_target_type_ou,
                                               ou_id):
            # We got at least one hit.  If we don't match a specific
            # affiliation, just return.
            if not affiliation or not r['attr']:
                return True
            if r['attr'] and str(affiliation) == r['attr']:
                return True
        return False

    def _has_operation_perm_somewhere(self, operator, operation):
        # This is called numerous times when using "help", so we use a cache
        key = "%i:%i" % (operator, operation)
        try:
            return self._any_perm_cache[key]
        except KeyError:
            sql = """
            SELECT 'foo' AS foo
            FROM [:table schema=cerebrum name=auth_operation] ao,
                 [:table schema=cerebrum name=auth_operation_set] aos,
                 [:table schema=cerebrum name=auth_role] ar
            WHERE     
               ao.op_code=:operation AND
               ao.op_set_id=aos.op_set_id AND
               aos.op_set_id=ar.op_set_id AND
               ar.entity_id IN (%s)""" % (", ".join(
                ["%i" % x for x in self._get_users_auth_entities(operator)]))
            r = self.query(sql, {'operation': int(operation) })
            if r:
                self._any_perm_cache[key] = True
            else:
                self._any_perm_cache[key] = False
        return self._any_perm_cache[key] 

    def _query_target_permissions(self, operator, operation, target_type,
                                  target_id, victim_id, operation_attr=None):
        logger = Factory.get_logger()
        logger.warn("Deprecated function _query_target_permissions. " +
                    "Use _has_target_permissions or _list_target_permissions.")
        return self._has_target_permissions(
            operator, operation, target_type, target_id, victim_id,
            operation_attr)
    

    def _has_target_permissions(self, operator, operation, target_type,
                                  target_id, victim_id, operation_attr=None):
        """Query any permissions that operator, or any of the groups where
        operator is a member, has been granted operation on
        target_type:target_id, or the global equivalent of the target.

        This function returns True or False.
        """
        if target_id is not None:
            if target_type in (self.const.auth_target_type_host,
                               self.const.auth_target_type_disk):
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_host,
                                           victim_id, operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_group:
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_group,
                                           victim_id, operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_maildomain:
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_maildomain,
                                           victim_id, operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_ou:
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_ou,
                                           victim_id, operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_dns:
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_dns,
                                           victim_id, operation_attr=operation_attr):
                    return True

        if self._list_target_permissions(
            operator, operation, target_type, target_id,  operation_attr):
            return True
        else:
            return False

    def _list_target_permissions(self, operator, operation, target_type,
                                 target_id,  operation_attr=None):
        """List permissions that operator, or any of the groups where operator
        is a member, has for the operation on the direct target. This could be
        used instead of L{_has_target_permissions} if you would like to accept
        more than one exact operation_attr.
        
        The result of this function is a sequence of dbrows which can be checked
        for dbrow['attr']. The keys are 'attr', 'op_id' and 'op_target_id'.
        """
        ewhere = ""
        if target_id is not None:
            ewhere = "AND aot.entity_id=:target_id"
        # Connect auth_operation and auth_op_target
        # Relevant entries in auth_operation are:
        # 
        # - all with correct op_code that either:
        #   o  has no entries in auth_op_attrs
        #   o  or has correct entry in auth_op_attrs

        sql = """
        SELECT aot.attr, ao.op_id, aot.op_target_id
        FROM [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_operation_set] aos,
             [:table schema=cerebrum name=auth_role] ar,
             [:table schema=cerebrum name=auth_op_target] aot
        WHERE
           ao.op_code=:opcode AND
           ((EXISTS (
              SELECT 'foo'
              FROM [:table schema=cerebrum name=auth_op_attrs] aoa
              WHERE ao.op_id=aoa.op_id AND aoa.attr=:operation_attr)) OR
            NOT EXISTS (
              SELECT 'foo'
              FROM [:table schema=cerebrum name=auth_op_attrs] aoa
              WHERE ao.op_id=aoa.op_id)) AND
           ao.op_set_id=aos.op_set_id AND
           aos.op_set_id=ar.op_set_id AND
           ar.entity_id IN (%s) AND
           ar.op_target_id=aot.op_target_id AND
           aot.target_type=:target_type %s
          """ % (", ".join(
            ["%i" % x for x in self._get_users_auth_entities(operator)]),
                 ewhere)
        return self.query(sql,
                          {'opcode': int(operation),
                           'target_type': target_type,
                           'target_id': target_id,
                           'operation_attr': operation_attr})

    def _has_access_to_entity_via_ou(self, operator, operation, entity,
                                     operation_attr=None):
        """entity may be an instance of Person or Account.  Returns
        True if the operator has access to any of the OU's associated
        with the entity, or False otherwise.  If an auth_op_target
        has an attribute, the attribute value is compared to the
        string representation of the affiliations the entity is a
        member of."""
        # make a list of the groups the operator is a (direct) member of.
        operator_groups = ["%i" % x
                           for x in self._get_users_auth_entities(operator)]
        if isinstance(entity, Factory.get('Account')):
            table_name = "account_type"
            id_colname = "account_id"
        else:
            table_name = "person_affiliation"
            id_colname = "person_id"

        # TODO: operation_attr
        sql = """
        SELECT at.affiliation, aot.attr, ao.op_id, aot.op_target_id
        FROM [:table schema=cerebrum name=%(table_name)s] at,
             [:table schema=cerebrum name=auth_op_target] aot,
             [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_operation_set] aos,
             [:table schema=cerebrum name=auth_role] ar
        WHERE at.%(id_colname)s=:id AND
              aot.op_target_id=ar.op_target_id AND
              ((aot.target_type=:target_type AND
                at.ou_id=aot.entity_id ) OR
               aot.target_type=:global_target_type) AND
              ar.entity_id IN (%(group_list)s) AND
              aos.op_set_id=ar.op_set_id AND
              ao.op_set_id=aos.op_set_id AND
              ao.op_code=:opcode AND
              ((EXISTS (
                 SELECT 'foo'
                 FROM [:table schema=cerebrum name=auth_op_attrs] aoa
                 WHERE ao.op_id=aoa.op_id AND aoa.attr=:operation_attr)) OR
               NOT EXISTS (
                 SELECT 'foo'
                 FROM [:table schema=cerebrum name=auth_op_attrs] aoa
                 WHERE ao.op_id=aoa.op_id))
              """ % {'group_list': ", ".join(operator_groups),
                     'table_name': table_name,
                     'id_colname': id_colname}

        for r in self.query(sql,
                            {'opcode': int(operation),
                             'target_type':
                                     self.const.auth_target_type_ou,
                             'global_target_type':
                                     self.const.auth_target_type_global_ou,
                             'id': entity.entity_id,
                             'operation_attr': operation_attr}):
            if not r['attr']:
                return True
            else:
                aff = str(self.const.PersonAffiliation(r['affiliation']))
                if aff == r['attr']:
                    return True
        return False

    def _has_global_access(self, operator, operation, global_type, victim_id,
                           operation_attr=None):
        """Check if operator has permission to the given operation globally for
        the given global_type.
        
        Note that global_host and global_group should not be allowed to operate
        on BOFHD_SUPERUSER_GROUP.
        """
        if global_type == self.const.auth_target_type_global_group:
            if victim_id == self._superuser_group:
                return False
        elif victim_id in \
                 self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP):
            return False
        for k in self._list_target_permissions(operator, operation,
                                               global_type, None,
                                               operation_attr=operation_attr):
            return True
        return False

    def _get_users_auth_entities(self, entity_id):
        """Return all entity_ids that may be relevant in auth_role for
        this user"""
        entity_id = int(entity_id)
        try:
            return self._users_auth_entities_cache[entity_id]
        except KeyError:
            pass
        group = Factory.get('Group')(self._db)
        ret = [entity_id]
        # Grab all groups where entity_id is a direct member
        ret.extend([int(x["group_id"])
                    for x in group.search(member_id=entity_id,
                                          indirect_members=False)])
        self._users_auth_entities_cache[entity_id] = list(set(ret))
        return ret

    def _get_group_members(self, groupname):
        try:
            return self._group_member_cache[groupname]
        except KeyError:
            pass
        group = Factory.get('Group')(self._db)
        group.find_by_name(groupname)
        members = [int(row["member_id"]) for row in
                   group.search_members(group_id=group.entity_id,
                                        indirect_members=True,
                                        member_type=self.const.entity_account)]
        self._group_member_cache[groupname] = list(set(members))
        return members

    def _get_user_disk(self, account_id):
        if not getattr(cereconf, 'BOFHD_CHECK_DISK_SPREAD', None):
            return None
        try:
            account = Factory.get('Account')(self._db)
            account.find(account_id)
            spread = self.const.Spread(cereconf.BOFHD_CHECK_DISK_SPREAD)
            return account.get_home(int(spread))
        except Errors.NotFoundError:
            return None

    def _get_disk(self, disk_id):
        disk = Factory.get('Disk')(self._db)
        disk.find(disk_id)
        return disk

    def _entity_is_guestuser(self, entity):
        for trait in ('trait_guest_owner', 'trait_uio_guest_owner'):
            try:
                if entity.get_trait(getattr(self.const, trait)):
                    return True
            except AttributeError:
                pass
        return None

# end class BofhdAuth
