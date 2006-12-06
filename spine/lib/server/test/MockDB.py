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
#

import sys
sys.path.append("..")
from unittest import TestCase, main
from pmock import *

from Cerebrum.spine.Account import Account
from Cerebrum.spine.Person import Person
from Cerebrum.spine.Entity import Entity
from Cerebrum.spine.Group import Group
from Cerebrum.spine.OU import OU

from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode as AuthRoleOpCode
from Cerebrum.Utils import Factory

from Cerebrum.spine.SpineLib import Database

import TestData

class MockDB(Mock):
    """A mock database to allow fast and isolated testing of bofhd.auth modules
    and the authorization layer."""

    def __init__(self, operation_sets={}, value_domain=None):
        super(MockDB, self).__init__()
        self.CONST = dict(TestData.types) # Make local copy.

        if value_domain:
            self.CONST['account_names'] = value_domain
            self.CONST['group_names'] = value_domain

        self._expected_sql = {}
        self._entities = []

        for name, data in operation_sets.items():
            self._add_opset(name, data['codestrs'])
        self._init_accounts()
        self._init_groups()
        self._init_bofhdauth()
        self._init_superuser()

    def _getClass(self):
        """Trick isinstance to believe we're a Database"""
        return Database.Database
    __class__ = property(_getClass)

    def _parse_sql(self, string):
        s, string = string[0], string[1:]

        sql_end = string.find(s)
        sql = string[:sql_end]
        args_start = string.find("{", sql_end)
        args = eval(string[args_start:])
        return sql, args

    def _add_sql(self, sql, args=None, res=None):
        if type(args) == dict:
            args = str(args) # Could be a dictionary.
        if not self._expected_sql.get(sql):
            self._expected_sql[sql] = {}
        self._expected_sql[sql][args] = res

    def _init_bofhdauth(self, value_domain=None):
        """When BofhdAuth is initialized, it retrieves some information about
        the superuser group.  First it finds out what domain_code it should use.
        Then it looks up the entity_id and then the entity_type of the
        cereconf.BOFHD_SUPERUSER_GROUP.  (The default value is bootstrap_group).
        Finally it looks up some more information about this group.
        """
        if value_domain:
            self.CONST['account_names'] = value_domain
            self.CONST['group_names'] = value_domain

        # SELECT entity_id FROM entity_name WHERE value_domain = 363 AND entity_name = 'bootstrap_group'
        sql = '\n        SELECT entity_id\n        FROM [:table schema=cerebrum name=entity_name]\n        WHERE value_domain=:domain AND entity_name=:name'
        args = {'domain': self.CONST['account_names'], 'name': 'bootstrap_group'}
        res = self.CONST['bootstrap_group']
        self._add_sql(sql, args, res)
        # SELECT entity_id, entity_type FROM entity_info WHERE entity_id = 19
        sql = '\n        SELECT entity_id, entity_type\n        FROM [:table schema=cerebrum name=entity_info]\n        WHERE entity_id=:e_id'
        args = {'e_id': self.CONST['bootstrap_group']}
        res = [self.CONST['bootstrap_group'], self.CONST['group']]
        self._add_sql(sql, args, res)
        # SELECT ... FROM group_info, entity_name WHERE value_domain = 363 AND entity_id = 19
        sql = '\n        SELECT gi.description, gi.visibility, gi.creator_id,\n               gi.create_date, gi.expire_date, en.entity_name\n        FROM [:table schema=cerebrum name=group_info] gi,\n             [:table schema=cerebrum name=entity_name] en\n        WHERE\n          gi.group_id=:g_id AND\n          en.entity_id=gi.group_id AND\n          en.value_domain=:domain'
        args = {'domain': self.CONST['account_names'], 'g_id': self.CONST['bootstrap_group']}
        res = ['', self.CONST['visibility'], self.CONST['bootstrap_user'], '2005-09-30', '', 'bootstrap_group']
        self._add_sql(sql, args, res)

    def _superuser(self, uid=None):
        self._add_supergroup_member(uid)
        
    def _no_superuser(self):
        self._superuser(uid=None)

    def _get_group_member_sql(self):
        return """
            SELECT operation, member_type, member_id 
            FROM [:table schema=cerebrum name=group_member] gm 
            LEFT JOIN [:table schema=cerebrum name=account_info] ai
              ON (gm.member_type = :entity_account AND
                  ai.account_id = gm.member_id)
            LEFT JOIN [:table schema=cerebrum name=group_info] gi
              ON (gm.member_type = :entity_group AND
                  gi.group_id = gm.member_id)
            
            WHERE member_type <> :not_member_type AND (ai.expire_date IS NULL OR
                            ai.expire_date > [:now]) AND
                           (gi.expire_date IS NULL OR
                            gi.expire_date > [:now]) AND  gm.group_id=:g_id""", """
            SELECT operation, member_type, member_id 
            FROM [:table schema=cerebrum name=group_member] gm 
            LEFT JOIN [:table schema=cerebrum name=account_info] ai
              ON (gm.member_type = :entity_account AND
                  ai.account_id = gm.member_id)
            LEFT JOIN [:table schema=cerebrum name=group_info] gi
              ON (gm.member_type = :entity_group AND
                  gi.group_id = gm.member_id)
            
            WHERE member_type=:member_type AND (ai.expire_date IS NULL OR
                            ai.expire_date > [:now]) AND
                           (gi.expire_date IS NULL OR
                            gi.expire_date > [:now]) AND  gm.group_id=:g_id"""

    def _add_group_member(self, gid, uid=None):
        data = dict(self.CONST, gid=gid)
        if not uid:
            r = []
            g = []
            uid = gid
        else:
            r = [[ self.CONST['union'],
                   self.CONST['account'],
                   uid]]
            g = [{ 'group_id': gid,
                   'operation': self.CONST['union'],
                   'member_type': self.CONST['account']}]

        # Look up what operations we are allowed due to group membership.
        sql1, sql2 = self._get_group_member_sql()
        args = """{'g_id': %(bootstrap_group)s, 'not_member_type': %(group)s, 'member_type': None, 'spread': None, 'entity_group': %(group)s, 'group_dom': %(account_names)s, 'entity_account': %(account)s, 'account_dom': %(account_names)s}""" % data
        self._add_sql(sql1, args, res=r)
        
        # Looking up whether there is an intersecting group membership.
        args = """{'g_id': %(gid)s, 'not_member_type': None, 'member_type': %(group)s, 'spread': None, 'entity_group': %(group)s, 'group_dom': %(account_names)s, 'entity_account': %(account)s, 'account_dom': %(account_names)s}""" % data
        self._add_sql(sql2, args, res=[])

        # Look if I'm a member.
        sql = '\n        SELECT group_id, operation, member_type\n        FROM [:table schema=cerebrum name=group_member]\n        WHERE member_id=:member_id'
        args = "{'member_id': %s}" % uid
        self._add_sql(sql, args, res=g)

    def _add_supergroup_member(self, uid=None):
        self._add_group_member(self.CONST['bootstrap_group'], uid)

    def _add_op_role(self, account, op_set=None, target=None):
        assert op_set is not None
        assert target is not None
        r = [[account, hash(op_set), target]]
        sql = """
        SELECT DISTINCT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role]
        WHERE (entity_id IN (%s))""" % account
        args = {'op_set_id': None, 'op_target_id': None}
        self._add_sql(sql, args, res=r)
        
    def _add_opset(self, name, operations):
        mySetId = hash(name)
        # SELECT op_set BY name
        sql = '\n        SELECT op_set_id\n        FROM [:table schema=cerebrum name=auth_operation_set]\n        WHERE name=:name'
        args = {'name': name}
        self._add_sql(sql, args, res=mySetId)
        # SELECT op_set BY id
        sql = '\n        SELECT name, op_set_id\n        FROM [:table schema=cerebrum name=auth_operation_set]\n        WHERE op_set_id=:id'
        args = {'id': mySetId}
        res = [name, mySetId]
        self._add_sql(sql, args, res)
        r = []
        for operation in operations: 
            if type('') == type(operation):
                myOpId = hash(operation)
            else:
                myOpId = int(operation)
                operation = str(operation)
            self._add_op(operation)
            r.append([operation, myOpId, mySetId])
        sql = '\n        SELECT op_code, op_id, op_set_id\n        FROM [:table schema=cerebrum name=auth_operation]\n        WHERE op_set_id=:op_set_id'
        args = {'op_set_id': mySetId}
        self._add_sql(sql, args, res=r)

    def _init_seq(self):
        self._entity_id_seq = 1000

    def nextval(self, seq):
        val = self._entity_id_seq
        self._entity_id_seq = val + 1
        return val

    def _insert_auth_op(self, name):
        if not type(self._entity_id_seq) == type(3):
            self._init_seq()

        sql, args = self._parse_sql("""'\n            INSERT INTO [:table schema=cerebrum name=auth_operation_set]\n            (op_set_id, name) VALUES (:os_id, :name)', {'os_id': %s, 'name': '%s'}""" % (self._entity_id_seq, name))
        self._add_sql(sql, args, [])

    def _delete_auth_op(self, id):
        sql, args = self._parse_sql("""'
        DELETE FROM [:table schema=cerebrum name=auth_operation_set]
        WHERE op_set_id=:os_id', {'os_id': %s}""" % id)
        self._add_sql(sql, args, [])
    
    def close(self):
        pass

    def _add_entity(self, entity_id, entity_type):
        # Spine wants to be able to get all entities and cache this.
        self._entities.append([entity_id, entity_type])

        sql_spine = 'SELECT entity_info.entity_id AS id, entity_info.entity_type AS type FROM entity_info  WHERE entity_info.entity_id = :id'
        args_spine = "{'id': %s}" % entity_id
        res_spine = {'id': entity_id, 'type': entity_type}
        self._add_sql(sql_spine, args_spine, res_spine)

        sql_cerebrum = '\n        SELECT entity_id, entity_type\n        FROM [:table schema=cerebrum name=entity_info]\n        WHERE entity_id=:e_id'
        args_cerebrum = "{'e_id': %s}" % entity_id
        res_cerebrum = [entity_id, entity_type]
        self._add_sql(sql_cerebrum, args_cerebrum, res_cerebrum)

    def _add_entity_type(self, type_id, name, description):
        sql = 'SELECT entity_type_code.code AS id, entity_type_code.code_str AS name, entity_type_code.description AS description FROM entity_type_code  WHERE entity_type_code.code = :id'
        dict = "{'id': %s}" % type_id
        res = {'id': type_id, 'name': name, 'description': description}
        self._add_sql(sql, dict, res)

    def _add_op(self, op):
        res = hash(op)
        self._add_code('auth_op_code', op, None, res)

    def _add_code(self, table, name, desc, res=None):
        sql = 'SELECT code FROM [:table schema=cerebrum name=%s] WHERE code_str=:str' % table
        args = {'int': None, '_desc': desc, 'str': name}
        if not res:
            res = self.CONST[name]
        self._add_sql(sql, args, res)

    def _init_superuser(self):
        self._add_code('entity_type_code', 'account', 'User Account - see table "cerebrum.account_info" and friends.')
        self._add_code('entity_type_code', 'group', 'Group - see table "cerebrum.group_info" and friends.')
        self._add_code('group_membership_op_code', 'union', 'Union')
        self._add_code('group_membership_op_code', 'intersection', 'Intersection')
        self._add_code('group_membership_op_code', 'difference', 'Difference')
        
    def query_1(self, sql, args, fn='query_1'):
        if sql in self._expected_sql.keys():
            expected_args = self._expected_sql[sql]
            if str(args) in expected_args.keys():
                return expected_args[str(args)]
            else:
                raise KeyError, "Unexpected args: %s(%s, %s)" % (fn, sql, args)
        else:
            raise KeyError, "Unexpected call: %s(%s, %s)" % (fn, sql, args)

    def query(self, sql, args=None):
        if sql == """SELECT entity_id, entity_type FROM entity_info""":
            return self._entities
        return self.query_1(sql, args, fn='query')

    def execute(self, sql, args=None):
        return self.query_1(sql, args, fn='execute')

    def _init_accounts(self):
        self._add_code('value_domain_code', 'account_names', 'Default domain for account names')
        self._add_entity_type(self.CONST['account'], name='account', description='none')

        # Spine has a ValueDomainHack that makes it look up the valuedomain when
        # a new Account object is created.
        sql = 'SELECT s0_value_domain_code.code AS s0_id, s0_value_domain_code.code_str AS s0_name, s0_value_domain_code.description AS s0_description FROM value_domain_code s0_value_domain_code WHERE s0_value_domain_code.code_str = :s0name'
        args = {'s0name': 'account_names'}
        res = [[self.CONST['account_names'], 'account_names', '' ]]
        self._add_sql(sql, args, res)

    def _init_groups(self):
        self._add_code('value_domain_code', 'group_names', 'Default domain for group names')
        self._add_entity_type(self.CONST['group'], name='group', description='none')

    def _add_account(self, data):
        self._add_entity(data['id'], data['type'])
        self._add_entity(data['owner'], data['owner_type'])
        self._add_account_info(data)

        sql, args = self._parse_sql("""'SELECT entity_info.entity_id AS id, entity_info.entity_type AS type, account_info.owner_id AS owner, account_info.owner_type AS owner_type, account_info.np_type AS np_type, account_info.create_date AS create_date, account_info.creator_id AS creator, account_info.expire_date AS expire_date, account_info.description AS description, entity_name.entity_name AS name, posix_user.gecos AS gecos, posix_user.posix_uid AS posix_uid, posix_user.gid AS primary_group, posix_user.pg_member_op AS pg_member_op, posix_user.shell AS shell FROM entity_info JOIN account_info account_info ON (entity_info.entity_id = account_info.account_id) JOIN entity_name entity_name ON (entity_info.entity_id = entity_name.entity_id AND entity_name.value_domain = :value_domain) LEFT JOIN posix_user posix_user ON (entity_info.entity_id = posix_user.account_id) WHERE entity_info.entity_id = :id', {'id': %s, 'value_domain': %s}""" % (data['id'], self.CONST['account_names']))
        self._add_sql(sql, args, data)

        sql, args = self._parse_sql("""'SELECT entity_type_code.code AS id, entity_type_code.code_str AS name, entity_type_code.description AS description FROM entity_type_code  WHERE entity_type_code.code = :id', {'id': %s}""" % data['owner_type'])
        res = {'id': data['owner_type'], 'name': 'bogus_name', 'description': 'bogus_description'}
        self._add_sql(sql, args, res)

        if data['owner'] == self.CONST['bootstrap_group']:
                self._add_entity(self.CONST['bootstrap_user'], self.CONST['account'])
        return Account(self, data['id'])

    def _add_person(self, data):
        self._add_entity(data['id'], self.CONST['person'])
        sql, args = self._parse_sql("""'SELECT export_id, birth_date, gender,\n                      deceased_date, description\n               FROM [:table schema=cerebrum name=person_info]\n               WHERE person_id=:p_id', {'p_id': %s})""" % id)
        self._add_sql(sql, args, data)
        return Person(self, data['id'])

    def _add_account_info(self, data):
        # Cerebrum uses many queries when needed to get the account info.
        sql_cerebrum = '\n        SELECT owner_type, owner_id, np_type, create_date,\n               creator_id, expire_date\n        FROM [:table schema=cerebrum name=account_info]\n        WHERE account_id=:a_id'
        data_cerebrum = "{'a_id': %s}" % data['id']
        res_cerebrum = [data['owner_type'], data['owner'], data['np_type'], data['create_date'], data['creator'], '']
        self._add_sql(sql_cerebrum, data_cerebrum, res_cerebrum)

        # Add name of the entity.
        sql_cerebrum = '\n        SELECT entity_name FROM [:table schema=cerebrum name=entity_name]\n        WHERE entity_id=:e_id AND value_domain=:domain'
        data_cerebrum = {'domain': self.CONST['account_names'], 'e_id': data['id']}
        res_cerebrum = ['ta_%s' % id]
        self._add_sql(sql_cerebrum, data_cerebrum, res_cerebrum)

        # Spine fetches all info in one query.
        sql_spine = 'SELECT entity_info.entity_id AS id, entity_info.entity_type AS type, account_info.owner_id AS owner, account_info.owner_type AS owner_type, account_info.np_type AS np_type, account_info.create_date AS create_date, account_info.creator_id AS creator, account_info.expire_date AS expire_date, account_info.description AS description, entity_name.entity_name AS name, posix_user.gecos AS gecos, posix_user.posix_uid AS posix_uid, posix_user.gid AS primary_group, posix_user.pg_member_op AS pg_member_op, posix_user.shell AS shell FROM entity_info JOIN account_info account_info ON (entity_info.entity_id = account_info.account_id) JOIN entity_name entity_name ON (entity_info.entity_id = entity_name.entity_id AND entity_name.value_domain = :value_domain) LEFT JOIN posix_user posix_user ON (entity_info.entity_id = posix_user.account_id) WHERE entity_info.entity_id = :id'
        data_spine = "{'id': %s, 'value_domain': %s}" % (data['id'], self.CONST['account_names'])
        self._add_sql(sql_spine, data_spine, data)

    def _get_op(self, str):
        return AuthRoleOpCode(str)

    def _grant_access_to_entity_via_ou(self, operators, operation, target):
        """The following query is run by BofhdAuth._has_access_to_entity_via_ou"""
        operators = ", ".join([str(op) for op in operators])
        sql = """
        SELECT at.affiliation, aot.attr, ao.op_id, aot.op_target_id
        FROM [:table schema=cerebrum name=account_type] at,
             [:table schema=cerebrum name=auth_op_target] aot,
             [:table schema=cerebrum name=auth_operation] ao,
             [:table schema=cerebrum name=auth_operation_set] aos,
             [:table schema=cerebrum name=auth_role] ar
        WHERE at.account_id=:id AND
              aot.op_target_id=ar.op_target_id AND
              ((aot.target_type=:target_type AND
                at.ou_id=aot.entity_id ) OR
               aot.target_type=:global_target_type) AND
              ar.entity_id IN (%s) AND
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
              """ % operators 
        args = """{'operation_attr': None, 'global_target_type': 'global_ou', 'opcode': %s, 'target_type': 'ou', 'id': %s}""" % (operation, target)
        res = [{'affiliation': 301, 'attr': None, 'op_id': operation, 'op_target_id': target}]
        self._add_sql(sql, args, res)

if __name__ == '__main__':
    main()

# vi:nowrap foldmethod=marker
