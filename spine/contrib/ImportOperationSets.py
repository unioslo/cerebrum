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
        self.op_sets = module.op_sets
        self.op_roles = module.op_roles


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
            op_code = int(_AuthRoleOpCode(operation))
            op_id = bofhd_os.add_operation(op_code)
            if attribute:
                bofhd_os.add_op_attrs(op_id, attribute)
            self.commit()

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
            bofhd_os.del_operation(op_code)
            bofhd_os.write_db()

    def _get_op_roles(self):
        bo_roles = BofhdAuthRole(self.db)
        self.roles = []
        group = Factory.get('Group')(self.db)
        op_set = BofhdAuthOpSet(self.db)
        op_target = BofhdAuthOpTarget(self.db)

        for eid, oid, tid in bo_roles.list():
            group.find(eid)
            op_set.find(oid)
            op_target.find(tid)
            self.roles.append((group.group_name, op_set.name,
                (op_target.target_type,
                 op_target.entity_id,
                 op_target.attr)))
            group.clear()
        return self.roles

    def _convert_op_roles(self, roles):
        res = []
        group = Factory.get('Group')(self.db)
        op_set = BofhdAuthOpSet(self.db)
        op_target = BofhdAuthOpTarget(self.db)

        for group_name, op_set_name, target in roles:
            try:
                op_set.find_by_name(op_set_name)
            except Cerebrum.Errors.NotFoundError:
                continue

            group.find_by_name(group_name)
            gid = group.entity_id

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

            res.append((gid, oid, tid))
            group.clear()
        return res
    
    def _add_op_roles(self, roles):
        role = BofhdAuthRole(self.db)
        for gid, oid, tid in self._convert_op_roles(roles):
            role.grant_auth(gid, oid, tid)
            
    def _remove_op_roles(self, roles):
        role = BofhdAuthRole(self.db)
        for gid, oid, tid in self._convert_op_roles(roles):
            role.revoke_auth(gid, oid, tid)

    def _remove_op_set(self, name):
        op_set = BofhdAuthOpSet(self.db)
        try:
            op_set.find_by_name(name)
        except Cerebrum.Errors.NotFoundError:
            return
        for code, oid, sid in op_set.list_operations():
            op_set.del_operation(code)

        op_set.delete()
        op_set.write_db()

    def update_operation_sets(self):
        existing = self._get_op_sets()

        # Add and update op_sets in the config file.
        for key, new in self.op_sets.items():
            new = Set(new)
            old = Set(existing.get(key))

            self._add_ops_to_set(key, new - old)
            self._remove_ops_from_set(key, old - new)

        # Remove op_sets not in the config file.
        for key in existing.keys():
            if not key in self.op_sets:
                self._remove_op_set(key)

    def update_roles(self):
        old = Set(self._get_op_roles())
        new = Set(self.op_roles)

        self._add_op_roles(new - old)
        #self._remove_op_roles(old - new)

if __name__ == '__main__':
    try:
        path = os.path.abspath(sys.argv[1])
        file = os.path.basename(path)
        sys.path.append(os.path.dirname(path))
        source = __import__(file[:-3])
    except Exception, e:
        print e
        print """Please supply a python file containing an op_sets dict and an op_roles list."""
        source = None
    if source:
        importer = AuthImporter(source)
        importer.update_operation_sets()
        importer.update_roles()
        importer.commit()

