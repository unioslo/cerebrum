#!/usr/bin/env python2.2

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Constants
from Cerebrum.Utils import Factory
from Cerebrum import Utils
import re

class _AuthRoleOpCode(Constants._CerebrumCode):
    "Mappings stored in the auth_role_op_code table"
    _lookup_table = '[:table schema=cerebrum name=auth_op_code]'

class Constants(Constants.Constants):
    auth_alter_printerquota = _AuthRoleOpCode('alter_printerquo', 'desc')
    auth_set_password = _AuthRoleOpCode('set_password', 'desc')
    auth_move_from_disk = _AuthRoleOpCode('move_from_disk',
                                         'can move from disk')
    auth_move_to_disk = _AuthRoleOpCode('move_to_disk',
                                         'can move to disk')
    auth_alter_group_membership = _AuthRoleOpCode('alter_group_memb', 'desc')

class BofhdAuthOpSet(DatabaseAccessor):
    __metaclass__ = Utils.mark_update
    __read_attr__ = ('__in_db', 'const')
    __write_attr__ = ('op_set_id', 'name')
    dontclear = ('const',)

    def __init__(self, database):
        """

        """
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
        self.execute("""INSERT INTO auth_operation (op_code, op_id, op_set_id)
        VALUES (:code, :op_id, :op_set_id)""", {
            'code': int(op_code), 'op_id': op_id, 'op_set_id': self.op_set_id})
        return op_id

    def add_op_attrs(self, op_id, attr):
        self.execute("""INSERT INTO auth_op_attrs (op_id, attr)
        VALUES (:op_id, :attr)""", {
            'op_id': op_id, 'attr': attr})

class BofhdAuthOpTarget(DatabaseAccessor):
    __metaclass__ = Utils.mark_update
    __read_attr__ = ('__in_db', 'const')
    __write_attr__ = ('entity_id', 'target_type', 'has_attr', 'op_target_id')
    dontclear = ('const',)

    def __init__(self, database):
        """

        """
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
        self.execute("""INSERT INTO auth_op_target_attrs (op_target_id, attr)
        VALUES (:id, :attr)""", {'id': self.op_target_id, 'attr': attr})

class BofhdAuthRole(DatabaseAccessor):
    def __init__(self, database):
        """

        """
        super(BofhdAuthRole, self).__init__(database)

    def grant_auth(self, entity_id, op_set_id, op_target_id):
        self.execute("""INSERT INTO auth_role (entity_id, op_set_id, op_target_id)
        VALUES (:e_id, :os_id, :t_id)""", {
            'e_id': entity_id, 'os_id': op_set_id, 't_id': op_target_id})


class BofhdAuth(DatabaseAccessor):
    def __init__(self, database):
        """

        """
        super(BofhdAuth, self).__init__(database)
        self.const = Factory.get('Constants')(database)
        self.std_qry = """
        SELECT 'yes'
        FROM auth_role_grants arg, auth_role_ops op
        WHERE arg.entity_id=:operator AND arg.role_id=op.role_id
          AND op.op_code=:opcode AND arg.dest_entity_id=:dest
          """
        self.attr_qry = """
        SELECT attr
        FROM auth_role_grants arg, auth_role_attrs ara, auth_role_ops op
        WHERE arg.entity_id=:operator AND ara.role_id=arg.role_id AND
          arg.role_id=op.role_id AND op.op_code=:opcode
          """

    qry = """
    SELECT ao.op_id, aot.op_target_id, aot.has_attr
    FROM auth_operation_set aos, auth_operation ao,
         auth_role ar, auth_op_target aot, 
    WHERE aos.op_set_id=ao.op_set_id
        AND ao.op_code=:code
        AND ar.entity_id=:e_id
        AND ar.op_set_id=ao.op_set_id
        AND ar.op_target_id=aot.op_target_id
        AND aot.entity_id=:tgt_e_id
        AND aot.target_type=:t_type
    """

    def can_change_disk(self, operator, disk):

        """With controls_disk, destination_id may point to a disk or a
        host.  If pointing to a host, auth_role_attrs are checked for
        wildcard matches.
        """

        if (self.query(self.std_qry,
                       {'operator': operator,
                        'opcode': self.const.controls_disk,
                        'dest': disk.entity_id}) or
            self.query(self.std_qry,
                       {'operator': operator,
                        'opcode': self.const.controls_host,
                        'dest': disk.host_id})):
            return 1
        for wc in self.query(self.attr_qry+" AND arg.dest_entity_id=:dest", {
            'operator': operator,
            'opcode': self.const.controls_wcdisk,
            'dest': disk.host_id}):
            m = re.compile(wc['attr']).match(disk.path)
            if m != None:
                return 1
        return 0

    def can_alter_group(self, operator, group_id):
        if self.query(self.std_qry,
                      {'operator': operator,
                       'opcode': self.const.auth_alter_group_membership,
                       'dest': group_id}):
            return 1
        return 0
