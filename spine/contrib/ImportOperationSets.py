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
from Cerebrum.Utils import Factory
from Cerebrum import Constants
from sets import Set
from Cerebrum.spine.SpineLib import Builder
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.bofhd.auth import *

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
        self.old_op_sets = self._get_op_sets()
        self.old_op_roles = self._get_op_roles()

        creator = Factory.get('Account')(self.db)
        creator.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.creator_id = creator.entity_id

        ceresync_group = Factory.get('Group')(self.db)
        try:
            ceresync_group.find_by_name("ceresync")
        except Cerebrum.Errors.NotFoundError:
            ceresync_group.populate(self.creator_id, ceresync_group.const.group_visibility_all,
                           "ceresync")
            ceresync_group.write_db()
        self.ceresync_group_id = ceresync_group.entity_id

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

    def _get_op_sets(self):
        bofhd_os = BofhdAuthOpSet(self.db)
        sets = {}
        self.operations = {}
        for sid, name in bofhd_os.list():
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

    def commit(self):
        self.db.commit()

    def _add_ops_to_set(self, name, operations):
        bofhd_os = BofhdAuthOpSet(self.db)
        try:
            bofhd_os.find_by_name(name)
        except Cerebrum.Errors.NotFoundError:
            bofhd_os.populate(name)
            bofhd_os.write_db()
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

    def _get_op_roles(self):
        bo_roles = BofhdAuthRole(self.db)
        self.roles = []
        entity = Factory.get('Entity')(self.db)
        group = Factory.get('Group')(self.db)
        account = Factory.get('Account')(self.db)
        op_set = BofhdAuthOpSet(self.db)
        op_target = BofhdAuthOpTarget(self.db)

        for eid, oid, tid in bo_roles.list():
            entity.find(eid)
            if entity.entity_type == entity.const.entity_account:
                account.find(eid)
                ename = account.account_name
                etype = 'account'
            elif entity.entity_type == entity.const.entity_group:
                group.find(eid)
                ename = group.group_name
                etype = 'group'
            else:
                print "ERROR: Invalid entity_type %d" % entity.entity_type
                sys.exit(1)
            op_set.find(oid)
            op_target.find(tid)
            self.roles.append((etype, ename, op_set.name,
                (op_target.target_type,
                 op_target.entity_id,
                 op_target.attr)))
            group.clear()
            account.clear()
            entity.clear()
        return self.roles

    def _convert_op_roles(self, roles):
        res = []
        group = Factory.get('Group')(self.db)
        account = Factory.get('Account')(self.db)
        op_set = BofhdAuthOpSet(self.db)
        op_target = BofhdAuthOpTarget(self.db)
        
        for entity_type, entity_name, op_set_name, target in roles:
            try:
                op_set.find_by_name(op_set_name)
            except Cerebrum.Errors.NotFoundError:
                print "WARNING: invalid op_set %s, ignoring" % op_set_name
                continue

            if entity_type=='group':
                entity = group
                try:
                    group.find_by_name(entity_name)
                except Cerebrum.Errors.NotFoundError:
                    # Create empty group
                    group.populate(self.creator_id, group.const.group_visibility_all,
                                   entity_name)
                    group.write_db()
            elif entity_type=='account':
                entity = account
                try:
                    account.find_by_name(entity_name)
                except Cerebrum.Errors.NotFoundError:
                    account.populate(entity_name,
                                     account.const.entity_group,
                                     self.ceresync_group_id,
                                     account.const.account_program,
                                     self.creator_id, None)
                    account.write_db()
            else:
                print "ERROR: Invalid entity_type %s" % entity_type
                sys.exit(1)
            eid = entity.entity_id

            oid = op_set.op_set_id
            ttype, tid, tattr = target
            r = op_target.list(entity_id=tid, target_type=ttype, attr=tattr)
            if not r:
                op_target.populate(tid, ttype, tattr)
                op_target.write_db()
                tid = op_target.op_target_id
                op_target.clear()
            else:
                tid = r[0]['op_target_id']

            res.append((eid, oid, tid))
            account.clear()
            group.clear()
        return res
    
    def _add_op_roles(self, roles):
        role = BofhdAuthRole(self.db)
        for eid, oid, tid in self._convert_op_roles(roles):
            role.grant_auth(eid, oid, tid)
            
    def _remove_op_roles(self, roles):
        role = BofhdAuthRole(self.db)
        for eid, oid, tid in self._convert_op_roles(roles):
            role.revoke_auth(eid, oid, tid)

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

    def update_operation_sets(self):

        # Add and update op_sets in the config file.
        for key, new in self.op_sets.items():
            new = Set(new)
            old = Set(self.old_op_sets.get(key))

            self._add_ops_to_set(key, new - old)
            self._remove_ops_from_set(key, old - new)

    def delete_operation_sets(self):
        # Remove op_sets not in the config file.
        for key in self.old_op_sets.keys():
            if not key in self.op_sets:
                self._remove_op_set(key)

    def update_roles(self):
        old = Set(self.old_op_roles)
        new = Set(self.op_roles)

        self._add_op_roles(new - old)
        self._remove_op_roles(old - new)

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
        importer.update_operation_sets()
        importer.update_roles()
        importer.delete_operation_sets()
        importer.commit()

