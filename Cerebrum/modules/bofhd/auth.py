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

import re
import sys

import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Constants
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.modules import PosixGroup
from Cerebrum.Utils import Factory, mark_update
from Cerebrum.modules.bofhd.errors import PermissionDenied


class AuthConstants(Constants._CerebrumCode):
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

    def del_operation(self, op_code):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=auth_operation]
        WHERE op_code=:op_code AND op_set_id=:op_set_id""", {
            'op_code': int(op_code), 'op_set_id': self.op_set_id})

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
        if target_id is not None:
            ewhere.append("op_target_id=:target_id")
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
        ORDER BY entity_id""" % ewhere, locals())


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
                          ", ".join(["%i" % i for i in entity_ids]))
        if op_set_id is not None:
            ewhere.append("op_set_id=:op_set_id")
        if op_target_id is not None:
            ewhere.append("op_target_id=:op_target_id")
        return self.query("""
        SELECT DISTINCT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role]
        WHERE (%s)""" % " AND ".join(ewhere), locals())

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
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    The query_run_any parameter is used to determine if operator has
    this permission somewhere.  It is used to filter available
    commands in bofhds get_commands().  Note that this should NOT be
    used a security measure"""

    def __init__(self, database):
        super(BofhdAuth, self).__init__(database)
        self.const = Factory.get('Constants')(database)
        self._group_member_cache = Cache.Cache(mixins = [Cache.cache_timeout],
                                               timeout = 60)
        group = Factory.get('Group')(self._db)
        group.find_by_name(cereconf.BOFHD_SUPERUSER_GROUP)
        self._superuser_group = group.entity_id
        self._any_perm_cache = Cache.Cache(mixins=[Cache.cache_mru,
                                                   Cache.cache_slots],
                                           size=500)

    def is_superuser(self, operator, query_run_any=False):
        if operator in self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP):
            return True
        return False

    def is_postmaster(self, operator, query_run_any=False):
        # Rather than require an operation as an argument, we pick a
        # suitable value which all postmasters ought to have.
        # auth_email_create seems appropriate.
        return self._query_target_permissions(operator,
                                              self.const.auth_email_create,
                                              self.const.auth_target_type_global_maildomain,
                                              None, None)

    def is_account_owner(self, operator, operation, entity):
        """See if operator has access to entity.  entity can be either
        a Person or Account object.  First check if operator is
        allowed to perform operation on one of the OUs associated with
        Person or Account.  If that fails, and the entity is an
        Account, check if operator's access to the account's disk.
        Returns True for success and raises exception PermissionDenied
        for failure."""

        if self._has_access_to_entity_via_ou(operator, operation, entity):
            return True
        if not isinstance(entity, Factory.get('Account')):
            raise PermissionDenied("No access to person")
        disk = self._get_user_disk(entity.entity_id)
        if disk and disk['disk_id']:
            self._query_disk_permissions(operator, operation,
                                         self._get_disk(disk['disk_id']),
                                         entity.entity_id)
        else:
            raise PermissionDenied("No access to account")


    def can_set_person_user_priority(self, operator, account=None,
                                     query_run_any=False):
        if query_run_any:
            return True
        if self.is_superuser(operator) or operator == account.entity_id:
            return True
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     account)

    def can_get_student_info(self, operator, person=None, query_run_any=False):
        # TODO: Change can_get_student_info so that the old studit
        # group may be grantet auth_view_studentinfo to global_host
        if (self.is_superuser(operator) or
            operator in self._get_group_members(cereconf.BOFHD_STUDADM_GROUP)):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not authorized to view student info")

    def can_create_person(self, operator, ou=None, affiliation=None,
                          query_run_any=False):
        if (self.is_superuser(operator) or
            self._query_target_permissions(operator,
                                           self.const.auth_create_user,
                                           self.const.auth_target_type_host,
                                           None, None) or
            self._query_target_permissions(operator,
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
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_set_password)
        # TODO 2003-07-04: Bård is going to comment this
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     entity)
    
    def can_remove_quarantine(self, operator, entity=None, qtype=None,
                              query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_set_password)
        # TODO 2003-07-04: Bård is going to comment this
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     entity)

    def can_set_quarantine(self, operator, entity=None, qtype=None,
                           query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_set_password)
        # TODO 2003-07-04: Bård is going to comment this
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     entity)

    def can_show_quarantines(self, operator, entity=None,
                             query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_set_password)
        # TODO 2003-07-04: Bård is going to comment this
        if not(isinstance(entity, Factory.get('Account'))):
            raise PermissionDenied("No access")
        return self.is_account_owner(operator, self.const.auth_set_password,
                                     entity)

    def can_create_disk(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        # auth_create_disk is not tied to a target
        if self._has_operation_perm_somewhere(
            operator, self.const.auth_add_disk):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_remove_disk(self, operator, query_run_any=False):
        return self.can_create_disk(operator, query_run_any=query_run_any)

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
        if self._query_target_permissions(operator,
                                          self.const.auth_alter_group_membership,
                                          self.const.auth_target_type_group,
                                          group.entity_id, group.entity_id):
            return True
        raise PermissionDenied("No access to group")

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
        if self.is_superuser(operator):
            return True
        if query_run_any:
            if self._has_operation_perm_somewhere(operator,
                                                  self.const.auth_create_user):
                return True
            account = Factory.get('Account')(self._db)
            account.find(operator)
        # No need to add this command if the operator has a personal
        # file group already.
        lacks_group = False
        try:
            pg = PosixGroup.PosixGroup(self._db)
            pg.find_by_name(account.account_name)
        except Errors.NotFoundError:
            lacks_group = True
        if query_run_any:
            return lacks_group
        if operator == account.entity_id:
            if lacks_group:
                return True
            raise PermissionDenied("Already has personal file group")
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
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")
    
    def can_add_spread(self, operator, entity=None, spread=None,
                       query_run_any=False):
        """The list of spreads that an operator may modify are stored
        in auth_op_target with target_type 'spread' and entity_id set
        to the integer code value of the spread."""
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_modify_spread)
        if spread is not None:
            if isinstance(spread, str):
                spread = Constants._SpreadCode(spread)
            if self._query_target_permissions(operator,
                                              self.const.auth_modify_spread,
                                              self.const.auth_target_type_spread,
                                              int(spread), None):
                return True
        raise PermissionDenied("No access to spread")

    def can_remove_spread(self, operator, entity=None, spread=None,
                          query_run_any=False):
        return self.can_add_spread(self, operator, entity, spread,
                                   query_run_any=query_run_any)
    
    def can_add_account_type(self, operator, account=None, ou=None, aff=None,
                            aff_status=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            if self._has_operation_perm_somewhere(operator, self.const.auth_create_user):
                return True
            return False
        # Return true if we have auth_create_user on this user, and
        # the affiliation is of type manual or the person has the affiliaton
        disk = self._get_user_disk(account.entity_id)
        if disk:
            disk = disk['disk_id']
        self.can_create_user(operator, disk=disk)
        if aff == self.const.affiliation_manuell:
            return True
        person = Person.Person(self._db)
        person.find(account.owner_id)
        for tmp_aff in person.get_affiliations():
            if (tmp_aff['affiliation'] == aff and
                tmp_aff['status'] == aff_status):
                return True
        raise PermissionDenied("No access")

    def can_remove_account_type(self, operator, account=None, ou=None,
                               aff=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            if self._has_operation_perm_somewhere(operator, self.const.auth_create_user):
                return True
            return False
        disk = self._get_user_disk(account.entity_id)
        if disk:
            disk = disk['disk_id']
        return self.can_create_user(operator, disk=disk)
    
    def can_add_affiliation(self, operator, person=None, ou=None, aff=None,
                            aff_status=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        # TODO (at a later time): add 'auth_add_affiliation',
        # 'auth_remove_affiliation'.  Determine how these should be
        # connected to ou etc.
        # Currently we allow anyone that can create users to
        # add/remove any affiliation of type manuell
        if query_run_any:
            if self._has_operation_perm_somewhere(operator, self.const.auth_create_user):
                return True
            return False
        if (aff == self.const.affiliation_manuell and
            self._has_operation_perm_somewhere(operator, self.const.auth_create_user)):
            return True
        raise PermissionDenied("No access for that person affiliation combination")

    def can_remove_affiliation(self, operator, person=None, ou=None,
                               aff=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            if self._has_operation_perm_somewhere(operator, self.const.auth_create_user):
                return True
            return False
        if (aff == self.const.affiliation_manuell and
            self._has_operation_perm_somewhere(operator, self.const.auth_create_user)):
            return True
        raise PermissionDenied("Currently limited to superusers")

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
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_set_gecos)
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

    def can_set_password(self, operator, account=None,
                         query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True
        if operator == account.entity_id:
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
            return (self._has_operation_perm_somewhere(operator,
                               self.const.auth_create_user) or
                    self._has_operation_perm_somewhere(operator,
                               self.const.auth_view_history))
        if entity.entity_type == self.const.entity_account:
            try:
                return self.is_account_owner(operator,
                                             self.const.auth_create_user,
                                             entity)
            except:
                pass
            return self.is_account_owner(operator, self.const.auth_view_history,
                                         entity)
        raise PermissionDenied("no access for that entity_type")

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
        return self._is_local_postmaster(operator,
                                         self.const.auth_set_password,
                                         account, None, query_run_any)

    # the user, local sysadmin, and helpdesk can ask for migration
    def can_email_migrate(self, operator, account=None, query_run_any=False):
        if query_run_any or account and operator == account.entity_id:
            return True
        return self._is_local_postmaster(operator,
                                         self.const.auth_email_migrate,
                                         account, None, query_run_any)

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
        return self._is_local_postmaster(operator,
                                         self.const.auth_email_quota_set,
                                         account, None, query_run_any)

    # the user and local sysadmin is allowed to turn forwarding and
    # tripnote on/off
    def can_email_forward_toggle(self, operator, account=None,
                                 query_run_any=False):
        if query_run_any or account and operator == account.entity_id:
            return True
        return self._is_local_postmaster(operator,
                                         self.const.auth_email_forward_off,
                                         account, None, query_run_any)

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
        return self._is_local_postmaster(operator,
                                         self.const.auth_email_vacation_off,
                                         account, None, query_run_any)

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
        return PermissionDenied("Currently limited to superusers")

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
        return self._is_local_postmaster(operator, self.const.auth_email_create,
                                         None, domain, query_run_any)

    def can_email_multi_delete(self, operator, domain=None, group=None,
                               query_run_any=False):
        return self._is_local_postmaster(operator, self.const.auth_email_delete,
                                         None, domain, query_run_any)

    # create e-mail targets of type "forward"
    def can_email_forward_create(self, operator, domain=None,
                                 query_run_any=False):
        return self._is_local_postmaster(operator, self.const.auth_email_create,
                                         None, domain, query_run_any)

    # associate a new e-mail address with an account, or other target.
    def can_email_address_add(self, operator, account=None, domain=None,
                              query_run_any=False):
        return self._is_local_postmaster(operator, self.const.auth_email_create,
                                         account, domain, query_run_any)

    def can_email_address_delete(self, operator, account=None, domain=None,
                                 query_run_any=False):
        return self._is_local_postmaster(operator, self.const.auth_email_delete,
                                         account, domain, query_run_any)

    def _is_local_postmaster(self, operator, operation, account=None,
                             domain=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(operator, operation)
        if self.is_postmaster(operator):
            return True
        if domain:
            self._query_maildomain_permissions(operator, operation,
                                               domain, None)
        if account:
            self.is_account_owner(operator, operation, account)
        return True

    def _query_disk_permissions(self, operator, operation, disk, victim_id):
        """Permissions on disks may either be granted to a specific
        disk, a complete host, or a set of disks matching a regexp"""
        
        if self._query_target_permissions(operator, operation,
                                          self.const.auth_target_type_disk,
                                          disk.entity_id, victim_id):
            return True
        if self._has_global_access(operator, operation,
                                   self.const.auth_target_type_global_host,
                                   victim_id):
            return True
        for r in self._query_target_permissions(operator, operation,
                                                self.const.auth_target_type_host,
                                                disk.host_id, victim_id):
            if not r['attr']:
                return True
            m = re.compile(r['attr']).match(disk.path.split("/")[-1])
            if m != None:
                return True
        raise PermissionDenied("No access to disk")

    def _query_maildomain_permissions(self, operator, operation, domain,
                                      victim_id):
        """Permissions on e-mail domains are granted specifically."""
        if self._has_global_access(operator, operation,
                                   self.const.auth_target_type_global_maildomain,
                                   victim_id):
            return True
        if self._query_target_permissions(operator, operation,
                                          self.const.auth_target_type_maildomain,
                                          domain.email_domain_id, victim_id):
            return True
        raise PermissionDenied("No access to e-mail domain")

    def _query_ou_permissions(self, operator, operation, ou, affiliation,
                              victim_id):
        """Permissions on OUs are granted specifically."""
        ou_id = None
        if ou:
            ou_id = ou.ou_id
        for r in self._query_target_permissions(operator, operation,
                                                self.const.auth_target_type_ou,
                                                ou_id, victim_id):
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
            SELECT 'foo'
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
                                  target_id, victim_id):
        """Query any permissions that operator, or any of the groups
        where operator is a member, has been granted operation on
        target_type:target_id"""
        ewhere = ""

        if target_id is not None:
            ewhere = "AND aot.entity_id=:target_id"
            if target_type in (self.const.auth_target_type_host,
                               self.const.auth_target_type_disk):
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_host,
                                           victim_id):
                    return True
            elif target_type == self.const.auth_target_type_group:
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_group,
                                           victim_id):
                    return True
            elif target_type == self.const.auth_target_type_maildomain:
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_maildomain,
                                           victim_id):
                    return True
            elif target_type == self.const.auth_target_type_ou:
                if self._has_global_access(operator, operation,
                                           self.const.auth_target_type_global_ou,
                                           victim_id):
                    return True

        # Connect auth_operation and auth_op_target
        sql = """
        SELECT aot.attr, ao.op_id, aot.op_target_id
        FROM [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_operation_set] aos,
             [:table schema=cerebrum name=auth_role] ar,
             [:table schema=cerebrum name=auth_op_target] aot
        WHERE
           ao.op_code=:opcode AND
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
                           'target_id': target_id})

    def _has_access_to_entity_via_ou(self, operator, operation, entity):
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

        sql = """
        SELECT at.affiliation, aot.attr, ao.op_id, aot.op_target_id
        FROM [:table schema=cerebrum name=%(table_name)s] at,
             [:table schema=cerebrum name=auth_op_target] aot,
             [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_operation_set] aos,
             [:table schema=cerebrum name=auth_role] ar
        WHERE at.%(id_colname)s=:id AND
              at.ou_id=aot.entity_id AND
              aot.op_target_id=ar.op_target_id AND
              aot.target_type=:target_type AND
              ar.entity_id IN (%(group_list)s) AND
              aos.op_set_id=ar.op_set_id AND
              ao.op_set_id=aos.op_set_id AND
              ao.op_code=:opcode
              """ % {'group_list': ", ".join(operator_groups),
                     'table_name': table_name,
                     'id_colname': id_colname}

        for r in self.query(sql,
                            {'opcode': int(operation),
                             'target_type': self.const.auth_target_type_ou,
                             'id': entity.entity_id}):
            if not r['attr']:
                return True
            else:
                aff = str(self.const._PersonAffiliationCode(r['affiliation']))
                if aff == r['attr']:
                    return True
        return False

    def _has_global_access(self, operator, operation, global_type, victim_id):
        """global_host and global_group should not be allowed to
        operate on BOFHD_SUPERUSER_GROUP"""
        if global_type == self.const.auth_target_type_global_group:
            if victim_id == self._superuser_group:
                return False
        elif victim_id in \
                 self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP):
            return False
        for k in self._query_target_permissions(operator, operation,
                                                global_type, None, None):
            return True
        return False

    def _get_users_auth_entities(self, entity_id):
        """Return all entity_ids that may be relevant in auth_role for
        this user"""
        group = Factory.get('Group')(self._db)
        ret = [entity_id]
        # TODO: Assert that user is a union member
        for r in group.list_groups_with_entity(entity_id):
            ret.append(r['group_id'])
        return ret

    def _get_group_members(self, groupname):
        try:
            return self._group_member_cache[groupname]
        except KeyError:
            pass
        group = Factory.get('Group')(self._db)
        group.find_by_name(groupname)
        members = [int(id) for id in group.get_members()]
        self._group_member_cache[groupname] = members
        return members

    def _get_user_disk(self, account_id):
        try:
            account = Factory.get('Account')(self._db)
            account.find(account_id)
            return account.get_home(self.const.spread_uio_nis_user)
        except Errors.NotFoundError:
            return None

    def _get_disk(self, disk_id):
        disk = Factory.get('Disk')(self._db)
        disk.find(disk_id)
        return disk
