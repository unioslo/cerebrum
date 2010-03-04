#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004-2006 University of Oslo, Norway
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

import os
import sys
import cerebrum_path
import cereconf
import Cerebrum.Errors
import types
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.bofhd.auth import *

try:
    set()
except NameError:
    from sets import Set as set

class AuthEntities(object):
    def __init__(self, db):
        self.db = db
        self.cache={}
        self.account=Factory.get('Account')(self.db)
        self.group=Factory.get('Group')(self.db)
        self.host=Factory.get('Host')(self.db)
        self.disk=Factory.get('Disk')(self.db)
        self.ou=Factory.get('OU')(self.db)
        self.co=Factory.get('Constants')()

        creator = Factory.get('Account')(self.db)
        creator.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.creator_id = creator.entity_id

        ceresync_group = Factory.get('Group')(self.db)
        try:
            ceresync_group.find_by_name("ceresync")
        except Cerebrum.Errors.NotFoundError:
            ceresync_group.populate(self.creator_id,
                                    ceresync_group.const.group_visibility_all,
                                    "ceresync")
            ceresync_group.write_db()
        self.ceresync_group_id = ceresync_group.entity_id


    def lookup(self, entity_type, name):
        key=(entity_type, name)
        if type(name) in types.StringTypes:
            if not key in self.cache:
                self.cache[key] = self._lookup(entity_type, name)
            return self.cache[key]
        else:
            return name
        
    def _lookup(self, entity_type, name):
        if entity_type == 'spread':
            return int(self.co.Spread(name))
        if entity_type == 'account':
            self.account.clear()
            self.account.find_by_name(name)
            return self.account.entity_id
        if entity_type == 'group':
            self.group.clear()
            self.group.find_by_name(name)
            return self.group.entity_id
        if entity_type == 'host':
            self.host.clear()
            self.host.find_by_name(name)
            return self.host.entity_id
        if entity_type == 'disk':
            self.disk.clear()
            splname = name.split(":", 1)
            if len(splname) == 1:
                name = splname[0]
                host = None
            else:
                host, name = splname
                host = lookup_entity("host", host)
            self.disk.find_by_path(name, host)
            return self.disk.entity_id
        if entity_type == 'ou':
            self.ou.clear()
            rows = self.ou.search(acronym=name)
            if len(rows) == 1:
                return rows[0]['ou_id']
            elif len(rows) == 0:
                raise Errors.NotFoundError("OU by acronym=%s" % acronym)
            else:
                raise Errors.TooManyRowsError("OU by acronym=%s" % acronym)

class AuthTargets(object):
    def __init__(self, db, auth_entities):
        self.db = db
        self.auth_entities = auth_entities
        self.targets = self.get_targets()
        self.new_targets = set()

    def parse1(self, target_type, target_name=None, attr=None):
        entity_id = self.auth_entities.lookup(target_type, target_name)
        self.new_targets.add((target_type, entity_id, attr))
        
    def get_targets(self):
        targets = {}
        op_target = BofhdAuthOpTarget(self.db)
        for row in op_target.list():
            targets[row['target_type'], row['entity_id'], row['attr']] = \
                row['op_target_id']
        return targets
    
    def _add_targets(self, targets):
        op_target = BofhdAuthOpTarget(self.db)
        for target_type, entity_id, attr in targets:
            op_target.clear()
            op_target.populate(entity_id, target_type, attr)
            op_target.write_db()
            self.targets[target_type, entity_id, attr] = op_target.op_target_id
        
    def _remove_targets(self, targets):
        op_target = BofhdAuthOpTarget(self.db)
        for t in targets:
            op_target.clear()
            op_target.find(self.targets[t])
            op_target.delete()
            
    def add_targets(self):
        old = set(self.targets.keys())
        new = self.new_targets
        self._add_targets(new - old)
        
    def remove_targets(self):
        old = set(self.targets.keys())
        new = self.new_targets
        self._remove_targets(old - new)

    def lookup(self, target_type, target_name=None, attr=None):
        return self.targets[(target_type,
                   self.auth_entities.lookup(target_type, target_name),
                   attr)]

class AuthOpSets(object):
    def __init__(self, db):
        self.db = db
        self.old_op_sets = self._get_op_sets()

    def parse(self, op_sets):
        self.op_sets = op_sets
            
    def _get_op_sets(self):
        bofhd_os = BofhdAuthOpSet(self.db)
        sets = {}
        self.operations = {}
        self.op_set_map = {}
        for sid, name in bofhd_os.list():
            self.op_set_map[name] = sid
            bofhd_os.find(sid)
            for op_code, op_id, set_id in bofhd_os.list_operations():
                attrs = bofhd_os.list_operation_attrs(op_id)
                op_code = str(_AuthRoleOpCode(op_code))
                self.operations['%s:%s' % (name, op_code)] = op_id
                if attrs:
                    for row in attrs:
                        attr = row['attr']
                        sets.setdefault(name, []).append((op_code, attr))
                else:
                    sets.setdefault(name, []).append((op_code, None))
        return sets

    def lookup(self, name):
        return self.op_set_map[name]

    def _add_ops_to_set(self, name, operations):
        bofhd_os = BofhdAuthOpSet(self.db)
        try:
            bofhd_os.find_by_name(name)
        except Cerebrum.Errors.NotFoundError:
            bofhd_os.populate(name)
            bofhd_os.write_db()
            self.op_set_map[name] = bofhd_os.op_set_id
        for operation, attribute in operations:
            try:
                op_code = int(_AuthRoleOpCode(operation))
            except Cerebrum.Errors.NotFoundError, e:
                print """ERROR: Could not find the operation code '%s' in the
database.  This might be because the database is out of date or
because you've made a typo in '%s'.  To update the database,
please run UpdateSpineConstants.py""" % (operation, sys.argv[1])
                sys.exit(1)
            op_id = bofhd_os.add_operation(op_code)
            if attribute:
                bofhd_os.add_op_attrs(op_id, attribute)

    def _remove_ops_from_set(self, name, operations):
        bofhd_os = BofhdAuthOpSet(self.db)
        try:
            bofhd_os.find_by_name(name)
        except Cerebrum.Errors.NotFoundError:
            return 

        for operation, attribute in operations:
            op_code = int(_AuthRoleOpCode(operation))
            op_id = self.operations['%s:%s' % (name, operation)]
            for row in bofhd_os.list_operation_attrs(op_id):
                attr = row['attr']
                bofhd_os.del_op_attrs(op_id, attr)
            bofhd_os.del_operation(op_code, op_id=op_id)
            bofhd_os.write_db()

    def _remove_op_set(self, name):
        op_set = BofhdAuthOpSet(self.db)
        try:
            op_set.find_by_name(name)
        except Cerebrum.Errors.NotFoundError:
            return
        for code, oid, sid in op_set.list_operations():
            for row in op_set.list_operation_attrs(oid):
                attr = row['attr']
                op_set.del_op_attrs(oid, attr)
            op_set.del_operation(code, op_id=oid)

        op_set.delete()
        op_set.write_db()

    def add_operation_sets(self):
        # Add and update op_sets in the config file.
        for key, new in self.op_sets.items():
            new = set(new)
            old = set(self.old_op_sets.get(key))

            self._add_ops_to_set(key, new - old)
            self._remove_ops_from_set(key, old - new)

    def remove_operation_sets(self):
        # Remove op_sets not in the config file.
        for key in self.old_op_sets.keys():
            if not key in self.op_sets:
                self._remove_op_set(key)


class AuthRoles(object):
    def __init__(self, db, auth_entities, auth_targets, auth_op_sets):
        self.db = db
        self.auth_entities = auth_entities
        self.auth_targets = auth_targets
        self.auth_op_sets = auth_op_sets
        self.old_op_roles = self._get_op_roles()

    def _get_op_roles(self):
        bo_roles = BofhdAuthRole(self.db)

        roles = set()
        for row in bo_roles.list():
            roles.add((row['entity_id'], row['op_set_id'], row['op_target_id']))
            
        return roles

    def parse(self, roles):
        self.parse_roles = []
        for entity_type, entity_name, operation_set, target in roles:
            # Parse only targets now,
            # the remainder of the roles can not be looked up until new
            # targets are created.
            self.auth_targets.parse1(*target)
            self.parse_roles.append(((entity_type, entity_name), operation_set, target))

    def parse1(self, entity, operation_set, target):
        roles = set()
        
        entity_id = self.auth_entities.lookup(*entity)
        op_set = self.auth_op_sets.lookup(operation_set)
        target_id = self.auth_targets.lookup(*target)
        return (entity_id, op_set, target_id)

    def post_parse(self):
        self.new_op_roles = set()
        for role in self.parse_roles:
            self.new_op_roles.add(self.parse1(*role))

    def _add_op_roles(self, roles):
        role = BofhdAuthRole(self.db)
        for eid, oid, tid in roles:
            role.grant_auth(eid, oid, tid)
 
    def _remove_op_roles(self, roles):
        role = BofhdAuthRole(self.db)
        for eid, oid, tid in roles:
            role.revoke_auth(eid, oid, tid)

    def update_roles(self):
        self.post_parse()

        old = set(self.old_op_roles)
        new = set(self.new_op_roles)

        self._add_op_roles(new - old)
        self._remove_op_roles(old - new)



class AuthImporter(object):
    def __init__(self, module):
        db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner']
        if db_user is None:
            db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user']
            if db_user is not None:
                print "'table_owner' not set in CEREBRUM_DATABASE_CONNECT_DATA."
                print "Will use regular 'user' (%s) instead." % db_user
                
        self.db = Factory.get('Database')(user=db_user)
        self.db.cl_init(change_program="import_op_sets")

        self.op_sets = module.op_sets
        self.op_roles = module.op_roles

    def main(self):
        auth_entities = AuthEntities(self.db)
        auth_targets = AuthTargets(self.db, auth_entities)

        auth_op_sets = AuthOpSets(self.db)
        auth_op_sets.parse(self.op_sets)
        auth_op_sets.add_operation_sets()

        auth_roles = AuthRoles(self.db, auth_entities, auth_targets, auth_op_sets)
        auth_roles.parse(self.op_roles)

        auth_targets.add_targets()

        auth_roles.post_parse()
        auth_roles.update_roles()

        auth_targets.remove_targets()
        
        auth_op_sets.remove_operation_sets()

    def commit(self):
        self.db.commit()

if __name__ == '__main__':
    try:
        path = os.path.abspath(sys.argv[1])
        file = os.path.basename(path)
        sys.path.append(os.path.dirname(path))
        source = __import__(file[:-3])
    except ImportError, e:
        print e
        print """Please supply a python file containing an op_sets dict and an op_roles list."""
        source = None
    if source:
        importer = AuthImporter(source)
        importer.main()
        importer.commit()

