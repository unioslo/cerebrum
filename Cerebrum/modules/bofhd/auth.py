# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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
"""Module for access control in Cerebrum.

This module was mainly written for use with `bofhd`, given its name, but its
functionality is *independent* of `bofhd`. You could use this module for every
Cerebrum service that needs access control.

This authorization module is quite fine grained, making it a bit complex.

Summary
=======

How the access control works:

- When access control is needed for some functionality, you call a method from
  the `BofhdAuth` class, e.g. `BofhdAuth.can_set_trait`.

- The `BofhdAuth` then checks various things, like the operator's group
  memberships, to see if the account is part of a superuser group, or if any of
  the groups have some auth operations set to it.

Terminology
===========

- **authentication**: This module does not check the *operator*. We expect the
  account to have been fully authenticated before this module is reached.

- **operator**: The entity that has requested access to some operation or
  function. This is normally an account.

- **operation**: A single operation, for some specific task, e.g. to create a
  group, to expire an account og to see personal information. Operations does
  ideally, and normally, only refer to *one single action*.

  Operations are registered in the database, and should not be confused with
  the access methods on `BofhdAuth`. The methods here checks the operations
  from db, but they also include more checks, and often add some hardcoded
  checks. The superuser access control is for instance hardcoded, and that the
  operator is able to see its own personal data.

- **OpSet**: A collection of various operations, with their parameters. The
  *OpSet* makes it easier to give groups of people access to a set of various
  actions they need in their role. Local IT needs to do some specific tasks,
  while student-IT needs something else.

  OpSets are registered in the database, but they are normally set up and
  configured through a configuration file, `opset_config.py` from the
  configuration repo. See `contrib/permission_updates.py` for more info.

- **role**: In this module, roles are quite lightweight, and are only
  connecting an operator together with an OpSet and a target. When an operator
  gets a role, it is then allowed to do what the OpSet says, but only on the
  entities defined by the given target, e.g. only users on a given disk.

  Targets could also be *global*, which means that the role is valid
  everywhere, for all entities. As a security measure, superusers are excluded
  from global targets, so the operator is not allowed to modify superusers.

- **target**: In *this* module, we refer to *target* as to where a role is
  valid. An operator could have many roles and OpSets, but the target defines
  where, i.e. what entities, the operations could be performed on. The target
  defines a subset of entities to perform operations on.

  Examples on targets are:
  - All users on a given disk.
  - All entities with a given spread.
  - All users on a given host, but where the disk path is on the form
    `student-u.*`.

- **victim**: A specific entity that the operator wants to process a certain
  operation on.

Auth model
==========

How authorization is registered for the operator - see `design/bofhd_auth.sql`
for the database model.

- *Operations* are defined constants.

- *OpSets* are created and consists of references to various operations. Each
  operation could be configured with some parameters. For example the operation
  to add a spread includes a parameter where you could define *what* spread is
  allowed.

- *Operators* are then authorized, i.e. *granted* access, to OpSets. Note that
  the OpSet is limited to targets, for instance all entities on a given
  disk/host, a given affiliation/OU, by a spread, or even globally.

  This makes it possible to give one local IT department access to the accounts
  on *their* disks/OUs without another local IT department interfering.

  Normally the authorization is added per group, and not to operators directly.
  This is to ease later configuration, as its easier to updated group
  memberships than to modify the authorization lists.

- When checking an operator's access, the method in `BofhdAuth` checks its
  direct operations, its groups' operations, and also some hardcoded values,
  for example that the operator has access to see its own personal data.

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
  the group matnat-drift are authorized for the LocalIT operations, but only
  for the accounts and persons located at MatNat.

  Roles are manipulated by `access grant` and `access revoke` in bofhd. The
  entity that executes an access command needs to be authorized to execute it
  through a role.

  Note that roles given to groups means that every member of the group is
  authorized for the OpSet. Also note that superusers are not authorized
  through roles and OpSets, but instead the superuser group is given hardcoded
  access in the different auth commands. You would therefore not find any
  superuser role.

- Services that uses BofhdAuth would only see different auth methods, e.g.
  can_view_trait(). The operations and OpSets are then checked internally, the
  service does not need to know about these details.

  An example is the bofhd command 'user_history', which calls
  BofhdAuth.can_show_history(). The auth method will check if the operator has
  access to the user by the operation 'auth_view_history' (or 'view_history')
  through either an OU or a disk.

  Some operations have the need for *attributes*. An example of this is the
  operation 'modify_spread', where the attribute decide what kind of spread it
  should be allowed to modify. Note that the attributes could change between
  the OpSets.

  The different auth methods rely on some common methods for querying for the
  permissions. The methods start with '_query', in addition to methods like
  _list_target_permissions.

In the database
===============

The operations are Cerebrum constants, but is also put in the table
`auth_operation`.

- Operations are put in `auth_operation`. Some operations have certain
  attributes, which are put in `auth_op_attrs`.

- OpSets are put in `auth_operation_set`.

- Roles are put in `auth_role`, and their targets are put in `auth_op_target`.

Configuration
=============

BOFHD_AUTH_GROUPMODERATOR
    An opset that identifies group moderators. This is used to list out which
    groups a given user has access to moderate.
BOFHD_CHECK_DISK_SPREAD
    A spread to check for home directory. If set, then access to that disk will
    also give access to users on that disk (see
    `has_privileged_access_to_account_or_person`)
BOFHD_STUDADM_GROUP
    A group name, members are considered IT support staff for users *without* a
    home direcotry.
BOFHD_SUPERUSER_GROUP
    A group name, members are considered superusers (see `is_superuser`).
HOME_SPREADS
    Spreads that are used on home directories, users with one of these spreads
    are *not* affected by BOFHD_STUDADM_GROUP.
QUARANTINE_AUTOMATIC
    A list of quarantines that should not be altered manually (see
    `can_*_quarantine`)
QUARANTINE_STRICTLY_AUTOMATIC
    A list of quarantines that *cannot* be altered manually (see
    `can_*_quarantine`)

"""

import re

import six

import cereconf

from Cerebrum import Cache
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory, mark_update
from Cerebrum.Utils import argument_to_sql
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests


class AuthConstants(Constants._CerebrumCode):
    """Defines an operation constant.

    # TODO: this looks like a duplicate of utils._AuthRoleOpCode.  Cleanup!

    Operations are saying what an operator is allowed to do. The operations are
    handled inside the `BofhdAuth` class' methods.

    Note that operations are not connected to operators directly. The
    operations are put inside *operation sets* (OpSets), which again are linked
    to operation targets, and is then either connected to the operator
    directly, or is most likely connected through a regular group the operator
    is member of.
    """

    _lookup_table = '[:table schema=cerebrum name=auth_op_code]'


class BofhdAuthOpSet(DatabaseAccessor):
    """Operation Set (OpSet) management.

    Operations could be put into different groups (sets) of operations. These
    sets are here called *OpSets*. OpSets are making it easier to administrate
    the authorizations. For instance, a specific group or account could be
    delegated an OpSet 'LocalIT', which could be an operation set with all the
    different operations the staff at local IT would need in their work.

    This class contains methods for updating the tables `auth_operation_set`,
    `auth_operation` and `auth_op_attrs` which specifies what operations may be
    performed. OpSets are handled by BofhdAuthOpSet, and is stored in the table
    `auth_operation_set`, while the operations that belongs to an OpSet is
    referenced to in the table `auth_operation`. Operation attributes, e.g. for
    setting constraints for an operation, is put in `auth_op_attrs`.
    """

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
                raise RuntimeError("populate() called multiple times.")
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

    def del_operation(self, op_code, op_id=None):

        if op_id is not None:
            self.del_all_op_attrs(op_id)

        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_operation]
        WHERE op_code=%s AND op_set_id=%s""" % (int(op_code), self.op_set_id))

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

    def del_all_op_attrs(self, op_id):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_op_attrs]
        WHERE op_id=%s""" % int(op_id))

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
    """Management of the `auth_op_target` table.

    This identifies *operation targets*, which operations may be performed on.
    """

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

    def list(self, target_id=None, target_type=None, entity_id=None,
             attr=None):
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

    def count_invalid(self):
        """Return the count of invalid auth_roles in the database."""
        return self.query_1("""
            SELECT count(*)
            FROM [:table schema=cerebrum name=auth_op_target] ot
            WHERE NOT EXISTS (
                SELECT entity_id
                FROM [:table schema=cerebrum name=entity_info] ei
                WHERE ei.entity_id = ot.entity_id)
            AND ot.entity_id IS NOT NULL;
            """)

    def remove_invalid(self):
        """Remove all invalid auth_op_targets in the database.

        The database can contain references to deleted entities. The method
        cleans up the table by deleting any auth_op_targets with an invalid
        entity_id target.
        :return: None
        """
        self.execute("""
            DELETE FROM [:table schema=cerebrum name=auth_op_target] ot
            WHERE NOT EXISTS (
                SELECT entity_id
                FROM [:table schema=cerebrum name=entity_info] ei
                WHERE ei.entity_id = ot.entity_id)
            AND ot.entity_id IS NOT NULL""")


class BofhdAuthRole(DatabaseAccessor):
    """Role management, telling who has permission to what targets.

    The data about roles are stored in the `auth_role` table, containing
    information about who has certain permissions to certain targets.

    Roles are authorizations given to entities. The role gives an entity access
    to a given OpSet for either a given target, or globally. The entity could
    for instance be an account or a group (which gives all direct members of
    the group access), and the target could for instance be an OU, group or a
    disk.
    """

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

        entity_id may be a list of entities.
        """
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
        """Return info about who owns the given target_ids."""
        if not isinstance(target_ids, (list, tuple)):
            target_ids = [target_ids]
        if not target_ids:
            return ()
        return self.query("""
        SELECT DISTINCT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role]
        WHERE op_target_id IN (%s)""" % ", ".join(["%i" % i for i in
                                                   target_ids]))

    def count_invalid(self):
        """Return the count of invalid auth_roles in the database."""
        return self.query_1("""
        SELECT count(*) FROM [:table schema=cerebrum name=auth_role]
        WHERE op_target_id IN (
            SELECT op_target_id
            FROM [:table schema=cerebrum name=auth_op_target] ot
            WHERE NOT EXISTS (
                SELECT entity_id
                FROM [:table schema=cerebrum name=entity_info] ei
                WHERE ei.entity_id = ot.entity_id)
                AND ot.entity_id IS NOT NULL
        )""")

    def remove_invalid(self):
        """Remove all invalid auth_roles in the database.

        The database can contain references to deleted entities. The method
        cleans up the table by deleting any auth_op_targets with an invalid
        entity_id target.
        :return: None
        """
        self.execute("""
            DELETE FROM [:table schema=cerebrum name=auth_role]
            WHERE op_target_id IN (
                SELECT op_target_id
                FROM [:table schema=cerebrum name=auth_op_target] ot
                WHERE NOT EXISTS (
                    SELECT entity_id
                    FROM [:table schema=cerebrum name=entity_info] ei
                    WHERE ei.entity_id = ot.entity_id)
                AND ot.entity_id IS NOT NULL
            )""")


class BofhdAuth(DatabaseAccessor):
    """Defines methods that are used by bofhd to determine whether an operator
    is allowed to perform a given action.

    The `query_run_any` parameter used throughout in the methods is used to
    determine if operator has this permission *somewhere*. It is used to filter
    available commands in bofhds `get_commands()`, and if it is `True`, the
    method should return either `True` or `False`, and not raise
    `PermissionDenied`. Note that `query_run_any` should NOT be used a security
    measure, as you are still able to call the command if not in jbofh!
    """

    def __init__(self, database):
        super(BofhdAuth, self).__init__(database)
        self.const = Factory.get('Constants')(database)
        self._group_member_cache = Cache.Cache(
                            mixins=[Cache.cache_timeout], timeout=60)
        self._users_auth_entities_cache = Cache.Cache(
                            mixins=[Cache.cache_timeout], timeout=60)
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
        entity_id = int(entity_id)
        try:
            account = Factory.get("Account")(self._db)
            account.find(entity_id)
            return account.account_name
        except Errors.NotFoundError:
            return "id=" + str(entity_id)

    def _get_gname(self, entity_id):
        entity_id = int(entity_id)
        try:
            group = Factory.get("Group")(self._db)
            group.find(entity_id)
            return group.group_name
        except Errors.NotFoundError:
            return "id=" + str(entity_id)

    def is_superuser(self, operator_id, query_run_any=False):
        members = self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP)
        if operator_id in members:
            return True
        return False

    def is_schoolit(self, operator, query_run_any=False):
        if self.is_superuser(operator, query_run_any):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                                operator, self.const.auth_set_password)
        return False

    def is_postmaster(self, operator, query_run_any=False):
        # Rather than require an operation as an argument, we pick a
        # suitable value which all postmasters ought to have.
        # auth_email_create seems appropriate.
        if self.is_superuser(operator, query_run_any):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                                    operator, self.const.auth_email_create)
        return self._has_target_permissions(
            operator, self.const.auth_email_create,
            self.const.auth_target_type_global_maildomain, None, None)

    def is_studit(self, operator, query_run_any=False):
        if operator in self._get_group_members(cereconf.BOFHD_STUDADM_GROUP):
            return True
        return False

    def is_owner_of_account(self, operator, account):
        """See if operator is personal or non-personal owner of an account.

        :param int operator:
            The operator's `entity_id`.
        :param Cerebrum.Account account:
            The account to check is operator is owner of.
        """

        return (self._is_owner_of_personal_account(operator, account) or
                self._is_owner_of_nonpersonal_account(operator, account))

    def has_privileged_access_to_group(
            self, operator, operation, entity, operation_attr=None):
        """See if operator has access to a certain `operation` on a given group.

        :param int operator: The operator's `entity_id`.
        :param int operation: The operation constant's `intval`.
        :param Cerebrum.Entity entity:
            The victim's Entity object, here normally a *Group* object.
        :param str operation_attr:
            Limit the operation check to a specific operation attribute.
        :rtype: bool
        :returns:
            True if access is permitted. False is undetermined, as an exception
            is raised instead.
        :raise PermissionDenied:
            If the operator doesn't have access to the entity.
        """
        if self._has_target_permissions(operator, operation,
                                        self.const.auth_target_type_group,
                                        target_id=int(entity.entity_id),
                                        victim_id=None,
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

    def is_group_member(self, operator, groupname):
        if operator in self._get_group_members(groupname):
            return True
        return False

    def has_privileged_access_to_account_or_person(
            self, operator, operation, entity, operation_attr=None):
        """See if operator has access to an account or a person.

        Operation targets that are checked:

        #. Is operator allowed to perform operation on one of the **OUs**
           associated with Person or Account?
        #. If the entity is an *Account* and the account is owned by a group:
           Is the operator a member of the owner group? If so, the operator has
           _full_ access.
        #. Has operator (local or global) access to the account's disk?

        :param int operator: The operator's `entity_id`.
        :param int operation: The operation constant's `intval`.
        :param Cerebrum.Entity entity:
            The victim's Entity object, a *Person* or *Account* object.
        :param str operation_attr:
            Limit the operation check to a specific operation attribute.
        :rtype: bool
        :returns:
            True if access is permitted. False is undetermined, as an exception
            is raised instead.
        :raise PermissionDenied:
            If the operator doesn't have access to the entity.
        """
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
            return self._query_disk_permissions(
                        operator, operation, self._get_disk(disk['disk_id']),
                        entity.entity_id, operation_attr=operation_attr)
        else:
            if self._has_global_access(operator, operation,
                                       self.const.auth_target_type_global_host,
                                       entity.entity_id,
                                       operation_attr=operation_attr):
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
            self.has_privileged_access_to_account_or_person(
                operator, self.const.auth_disk_quota_forever, account)
        if unlimited:
            self.has_privileged_access_to_account_or_person(
                operator, self.const.auth_disk_quota_unlimited, account)
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_disk_quota_set, account)

    def can_set_disk_default_quota(self, operator, host=None, disk=None,
                                   query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_disk_def_quota_set)
        if ((host is not None and self._has_target_permissions(
                                operator, self.const.auth_disk_def_quota_set,
                                self.const.auth_target_type_host,
                                host.entity_id, None)) or
            (disk is not None and self._has_target_permissions(
                                operator, self.const.auth_disk_def_quota_set,
                                self.const.auth_target_type_disk,
                                disk.entity_id, None))):
            return True
        raise PermissionDenied("No access to disk")

    def can_show_disk_quota(self, operator, account=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_disk_quota_show)
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_disk_quota_show, account)

    def can_set_person_user_priority(self, operator, account=None,
                                     query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator) or operator == account.entity_id:
            return True
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_set_password, account)

    def can_set_trait(self, operator, trait=None, ety=None, target=None,
                      query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        if trait and self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_set_trait,
                target_type=self.const.auth_target_type_host,
                target_id=ety.entity_id,
                victim_id=ety.entity_id,
                operation_attr=six.text_type(trait)):
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
        if trait and self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_remove_trait,
                target_type=self.const.auth_target_type_host,
                target_id=ety.entity_id,
                victim_id=ety.entity_id,
                operation_attr=six.text_type(trait)):
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
        operation_attr = six.text_type(trait) if trait else None
        if self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_view_trait,
                target_type=self.const.auth_target_type_host,
                target_id=ety.entity_id,
                victim_id=target,
                operation_attr=operation_attr):
            return True
        raise PermissionDenied("Not allowed to see trait")

    def can_list_trait(self, operator, trait=None, query_run_any=False):
        """Access to list which entities has a trait."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_list_trait)
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_list_trait):
            return True
        raise PermissionDenied("Not allowed to list traits")

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
            self._query_ou_permissions(operator, self.const.auth_create_user,
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
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_create_user, account)

    def can_alter_printerquota(self, operator, account=None,
                               query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_alter_printerquota)
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_alter_printerquota, account)

    def can_query_printerquota(self, operator, account=None,
                               query_run_any=False):
        if self.is_superuser(operator):
            return True
        return True

    def can_disable_quarantine(self, operator, entity=None,
                               qtype=None, query_run_any=False):
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_quarantine_disable)
        if six.text_type(qtype) in cereconf.QUARANTINE_STRICTLY_AUTOMATIC:
            raise PermissionDenied('Not allowed, automatic quarantine')
        if self.is_superuser(operator):
            return True

        # Special rule for guestusers. Only superuser are allowed to
        # alter quarantines for these users.
        if self._entity_is_guestuser(entity):
            raise PermissionDenied("No access")
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")

        for row in self._list_target_permissions(
                operator, self.const.auth_quarantine_disable,
                self.const.auth_target_type_global_host,
                None, get_all_op_attrs=True):
            attr = row.get('operation_attr')
            # No operation attributes means that all quarantines are allowed
            # TODO: This can be removed when all opsets for all instances
            # has a populated qua_disable dict.
            if not attr:
                return True
            if six.text_type(qtype) == attr:
                return True

        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_quarantine_disable, entity,
            operation_attr=six.text_type(qtype))

    def can_remove_quarantine(self, operator, entity=None, qtype=None,
                              query_run_any=False):
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_quarantine_remove)
        if six.text_type(qtype) in cereconf.QUARANTINE_STRICTLY_AUTOMATIC:
            raise PermissionDenied('Not allowed, automatic quarantine')
        # TBD: should superusers be allowed to remove automatic quarantines?
        if self.is_superuser(operator):
            return True
        if six.text_type(qtype) in cereconf.QUARANTINE_AUTOMATIC:
            raise PermissionDenied('Not allowed, automatic quarantine')

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

        for row in self._list_target_permissions(
                operator, self.const.auth_quarantine_remove,
                self.const.auth_target_type_global_host,
                None, get_all_op_attrs=True):
            attr = row.get('operation_attr')
            # No operation attributes means that all quarantines are allowed
            # TODO: This can be removed when all opsets for all instances
            # has a populated qua_remove dict.
            if not attr:
                return True
            if six.text_type(qtype) == attr:
                return True

        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_quarantine_remove, entity,
            operation_attr=six.text_type(qtype))

    def can_set_quarantine(self, operator, entity=None, qtype=None,
                           query_run_any=False):
        if query_run_any:
            if self.is_superuser(operator):
                return True
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_quarantine_set)
        if six.text_type(qtype) in cereconf.QUARANTINE_STRICTLY_AUTOMATIC:
            raise PermissionDenied('Not allowed, automatic quarantine')
        if self.is_superuser(operator):
            return True
        if six.text_type(qtype) in cereconf.QUARANTINE_AUTOMATIC:
            raise PermissionDenied('Not allowed, automatic quarantine')
        for row in self._list_target_permissions(
                operator, self.const.auth_quarantine_set,
                self.const.auth_target_type_global_host,
                None, get_all_op_attrs=True):
            attr = row.get('operation_attr')
            # No operation attributes means that all quarantines are allowed
            # TODO: This can be removed when all opsets for all instances
            # has a populated qua_add dict.
            if not attr:
                return True
            if six.text_type(qtype) == attr:
                return True

        # TODO 2003-07-04: Bård is going to comment this
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        else:
            if self._no_account_home(operator, entity):
                return True
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_quarantine_set, entity,
            operation_attr=six.text_type(qtype))

    def can_show_quarantines(self, operator, entity=None,
                             query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        # this is a hack
        if self._no_account_home(operator, entity):
            return True
        if self.is_owner_of_account(operator, entity):
            return True
        return self.has_privileged_access_to_account_or_person(
                    operator, self.const.auth_set_password, entity)

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
        if self._has_operation_perm_somewhere(operator,
                                              self.const.auth_create_host):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_remove_host(self, operator, query_run_any=False):
        return self.can_create_host(operator, query_run_any=query_run_any)

    def can_alter_group(self, operator, group=None, query_run_any=False):
        """Checks if the operator has permission to add/remove group members
        for the given group.

        @type operator: int
        @param operator: The entity_id of the user performing the operation.

        @type group: An entity of EntityType Group
        @param group: The group to add/remove members to/from.

        @type query_run_any: True or False
        @param query_run_any: Check if the operator has permission *somewhere*

        @return: True or False
        """
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

    def list_alterable_entities(self, operator, target_type):
        """Find entities of `target_type` that `operator` can moderate.

        'Moderate' in this context is equivalent with `auth_operation_set`
        defined in `cereconf.BOFHD_AUTH_GROUPMODERATOR`.

        :param int operator:
          The account on behalf of which the query is to be executed.

        :param str target_type:
          The kind of entities for which permissions are checked. The only
          permissible values are 'group', 'disk', 'host' and 'maildom'.

        """
        legal_target_types = ('group', 'disk', 'host', 'maildom')

        if target_type not in legal_target_types:
            raise ValueError("Illegal target_type <%s>" % target_type)

        operator_id = int(operator)
        opset = BofhdAuthOpSet(self._db)
        opset.find_by_name(cereconf.BOFHD_AUTH_GROUPMODERATOR)

        sql = """
        SELECT aot.entity_id
        FROM [:table schema=cerebrum name=auth_op_target] aot,
             [:table schema=cerebrum name=auth_role] ar
        WHERE (
            ar.entity_id = :operator_id OR
            -- do NOT replace with EXISTS, it's much more expensive
            ar.entity_id IN (
                SELECT gm.group_id
                FROM [:table schema=cerebrum name=group_member] gm
                WHERE gm.member_id = :operator_id
            ))
        AND ar.op_target_id = aot.op_target_id
        AND aot.target_type = :target_type
        AND ar.op_set_id = :op_set_id
        """

        return self.query(sql, {"operator_id": operator_id,
                                "target_type": target_type,
                                "op_set_id": opset.op_set_id})

    def can_create_group(self, operator, groupname=None, query_run_any=False):
        """If an account should be allowed to create a group.

        We allow accounts with the operation `create_group` access, if the
        groupname matches the given operation's whitelist. Superusers are
        always allowed access.

        Access could be checked based on the groupname format, depending on how
        the OpSet is defined.

        :param int operator: The operator's `entity_id`.
        :param str groupname:
            The requested groupname of the group we want to create. Note that
            this auth module does not check if this group already exists or
            not. The access control only validates the group name in this case.
        :param bool query_run_any:
            If True, we only check if the account has access to the operation,
            *somewhere*.
        :rtype: bool
        :returns:
            `True` if the account is allowed access. If, *and only if*, the
            parameter `query_run_any` is True, we return `False` if the
            operator does not have access.
        :raise PermissionDenied:
            If the account is not allowed access for the operation. This will
            not be raised if `query_run_any` is set to `True`.

        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                                operator, self.const.auth_create_group)
        for row in self._list_target_permissions(
                    operator, self.const.auth_create_group,
                    self.const.auth_target_type_global_group,
                    None, get_all_op_attrs=True):
            attr = row.get('operation_attr')
            # No operation attribute means that all groupnames are allowed:
            if not attr:
                return True
            # Check if the groupname matches the pattern defined in the
            # operation
            checktype, pattern = attr.split(':', 1)
            p = re.compile(pattern)
            if checktype == 'pre' and p.match(groupname) is not None:
                # Prefix definitions
                return True
            elif checktype == 're':
                # Regular regex definitions
                m = p.match(groupname)
                if m and m.end() == len(groupname):
                    return True
        raise PermissionDenied("Permission denied")

    def can_create_personal_group(self, operator, account=None,
                                  query_run_any=False):
        if query_run_any or self.is_superuser(operator):
            return True
        if operator == account.entity_id:
            return True
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_create_user, account)

    def can_force_delete_group(self, operator, group=None,
                               query_run_any=False):
        """
        Check if operator is allowed to force delete a group.

        This removes the group at once, expire date is not used.
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_delete_group)
        if self._has_target_permissions(operator,
                                        self.const.auth_delete_group,
                                        self.const.auth_target_type_group,
                                        group.entity_id, group.entity_id):
            return True
        raise PermissionDenied("Not allowed to force delete group")

    def can_delete_group(self, operator, group=None, query_run_any=False):
        """
        Check if operator is allowed to delete a group.

        Group deletion is done by setting the expire date to today.
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return (self._has_operation_perm_somewhere(
                operator, self.const.auth_expire_group) or
                    self._has_operation_perm_somewhere(
                operator, self.const.auth_delete_group))
        if self._has_target_permissions(operator,
                                        self.const.auth_expire_group,
                                        self.const.auth_target_type_group,
                                        group.entity_id, group.entity_id):
            return True

        if self._has_target_permissions(operator,
                                        self.const.auth_delete_group,
                                        self.const.auth_target_type_group,
                                        group.entity_id, group.entity_id):
            return True

        raise PermissionDenied("Not allowed to delete group")

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
            spread = six.text_type(self.const.Spread(spread))

        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_modify_spread)
        if entity.entity_type == self.const.entity_group:
            self.has_privileged_access_to_group(
                operator, self.const.auth_modify_spread, entity, spread)
        else:
            self.has_privileged_access_to_account_or_person(
                operator, self.const.auth_modify_spread, entity,
                operation_attr=spread)
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
        as above, but also allow the last affiliation to be removed.
        """
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
            raise PermissionDenied(
                "Can't manipulate account not owned by a person")

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
            raise PermissionDenied("No such affiliation")
        if myself and removing:
            if others:
                return True
            raise PermissionDenied(
                  "Can't remove affiliation from last account")

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
        """If the opset has add_affiliation access to the affiliation and
        status, and the operator has add_affiliation access to the
        affiliation's OU, allow adding the affiliation to the person."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            if self._has_operation_perm_somewhere(
                    operator, self.const.auth_add_affiliation):
                return True
            return False
        if self._has_target_permissions(operator,
                                        self.const.auth_add_affiliation,
                                        self.const.auth_target_type_ou,
                                        ou.entity_id, person.entity_id,
                                        six.text_type(aff_status)):
            return True
        raise PermissionDenied("No access for combination %s on person %s in "
                               "OU %02d%02d%02d" % (aff_status,
                                                    person.entity_id,
                                                    ou.fakultet, ou.institutt,
                                                    ou.avdeling))

    def can_remove_affiliation(self, operator, person=None, ou=None,
                               aff=None, query_run_any=False):
        """If the opset has rem_affiliation access to the affiliation, and the
        operator has rem_affiliation access to the affiliation's OU, allow
        removing the affiliation from the person. Not as strict on MANUELL.
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            if (self._has_operation_perm_somewhere(
                        operator, self.const.auth_remove_affiliation) or
                    self._has_operation_perm_somewhere(
                        operator, self.const.auth_create_user)):
                return True
            return False
        if self._has_target_permissions(operator,
                                        self.const.auth_remove_affiliation,
                                        self.const.auth_target_type_ou,
                                        ou.entity_id, person.entity_id,
                                        six.text_type(aff)):
            return True
        # 2015-09-11: Temporarily (?) allow all LITAs to remove manual
        #             affiliations from all persons to simplify cleaning up.
        #             CERT (bore) has given permission to do this. – tvl
        if (aff == self.const.affiliation_manuell and
            self._has_operation_perm_somewhere(operator,
                                               self.const.auth_create_user)):
            return True
        raise PermissionDenied("No access for affiliation %s on person %s in "
                               "OU %02d%02d%02d" % (aff, person.entity_id,
                                                    ou.fakultet, ou.institutt,
                                                    ou.avdeling))

    def can_create_user(self, operator, person=None, disk=None,
                        query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_create_user)
        if disk:
            return self._query_disk_permissions(operator,
                                                self.const.auth_create_user,
                                                self._get_disk(disk),
                                                None)
        if person:
            return self.has_privileged_access_to_account_or_person(
                operator, self.const.auth_create_user, person)
        raise PermissionDenied("No access")

    def can_create_user_unpersonal(self, operator, group=None, disk=None,
                                   query_run_any=False):
        """Check if operator could create an account with group owner.

        You need access to the given disk. If no disk is given, you only need
        to have access to create unpersonal users *somewhere* to be allowed -
        for now.

        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_create_user_unpersonal)
        if disk:
            return self._query_disk_permissions(
                operator, self.const.auth_create_user_unpersonal,
                self._get_disk(disk), None)
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_create_user_unpersonal):
            return True
        raise PermissionDenied("No access")

    def can_delete_user(self, operator, account=None,
                        query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_remove_user)
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_remove_user, account)

    def can_set_default_group(self, operator, account=None,
                              group=None, query_run_any=False):
        if query_run_any or self.is_superuser(operator):
            return True
        if account.account_name == group.group_name:
            # personal group:
            # TODO need better detection
            return True
        self.can_alter_group(operator, group)
        self.can_give_user(operator, account)
        return True

    def can_set_gecos(self, operator, account=None,
                      query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return (self._has_operation_perm_somewhere(
                            operator, self.const.auth_set_gecos) or
                    self._has_operation_perm_somewhere(
                            operator, self.const.auth_create_user))
        if self._is_owner_of_nonpersonal_account(operator, account):
            return True
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_set_gecos, account)

    def can_move_user(self, operator, account=None, dest_disk=None,
                      query_run_any=False):
        if self.is_superuser(operator):
            return True
        return (self.can_give_user(operator, account,
                                   query_run_any=query_run_any) and
                self.can_receive_user(operator, account, dest_disk,
                                      query_run_any=query_run_any))

    def can_give_user(self, operator, account=None,
                      query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_move_from_disk)
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_move_from_disk, account)

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
        except AttributeError:
            return False
        if not self.is_studit(operator):
            return False
        for r in account.get_account_types():
            if r['affiliation'] == aff_stud:
                break
        else:
            return False
        spreads = [int(r['spread']) for r in account.get_spread()]
        for s in (int(getattr(self.const, x)) for x in cereconf.HOME_SPREADS):
            if s in spreads:
                return False
        return True

    def _is_important_account(self, operator, account):
        """If an account is considered important."""
        # Superusers
        if self.is_superuser(account.entity_id):
            return True
        # Manually tagged important accounts
        if account.get_trait(self.const.trait_important_account):
            return True
        # Accounts that can set passwords for these accounts are also important
        if self._has_operation_perm_somewhere(
                account.entity_id, self.const.auth_set_password_important):
            return True
        return False

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
        important = self._is_important_account(operator, account)
        operation = (self.const.auth_set_password_important if important
                     else self.const.auth_set_password)
        try:
            return self.has_privileged_access_to_account_or_person(
                operator, operation, account)
        except PermissionDenied:
            raise PermissionDenied(
                "Not allowed to set password for '{}'".format(
                    account.account_name))

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
                shell.description.find("/bin/") != -1):
            return True
        # TODO 2003-07-04: Bård is going to comment this
        return self.has_privileged_access_to_account_or_person(
            operator, self.const.auth_set_password, account)

    def can_show_history(self, operator, entity=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_view_history)

        # Check if user has been granted an op-set that allows viewing the
        # entity's history in some specific fashion.
        for row in self._list_target_permissions(
                operator, self.const.auth_view_history,
                # TODO Should the auth target type be generalized?
                self.const.auth_target_type_global_group,
                None, get_all_op_attrs=True):
            attr = row.get('operation_attr')

            # Op-set allows viewing history for this entity type
            # We need try/except here as self.const.EntityType will throw
            # exceptions if attr is something else than an entity-type
            # (for example a spread-type).
            try:
                if entity.entity_type == int(self.const.EntityType(attr)):
                    return True
            except:
                pass

            # For groups we use the op-set attribute to specify groups that has
            # specified spreads (for example, postmasters are permitted to view
            # the entity history of groups with the exchange_group spread).
            # try/except is needed here for the same reasons as above.
            if entity.entity_type == self.const.entity_group:
                try:
                    spread_type = int(self.const.Spread(attr))
                    if entity.has_spread(spread_type):
                        return True
                except:
                    pass

        if entity.entity_type == self.const.entity_account:
            if self._no_account_home(operator, entity):
                return True
            return self.has_privileged_access_to_account_or_person(
                operator, self.const.auth_view_history, entity)
        if entity.entity_type == self.const.entity_group:
            return self.has_privileged_access_to_group(
                operator, self.const.auth_view_history, entity)
        raise PermissionDenied("no access for that entity_type")

    def can_cancel_request(self, operator, req_id, query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
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

    def can_request_guests(self, operator, groupname=None,
                           query_run_any=False):
        if self.is_superuser(operator):
            return True
        if not self._has_operation_perm_somewhere(
                operator, self.const.auth_guest_request):
            return False
        if query_run_any:
            return True
        if self.is_group_member(operator, groupname):
            return True
        raise PermissionDenied("Can't request guest accounts: Not member of "
                               "group {}".format(groupname))

    def can_release_guests(self, operator, groupname=None,
                           query_run_any=False):
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
            for row in pe.list_affiliations(
                            person_id=ac.owner_id,
                            affiliation=self.const.affiliation_ansatt):
                return True
        raise PermissionDenied(
                "Guest accounts can only be created by employees")

    def _is_owner_of_personal_account(self, operator, account):
        """See if person that owns the operator account is personal owner of
        account.

        :param int operator:
            The operator's `entity_id`.
        :param Cerebrum.Account account:
            The account to check is operator is personal owner of.
        :returns: True if account is an Account object and the person that
            owns the operator account is personal owner of account.
        """

        if not isinstance(account, Factory.get('Account')):
            return False
        op_account = Factory.get('Account')(self._db)
        op_account.find(operator)
        if op_account.owner_id == account.owner_id:
            return True
        else:
            return False

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
        """Check if operator can do `operation` on a victim on a disk.

        Permissions on disks may either be granted to a specific **disk**, a
        complete **host**, or a set of disks matching a **regexp**.

        :param int operator: The operator's `entity_id`.
        :param int operation: The operation constant's `intval`.
        :param Cerebrum.Disk disk:
            The Disk object to check the permissions for.
        :param int victim_id:
            The victim's `entity_id`.
        :param str operation_attr:
            Limit the operation check to a specific operation attribute.
        :rtype: bool
        :returns: True if the operator has access.
        :raise PermissionDenied: If the operator doesn't have the access.
        """
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
        for r in self._list_target_permissions(
                    operator, operation, self.const.auth_target_type_host,
                    disk.host_id, operation_attr=operation_attr):
            if not r['attr']:
                return True
            m = re.compile(r['attr']).match(disk.path.split("/")[-1])
            if m is not None:
                return True
        raise PermissionDenied("No access to disk checking for '%s'" %
                               operation)

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
            if r['attr'] and six.text_type(affiliation) == r['attr']:
                return True
        return False

    def _has_operation_perm_somewhere(self, operator, operation):
        """Check if the operator has access to a given operation, anywhere.

        Note that the operator might not be allowed to do this for a *specific*
        target - that is not checked here. The method is therefore useful if
        you only want to know what the operator is allowed to do
        (`query_run_any`) or if you check for operations that are not bound to
        specific targets. Global permissions are also considered.

        The checks are cached, so this method could be called numerously.

        :param int operator: The operator's `entity_id`.
        :param int operation: The operation constant's `intval`.
        :rtype: bool
        :return: If the operator has been granted the operation *somewhere*.
        """
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
            r = self.query(sql, {'operation': int(operation)})
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
        """Check if operator has access to `operation` for a given target.

        This method checks if the `operator` has been given the `operation`,
        and that the `operation` is granted to a target subset that includes
        the given `target`. Access is checked through global operation targets
        too.

        :param int operator: The operator's `entity_id`.
        :param int operation: The operation constant's `intval`.
        :param int target_type:
            The type of target. These are hardcoded strings, which are used as
            constants. Examples are "group", "disk", and "spread". See
            `Cerebrum/modules/bofhd/utils.py` for target type definitions.
        :param int target_id:
            The target entity's unique ID. If the target entity is an entity,
            use `entity_id`. If the target is a Cerebrum constants, use its
            `intval`. Do not confuse this with the target's id, which is the
            internal, unique id of the target in the target table.
        :param int victim_id:
            The affected entity's `entity_id`. This is used when the
            `target_id` is not the same as the victim, and is essential for
            avoiding that operators have access to superusers.
        :param str operation_attr:
            Limit the permission check to a specific operation attribute.
        :rtype: bool
        :return:
            If the operator is permitted for the given operation, on the given
            target, and by the given attributes.

        """
        if target_id is not None:
            if target_type in (self.const.auth_target_type_host,
                               self.const.auth_target_type_disk):
                if self._has_global_access(
                        operator, operation,
                        self.const.auth_target_type_global_host, victim_id,
                        operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_group:
                if self._has_global_access(
                        operator, operation,
                        self.const.auth_target_type_global_group, victim_id,
                        operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_maildomain:
                if self._has_global_access(
                        operator, operation,
                        self.const.auth_target_type_global_maildomain,
                        victim_id, operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_ou:
                if self._has_global_access(
                        operator, operation,
                        self.const.auth_target_type_global_ou, victim_id,
                        operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_dns:
                if self._has_global_access(
                        operator, operation,
                        self.const.auth_target_type_global_dns, victim_id,
                        operation_attr=operation_attr):
                    return True
            elif target_type == self.const.auth_target_type_person:
                if self._has_global_access(
                        operator, operation,
                        self.const.auth_target_type_global_person, victim_id,
                        operation_attr=operation_attr):
                    return True
        if self._list_target_permissions(operator, operation, target_type,
                                         target_id, operation_attr):
            return True
        else:
            return False

    def _list_target_permissions(self, operator, operation, target_type,
                                 target_id, operation_attr=None,
                                 get_all_op_attrs=False):
        """List operator's permission by given criterias.

        Both direct permissions and those registered at the groups the operator
        is member of are returned. Global permissions have different
        `target_type`s, so you need to call this once for local and once for
        global target types.

        This method could be used instead of `_has_target_permissions` if you
        would like to accept more than one exact `operation_attr`.

        :param int operator: The operator's `entity_id`.
        :param int operation: The operation constant's `intval`.
        :param str target_type:
            The type of target. These are hard coded strings, which are used as
            constants. Examples are "group", "disk", and "spread". See
            `Cerebrum/modules/bofhd/utils.py` for target type definitions.
        :param int target_id:
            The target entity's unique ID. If the target entity is an entity,
            use `entity_id`. If the target is a Cerebrum constants, use its
            `intval`. The target entity might not be needed if a global target
            is requested. Do not confuse this with the target's id, which is
            the internal, unique id of the target in the target table.
        :param str operation_attr:
            Fetch operations with the given operation attribute. The attribute
            must be the exact value for the operation to be returned. If this
            is set to None, you will not get operations that are set up with an
            attribute.
        :param bool get_all_op_attrs:
            In some cases, the operation attributes can't just be string
            compared, but has more functionality to it. In these cases you
            could set this parameter to `True` to fetch all attributes for the
            relevant operations, and process them further in the code. This
            makes `operation_attr` unnecessary.
        :rtype: sequence of db-rows
        :return:
            A sequence of dbrows which can be checked for `dbrow['attr']`. The
            keys are:

            - `op_id`: The operation constant's `intval`.
            - `op_target_id`: The target ID's unique ID.
            - `attr`: The target's attribute, to specify/limit the subset the
              target is valid for.
            - `operation_attr`: If `get_all_op_attrs` is True, the operation
              attribute is returned as well.

        """
        tables = [
            """[:table schema=cerebrum name=auth_operation] ao
            JOIN [:table schema=cerebrum name=auth_operation_set] AS aos
                ON ao.op_set_id = aos.op_set_id
            JOIN [:table schema=cerebrum name=auth_role] AS ar
                ON aos.op_set_id = ar.op_set_id
            JOIN [:table schema=cerebrum name=auth_op_target] AS aot
                ON aot.op_target_id = ar.op_target_id """, ]
        select = ['ao.op_id AS op_id',
                  'aot.attr AS attr',
                  'aot.op_target_id AS op_target_id', ]
        where = ['ao.op_code=:opcode',
                 'aot.target_type=:target_type', ]
        binds = {'opcode': int(operation),
                 'target_type': target_type,
                 'target_id': target_id,
                 'operation_attr': operation_attr, }
        # Add the operators auth related entities (group memberships) to the
        # check for relevant roles:
        where.append(argument_to_sql(self._get_users_auth_entities(operator),
                                     'ar.entity_id', binds, int))
        if target_id is not None:
            where.append(argument_to_sql(target_id, "aot.entity_id", binds,
                                         int))

        # Connect auth_operation and auth_op_target

        if get_all_op_attrs:
            tables.append("""
                LEFT OUTER JOIN [:table schema=cerebrum name=auth_op_attrs] aoa
                ON aoa.op_id = ao.op_id""")
            select.append('aoa.attr AS operation_attr')
        else:
            # Only fetch operations that have the exact operation attribute as
            # specified, or if it doesn't have any registered operation
            # (auth_op_attrs) attribute at all:
            where.append("""
               ((EXISTS (
                  SELECT 'foo'
                  FROM [:table schema=cerebrum name=auth_op_attrs] aoa
                  WHERE ao.op_id=aoa.op_id AND aoa.attr=:operation_attr)) OR
                NOT EXISTS (
                  SELECT 'foo'
                  FROM [:table schema=cerebrum name=auth_op_attrs] aoa
                  WHERE ao.op_id=aoa.op_id))""")

        sql = "SELECT DISTINCT %s FROM %s WHERE %s" % (', '.join(select),
                                                       ' '.join(tables),
                                                       ' AND '.join(where))
        return self.query(sql, binds)

    def _has_access_to_entity_via_ou(self, operator, operation, entity,
                                     operation_attr=None):
        """entity may be an instance of Person or Account. Returns
        True if the operator has access to any of the OU's associated
        with the entity, or False otherwise.  If an auth_op_target
        has an attribute, the attribute value is compared to the
        string representation of the affiliations the entity is a
        member of.
        """
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

        binds = {
            'opcode': int(operation),
            'target_type': self.const.auth_target_type_ou,
            'global_target_type': self.const.auth_target_type_global_ou,
            'id': entity.entity_id,
            'operation_attr': operation_attr,
        }

        for r in self.query(sql, binds):
            if not r['attr']:
                return True
            else:
                aff = six.text_type(
                    self.const.PersonAffiliation(r['affiliation']))
                if aff == r['attr']:
                    return True
        return False

    def _has_global_access(self, operator, operation, global_type, victim_id,
                           operation_attr=None):
        """Check if operator has a global permission to an operation.

        Superusers must not be affected by global permissions, which is why the
        `victim_id` is needed. Note that `global_host` and `global_group`
        should not be allowed to operate on `cereconf.BOFHD_SUPERUSER_GROUP`.

        :param int operator: The operator's `entity_id`
        :param int operation: The operation constant's `intval`.
        :param str global_type:
            The type of global target type the permission is about. Examples
            are global group access and global host access.
        :param int victim_id:
            The victim's `entity_id`. This is needed to avoid that superusers
            are affected.
        :param str operation_attr:
            Limit the access check to a specific operation attribute.
        :rtype: bool
        """
        if global_type == self.const.auth_target_type_global_group:
            if victim_id == self._superuser_group:
                return False
        elif (victim_id in
                self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP)):
            return False
        for k in self._list_target_permissions(operator, operation,
                                               global_type, None,
                                               operation_attr=operation_attr):
            return True
        return False

    def _get_users_auth_entities(self, entity_id):
        """Get all entities that the given entity could represent, auth.wise.

        An account could represent itself, but it could also be part of groups
        with privileges. This method returns all these entities that may be
        relevant for `auth_role` for the accounaccount. Only *direct*
        memberships are considered in our authorization model.

        The memberships are cached.

        :param int entity_id:
            The entity to fetch the auth related entities for. This is normally
            an account.

        :rtype: list
        :returns:
            `entity_id` for the account itself and all the groups it is a
            direct member of.

        """
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
        # Now get the operator's Person-entity_id
        # When we check whether some operator user is a member of
        # f.i. a moderator-group, in addition to checking whether the user is
        # member of the group, we want to also check whether the user's
        # owner (only if the owner is a Person) is a member of the group.
        account = Factory.get('Account')(self._db)
        account.find(entity_id)
        if account.owner_type == self.const.entity_person:
            # if the owner of the account is a Person
            ret.extend([int(x["group_id"])
                        for x in group.search(member_id=account.owner_id,
                                              indirect_members=False)])
        self._users_auth_entities_cache[entity_id] = list(set(ret))
        return ret

    def _get_group_members(self, groupname):
        """Get a group's *direct* members.

        The memberships are cached for a while.

        :param str groupname: The name of the group.

        :rtype: list
        :returns: A list of each member's `entity_id`.
        :raise Errors.NotFoundError: If the group doesn't exist.
        """
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

    def can_get_person_external_id(self, operator, person, extid_type,
                                   source_sys, query_run_any=False):
        """Check if operator can see external ids. Lets everyone see
         NO_STUDNO and NO_SAPNO. But restricts access to NO_BIRTHNO.

        :param operator: operator object
        :param person: person object
        :param str extid_type: e.g NO_STUDNO/NO_BIRTHNO
        :param str source_sys: str source source system. e.g FS/SAP
        :param query_run_any
        :return bool True or False
        """
        if query_run_any:
            return True
        if self.is_superuser(operator.get_entity_id()):
            return True
        account = Factory.get('Account')(self._db)
        account_ids = [int(
            r['account_id']) for r in
            account.list_accounts_by_owner_id(person.entity_id)]
        if operator.get_entity_id() in account_ids:
            return True

        ext_id_const = int(self.const.EntityExternalId(extid_type))
        if ext_id_const == self.const.externalid_studentnr:
            return True
        if ext_id_const == self.const.externalid_sap_ansattnr:
            return True

        operation_attr = str("{}:{}".format(
            str(self.const.AuthoritativeSystem(source_sys)),
            extid_type))

        if self._has_target_permissions(
                operator.get_entity_id(),
                self.const.auth_view_external_id,
                self.const.auth_target_type_global_person,
                None, None,
                operation_attr=operation_attr):
            return True
        raise PermissionDenied("You don't have permission to view "
                               "external ids for person entity {}".format(
                                   person.entity_id))
