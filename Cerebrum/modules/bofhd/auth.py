#!/usr/bin/env python2.2

import re
import sys

import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Constants
from Cerebrum import Group
from Cerebrum.Utils import Factory
from Cerebrum import Utils
from Cerebrum import Disk
from Cerebrum.modules.bofhd.errors import PermissionDenied

class AuthConstants(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=auth_op_code]'
    pass

class BofhdAuthOpSet(DatabaseAccessor):
    """Methods for updating auth_operation_set, auth_operation and
    auth_op_attrs which specifies what operations may be performed."""

    __metaclass__ = Utils.mark_update
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
        self.__updated = False

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
        self.__updated = False

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
        self.__updated = False
        return is_new

    def add_operation(self, op_code):
        op_id = int(self.nextval('entity_id_seq'))
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_operation]
        (op_code, op_id, op_set_id)
        VALUES (:code, :op_id, :op_set_id)""", {
            'code': int(op_code), 'op_id': op_id, 'op_set_id': self.op_set_id})
        return op_id

    def add_op_attrs(self, op_id, attr):
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_op_attrs] (op_id, attr)
        VALUES (:op_id, :attr)""", {
            'op_id': op_id, 'attr': attr})

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
    """Methods for updating auth_op_target and auth_op_target_attrs
    with information identifying targets which operations may be
    performed on."""

    __metaclass__ = Utils.mark_update
    __read_attr__ = ('__in_db', 'const')
    __write_attr__ = ('entity_id', 'target_type', 'has_attr', 'op_target_id')
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
        self.__updated = False

    def populate(self, entity_id, target_type):
        self.__in_db = False
        self.entity_id = entity_id
        self.target_type = target_type
        self.has_attr = 0

    def write_db(self):
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.op_target_id = int(self.nextval('entity_id_seq'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=auth_op_target]
            (op_target_id, entity_id, target_type, has_attr) VALUES
            (:t_id, :e_id, :t_type, :has_attr)""", {
                't_id': self.op_target_id, 'e_id': self.entity_id,
                't_type': self.target_type, 'has_attr': self.has_attr})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=auth_op_target]
            SET target_type=:t_type, has_attr=:has_attr, entity_id=:e_id
            WHERE op_target_id=:t_id""", {
                't_id': self.op_target_id, 'e_id': self.entity_id,
                't_type': self.target_type, 'has_attr': self.has_attr})
        del self.__in_db
        self.__in_db = True
        self.__updated = False
        return is_new

    def add_op_target_attr(self, attr):
        self.has_attr = 1
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=auth_op_target_attrs]
        (op_target_id, attr)
        VALUES (:id, :attr)""", {'id': self.op_target_id, 'attr': attr})

    def del_op_target_attr(self, attr):
        # TBD: should we also check if has_attr should be set to 0?
        self.execute("""DELETE FROM [:table schema=cerebrum name=auth_op_target_attrs]
        WHERE op_target_id=:id AND attr=:attr""", {'id': self.op_target_id, 'attr': attr})

    def list(self, target_id=None, target_type=None, entity_id=None):
        ewhere = []
        if entity_id is not None:
            ewhere.append("entity_id=:entity_id")
        if target_id is not None:
            ewhere.append("op_target_id=:target_id")
        if target_type is not None:
            ewhere.append("target_type=:target_type")
        return self.query("""
        SELECT op_target_id, entity_id, target_type, has_attr
        FROM [:table schema=cerebrum name=auth_op_target]
        WHERE %s""" % " AND ".join(ewhere), {
            'target_type': target_type, 'entity_id': entity_id,
            'target_id': target_id})

    def list_target_attrs(self, op_target_id):
        return self.query("""
        SELECT attr
        FROM [:table schema=cerebrum name=auth_op_target_attrs]
        WHERE op_target_id=:op_target_id""", {'op_target_id': op_target_id})

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

    def list(self, entity_id):
        return self.query("""
        SELECT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role]
        WHERE entity_id=:entity_id""", {
            'entity_id': entity_id})

class BofhdAuth(DatabaseAccessor):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action."""

    def __init__(self, database):
        super(BofhdAuth, self).__init__(database)
        self.const = Factory.get('Constants')(database)
        self._superusers = self._get_group_members(cereconf.BOFHD_SUPERUSER_GROUP)
        # TODO: should not be hardcoded, but what do we call the cereconf variable?
        self._student_info_users = self._get_group_members("studit")

    def is_superuser(self, operator):
        if operator in self._superusers:
            return 1
        return 0
    
    def can_set_person_user_priority(self, operator, account):
        if self.is_superuser(operator) or operator == account.entity_id:
            return 1
        return self._query_disk_permissions(operator,
                                            self.const.auth_set_password,
                                            self._get_disk(account.disk_id))

    def can_get_student_info(self, operator, person):
        if self.is_superuser(operator) or operator in self._student_info_users:
            return 1
        raise PermissionDenied("Not authorized to view student info")

    def can_create_person(self, operator):
        if (self.is_superuser(operator) or
            self._query_target_permissions(operator, self.const.auth_create_user, 'host', None) or
            self._query_target_permissions(operator, self.const.auth_create_user, 'disk', None)):
            return 1
        raise PermissionDenied("Not allowed to create persons")

    def can_set_person_id(self, operator, person, idtype):
        if self.is_superuser(operator):
            return 1
        if person.get_external_id(id_type=idtype):
            raise PermissionDenied("Already has a value for that idtype")
        account = Account.Account(self._db)
        account.find(operator)
        if person.entity_id == account.owner_id:
            return 1
        return self._query_disk_permissions(operator,
                                            self.const.auth_create_user,
                                            self._get_disk(account.disk_id))

    def can_alter_printerquta(self, operator, account):
        if self.is_superuser(operator):
            return 1
        return self._query_disk_permissions(operator,
                                            self.const.auth_alter_printerquota,
                                            self._get_disk(account.disk_id))
    
    def can_query_printerquta(self, operator, account):
        if self.is_superuser(operator):
            return 1
        return 1                     # Anyone can query quota

    def can_disable_quarantine(self, operator, entity, qtype):
        if self.is_superuser(operator):
            return 1
        # TODO 2003-07-04: Bård is going to comment this
        return self._query_disk_permissions(operator,
                                            self.const.auth_set_password,
                                            self._get_disk(account.disk_id))
    
    def can_remove_quarantine(self, operator, entity, qtype):
        if self.is_superuser(operator):
            return 1
        # TODO 2003-07-04: Bård is going to comment this
        return self._query_disk_permissions(operator,
                                            self.const.auth_set_password,
                                            self._get_disk(account.disk_id))

    def can_set_quarantine(self, operator, entity, qtype):
        if self.is_superuser(operator):
            return 1
        # TODO 2003-07-04: Bård is going to comment this
        return self._query_disk_permissions(operator,
                                            self.const.auth_set_password,
                                            self._get_disk(account.disk_id))

    def can_show_quarantines(self, operator, entity):
        if self.is_superuser(operator):
            return 1
        # TODO 2003-07-04: Bård is going to comment this
        return self._query_disk_permissions(operator,
                                            self.const.auth_set_password,
                                            self._get_disk(account.disk_id))

    def can_alter_group(self, operator, group):
        if self.is_superuser(operator):
            return 1
        if self._query_target_permissions(operator,
                                          self.const.auth_alter_group_membership,
                                          'group', group.entity_id):
            return 1
        raise PermissionDenied("No access to group")


    def can_create_group(self, operator):
        if self.is_superuser(operator):
            return 1
        raise PermissionDenied("Currently limited to superusers")
    
    def can_delete_group(self, operator, group):
        if self.is_superuser(operator):
            return 1
        raise PermissionDenied("Currently limited to superusers")

    def can_add_spread(self, operator, entity, spread):
        """The list of spreads that an operator may modify are stored
        in auth_op_target_attrs, where the corresponding
        auth_op_target has target_type='spread' and entity_id=None"""
        if self.is_superuser(operator):
            return 1
        for r in self._query_target_permissions(operator, self.const.auth_modify_spread,
                                                'spread', None) :
            if not int(r['has_attr']):
                continue
            if self.query("""
            SELECT attr
            FROM [:table schema=cerebrum name=auth_op_target_attrs]
            WHERE op_target_id=:op_target_id AND attr=:spread""", {
                'op_target_id': r['op_target_id'],
                'spread': str(spread)}):
                return 1
        raise PermissionDenied("No access to spread")
    
    def can_remove_spread(self, operator, entity, spread):
        return self.can_add_spread(self, operator, entity, spread)
    
    def can_add_affiliation(self, operator, person, ou, aff, aff_status):
        if self.is_superuser(operator):
            return 1
        # TODO (at a later time): add 'auth_add_affiliation',
        # 'auth_remove_affiliation'.  Determine how these should be
        # connected to ou etc.
        raise PermissionDenied("Currently limited to superusers")

    def can_remove_affiliation(self, operator, person, ou, aff):
        if self.is_superuser(operator):
            return 1
        raise PermissionDenied("Currently limited to superusers")

    def can_create_user(self, operator, person, disk):
        if self.is_superuser(operator):
            return 1
        return self._query_disk_permissions(operator,
                                            self.const.auth_create_user,
                                            self._get_disk(disk))

    def can_delete_user(self, operator, account):
        if self.is_superuser(operator):
            return 1
        return self._query_disk_permissions(operator,
                                            self.const.auth_remove_user,
                                            self._get_disk(account.disk_id))
    
    def can_set_gecos(self, operator, account):
        if self.is_superuser(operator):
            return 1
        raise PermissionDenied("Currently limited to superusers")

    def can_move_user(self, operator, account, dest_disk):
        if self.is_superuser(operator):
            return 1
        return self.can_give_user(operator, account) and \
               self.can_receive_user(operator, account, dest_disk)

    def can_give_user(self, operator, account):
        if self.is_superuser(operator):
            return 1
        return self._query_disk_permissions(operator,
                                            self.const.auth_move_from_disk,
                                            self._get_disk(account.disk_id))

    def can_receive_user(self, operator, account, dest_disk):
        if self.is_superuser(operator):
            return 1
        return self._query_disk_permissions(operator,
                                            self.const.auth_move_to_disk,
                                            self._get_disk(dest_disk))

    def can_set_password(self, operator, account):
        if self.is_superuser(operator):
            return 1
        return self._query_disk_permissions(operator,
                                            self.const.auth_set_password,
                                            self._get_disk(account.disk_id))

    def can_set_shell(self, operator, account, shell):
        # TBD: auth_op_attrs may contain legal shells
        if self.is_superuser(operator):
            return 1
        # TODO 2003-07-04: Bård is going to comment this
        return self._query_disk_permissions(operator,
                                            self.const.auth_set_password,
                                            self._get_disk(account.disk_id))

    def _query_disk_permissions(self, operator, operation, disk):
        """Permissions on disks may either be granted to a specific
        disk, a complete host, or a set of disks matching a regexp"""
        
        if self._query_target_permissions(operator, operation, 'disk',
                                          disk.entity_id):
            return 1
        for r in self._query_target_permissions(operator, operation, 'host',
                                                disk.host_id):
            if not int(r['has_attr']):
                return 1
            for r2 in self.query("""
            SELECT attr
            FROM [:table schema=cerebrum name=auth_op_target_attrs]
            WHERE op_target_id=:op_target_id""",
                                 {'op_target_id': r['op_target_id']}):
                m = re.compile(wc['attr']).match(disk.path)
                if m != None:
                    return 1
        raise PermissionDenied("No access to disk")

    def _query_target_permissions(self, operator, operation, target_type,
                                  target_id):
        """Query any permissions that operator, or any of the groups
        where operator is a member has been grantet operation on
        target_type:target_id"""
        ewhere = ""
        if target_id is not None:
            ewhere = "AND aot.entity_id=:target_id"
        # Connect auth_operation and auth_op_target
        sql = """
        SELECT aot.has_attr, ao.op_id, aot.op_target_id
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
    
    def _get_users_auth_entities(self, entity_id):
        """Return all entity_ids that may be relevant in auth_role for
        this user"""
        group = Group.Group(self._db)
        ret = [entity_id]
        # TODO: Assert that user is a union member
        for r in group.list_groups_with_entity(entity_id):
            ret.append(r['group_id'])
        return ret

    def _get_group_members(self, groupname):
        group = Group.Group(self._db)
        group.find_by_name(groupname)
        return [int(id) for id in group.get_members()]
        
    def _get_disk(self, disk_id):
        disk = Disk.Disk(self._db)
        disk.find(disk_id)
        return disk
