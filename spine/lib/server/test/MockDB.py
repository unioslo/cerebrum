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
import sys, types
sys.path.append("..")
from unittest import TestCase, main
from pmock import *

from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode as AuthRoleOpCode
from Cerebrum.Utils import Factory

Account = Factory.get("Account")
Person = Factory.get("Person")
Entity = Factory.get("Entity")
Group = Factory.get("Group")
OU = Factory.get("OU")

from Cerebrum.spine.SpineLib import Database

class MockDB(Mock):
    """A mock database to allow fast and isolated testing of bofhd.auth modules
    and the authorization layer."""

    CONST = {
        'bootstrap_group': 19,
        'bootstrap_user': 20,
        'difference': 187,
        'intersection': 188,
        'union': 189,
        'account': 147,
        'disk': 148,
        'group': 149, 
        'visibility': 331,
        'host': 150, 
        'ou': 151, 
        'account_names': 363,
        'person': 152,
        'ANSATT': 301,
        'testbruker': 146} 
    
    def __init__(self):
        super(MockDB, self).__init__()
        self.dict = dict(MockDB.CONST) # Make local copy.

    def _getClass(self):
        """Trick isinstance to believe we're a Database"""
        return Database.Database
    __class__ = property(_getClass)

# {{{ Utility functions for generating expects and stubs.

    def _stub(self, string, retval):
        """Convenience function for adding a stub method based on the string
        that pmock prints when an unexpected method is called on the mock
        object."""
        name, sql, dict = self._parse_string(string)
        self.stubs().method(name).with(eq(sql), eq(dict)
                ).will(return_value(retval))

    def _expect_once(self, string, retval):
        """Convenience function for adding a method that shall be called once
        and only once, based on the string that pmock prints when an unexpected
        method is called on the mock object."""
        name, sql, dict = self._parse_string(string)
        self.expects(once()).method(name).with(eq(sql), eq(dict)
                ).will(return_value(retval))

    def _expect_at_least_once(self, string, retval):
        """Convenience function for adding a method that shall be called at
        least once, based on the string that pmock prints when an unexpected
        method is called on the mock object."""
        name, sql, dict = self._parse_string(string)
        self.expects(at_least_once()).method(name).with(eq(sql), eq(dict)
                ).will(return_value(retval))

    def _parse_string(self, string):
        """Parse the string: invoked method('argument1', {'dict': 'arg2'})
        and return the method name, argument1 and the dict."""
        begin = string.find('(')
        name = string[0:begin]
        s = string[begin + 1]
        sql_start = string.find(s) + 1
        sql_end = string.find(s, sql_start)
        sql = string[sql_start:sql_end]
        dict_start = string.find("{", sql_end)
        dict = eval(string[dict_start:-1])
        return name, sql, dict

# }}}

    def _add_op_role(self, account, op_set=None, target=None, method=None):
        if not method: method=self._expect_once
        if account is None:
            r = []
            account = self.userid
        else:
            assert op_set is not None
            assert target is not None
            r = [[account, hash(op_set), target]]
        method("""query('
        SELECT DISTINCT entity_id, op_set_id, op_target_id
        FROM [:table schema=cerebrum name=auth_role]
        WHERE (entity_id IN (%s))', {'op_set_id': None, 'op_target_id': None})""" % account,
          r)
        
    def _add_op(self, op, method=None):
        if not method: method=self._expect_once
        id = hash(op)
        method("""query_1('SELECT code FROM [:table schema=cerebrum name=auth_op_code] WHERE code_str=:str', {'int': None, '_desc': None, 'str': '%s'})""" % op, id)
        return id

    def _add_opset(self, name, method=None):
        if not method: method=self._expect_once
        id = hash(name)
        method("""query_1('\n        SELECT name, op_set_id\n        FROM [:table schema=cerebrum name=auth_operation_set]\n        WHERE op_set_id=:id', {'id': %s})""" % id, [name, id])
        return id

    def _add_opset_byname(self, name, method=None):
        if not method: method=self._expect_once
        id = hash(name)
        method("""query_1('\n        SELECT op_set_id\n        FROM [:table schema=cerebrum name=auth_operation_set]\n        WHERE name=:name', {'name': '%s'})""" % name, id)
        self._add_opset(name, method=method)

    def _add_ops_to_set(self, op_set, ops=[], method=None):
        if not method: method=self._expect_once
        r = []
        for op in ops: 
            r.append([str(op), int(op), hash(op_set)])
        method("""query('\n        SELECT op_code, op_id, op_set_id\n        FROM [:table schema=cerebrum name=auth_operation]\n        WHERE op_set_id=:op_set_id', {'op_set_id': %s})""" % hash(op_set),
                r)

    def _init_bofhdauth(self, value_domain=None, method=None):
        """When BofhdAuth is initialized, it retrieves some information about
        the superuser group.  First it finds out what domain_code it should use.
        Then it looks up the entity_id and then the entity_type of the
        cereconf.BOFHD_SUPERUSER_GROUP.  (The default value is bootstrap_group).
        Finally it looks up some more information about this group.
        """
        if value_domain:
            self.dict['account_names'] = value_domain
        if not method: method=self._expect_at_least_once
        # SELECT code FROM value_domain_code WHERE code_str = 'group_names'
        method("""query_1('SELECT code FROM [:table schema=cerebrum name=value_domain_code] WHERE code_str=:str', {'int': None, '_desc': 'Default domain for group names', 'str': 'group_names'})""", self.dict['account_names'])
        # SELECT entity_id FROM entity_name WHERE value_domain = 363 AND entity_name = 'bootstrap_group'
        method("""query_1('\n        SELECT entity_id\n        FROM [:table schema=cerebrum name=entity_name]\n        WHERE value_domain=:domain AND entity_name=:name', {'domain': %s, 'name': 'bootstrap_group'})""" % self.dict['account_names'], self.dict['bootstrap_group'])
        # SELECT entity_id, entity_type FROM entity_info WHERE entity_id = 19
        method("""query_1('\n        SELECT entity_id, entity_type\n        FROM [:table schema=cerebrum name=entity_info]\n        WHERE entity_id=:e_id', {'e_id': %s})""" % self.dict['bootstrap_group'], [self.dict['bootstrap_group'], self.dict['group']])
        # SELECT ... FROM group_info, entity_name WHERE value_domain = 363 AND entity_id = 19
        method("""query_1('\n        SELECT gi.description, gi.visibility, gi.creator_id,\n               gi.create_date, gi.expire_date, en.entity_name\n        FROM [:table schema=cerebrum name=group_info] gi,\n             [:table schema=cerebrum name=entity_name] en\n        WHERE\n          gi.group_id=:g_id AND\n          en.entity_id=gi.group_id AND\n          en.value_domain=:domain', {'domain': %s, 'g_id': %s})""" % (self.dict['account_names'], self.dict['bootstrap_group']), ['', self.dict['visibility'], self.dict['bootstrap_user'], '2005-09-30', '', 'bootstrap_group'])

    def _init_group(self, name, method=None):
        if not method: method=self._expect_once

    def _add_code(self, table, name, desc, method=None):
        if not method: method=self._expect_once
        method("""query_1('SELECT code FROM [:table schema=cerebrum name=%s] WHERE code_str=:str', {'int': None, '_desc': '%s', 'str': '%s'})""" % (table, desc, name), 
                self.dict[name])

    def _init_account(self, method=None):
        if not method: method=self._expect_at_least_once
        self._add_code('value_domain_code', 'account_names', 'Default domain for account names', method=method)

    def _init_superuser(self, method=None):
        if not method: method=self._expect_at_least_once
        self._init_account(method=method)
        self._add_code('entity_type_code', 'account', 'User Account - see table "cerebrum.account_info" and friends.', method=method)
        self._add_code('entity_type_code', 'group', 'Group - see table "cerebrum.group_info" and friends.', method=method)
        self._add_code('group_membership_op_code', 'union', 'Union', method=method)
        self._add_code('group_membership_op_code', 'intersection', 'Intersection', method=method)
        self._add_code('group_membership_op_code', 'difference', 'Difference', method=method)
        
    def _superuser(self, uid=None, method=None):
        self._init_superuser(method=method)
        self._add_supergroup_member(uid)
        
    def _no_superuser(self, method=None):
        self._superuser(uid=None, method=method)

    def _add_group_member(self, gid, uid=None):
        dict = { 'gid': gid }
        dict.update(self.dict)
        if not uid:
            r = []
            g = []
            uid = gid
        else:
            r = [[ self.dict['union'],
                   self.dict['account'],
                   uid]]
            g = [{ 'group_id': gid,
                   'operation': self.dict['union'],
                   'member_type': self.dict['account']}]
        self._stub("""query('
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
                            gi.expire_date > [:now]) AND  gm.group_id=:g_id', {'g_id': %(bootstrap_group)s, 'not_member_type': %(group)s, 'member_type': None, 'spread': None, 'entity_group': %(group)s, 'group_dom': %(account_names)s, 'entity_account': %(account)s, 'account_dom': %(account_names)s})""" % dict,
                r)
        self._stub("""query('
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
                            gi.expire_date > [:now]) AND  gm.group_id=:g_id', {'g_id': %(gid)s, 'not_member_type': None, 'member_type': %(group)s, 'spread': None, 'entity_group': %(group)s, 'group_dom': %(account_names)s, 'entity_account': %(account)s, 'account_dom': %(account_names)s})""" % dict,
                [])

        self._stub("""query('\n        SELECT group_id, operation, member_type\n        FROM [:table schema=cerebrum name=group_member]\n        WHERE member_id=:member_id', {'member_id': %s})""" % uid,
                g)

    def _add_supergroup_member(self, uid=None):
        self._add_group_member(self.dict['bootstrap_group'], uid)

    def _init_seq(self):
        self._entity_id_seq = 1000

    def nextval(self, seq):
        val = self._entity_id_seq
        self._entity_id_seq = val + 1
        return val

    def _insert_auth_op(self, name, method=None):
        if not method: method=self._expect_once
        if not type(self._entity_id_seq) == type(3):
            self._init_seq()

        method("""execute('
            INSERT INTO [:table schema=cerebrum name=auth_operation_set]
            (op_set_id, name) VALUES (:os_id, :name)', {'os_id': %s, 'name': '%s'})""" % (self._entity_id_seq, name), [])

    def _delete_auth_op(self, id):
        method=self._expect_once
        method("""execute('\n        DELETE FROM [:table schema=cerebrum name=auth_operation_set]\n        WHERE op_set_id=:os_id', {'os_id': %s})""" % id, [])
    
    def close(self):
        pass

    def _get_user(self, userid, ownerid):
        self.userid = userid
        self.ownerid = ownerid
        return self._getAccount(userid, ownerid)

    def _getAccount(self, id, owner=None):
        if not owner:
            owner = self.dict['bootstrap_group']
            owner_type = self.dict['group']
            np_type = self.dict['testbruker']
        elif type(owner) == type(1):
            owner_type = self.dict['person']
            np_type = ''
        create_date = '2006-01-01'

        self._expect_once("""query_1('\n        SELECT entity_id, entity_type\n        FROM [:table schema=cerebrum name=entity_info]\n        WHERE entity_id=:e_id', {'e_id': %s})""" % id,
                [id, self.dict['account']])
        self._expect_once("""query_1('\n        SELECT owner_type, owner_id, np_type, create_date,\n               creator_id, expire_date\n        FROM [:table schema=cerebrum name=account_info]\n        WHERE account_id=:a_id', {'a_id': %s})""" % id,
                [owner_type, owner, np_type, create_date, self.dict['bootstrap_user'], ''])
        self._init_account()
        self._expect_once("""query_1('\n        SELECT entity_name FROM [:table schema=cerebrum name=entity_name]\n        WHERE entity_id=:e_id AND value_domain=:domain', {'domain': %s, 'e_id': %s})""" % (self.dict['account_names'], id),
                ['ta_%s' % id])
        a = Account(self)
        a.find(id)
        return a

    def _getPerson(self, id):
        self._expect_once("""query_1('\n        SELECT entity_id, entity_type\n        FROM [:table schema=cerebrum name=entity_info]\n        WHERE entity_id=:e_id', {'e_id': %s})""" % id,
                [id, self.dict['person']])
        self._expect_once("""query_1('SELECT export_id, birth_date, gender,\n                      deceased_date, description\n               FROM [:table schema=cerebrum name=person_info]\n               WHERE person_id=:p_id', {'p_id': %s})""" % id,
                [0000, '2004-01-01', 'M', '', ''])
        p = Person(self)
        p.find(id)
        return p

    def _get_op(self, str):
        self._add_op(str, method=self._expect_at_least_once)
        op = AuthRoleOpCode(str)
        int(op) # Force lookup.
        return op

    def _grant_access_to_entity_via_ou(self, operators, operation, target):
        """The following query is run by BofhdAuth._has_access_to_entity_via_ou"""
        operators = ", ".join([str(op) for op in operators])
        self._expect_once("""query("
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
              ", {'operation_attr': None, 'global_target_type': 'global_ou', 'opcode': %s, 'target_type': 'ou', 'id': %s})""" % (operators, operation, target),
              [{'affiliation': 301, 'attr': None, 'op_id': operation, 'op_target_id': target}])

if __name__ == '__main__':
    main()

# vi:nowrap foldmethod=marker
