# -*- coding: utf-8 -*-
#
# Copyright 2003, 2004, 2019 University of Oslo, Norway
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
"""
Uit specific extension to access a simple role source system

We need something now!
Refine later....

"""

import cereconf
from Cerebrum.database import Database


class SystemY(object):

    def __init__(self, db=None, user=None, database=None, host=None):
        if db is None:
            user = user or cereconf.SYSY_USER
            database = database or cereconf.SYSY_DATABASE_NAME
            db = Database.connect(user=user, service=database,
                                  host=host, DB_driver='PsycoPG2')
        self.db = db

    def list_role_types(self):
        pass

    def list_role_members(self, rolename):
        pass

    def _rolefilter(self, rolename):

        excluded_roles = ['administrator']
        if rolename in excluded_roles:
            return True
        if rolename.endswith('_admin'):
            return True

        return False

    def list_roles(self, ):

        items = []

        sql = """
        SELECT  u.uname,gg.gname
        FROM grp_group gg
             JOIN grp_member gm ON gm.gid=gg.gid
             JOIN users u on gm.uid=u.uid
        """
        for r in self.db.query(sql):
            if not self._rolefilter(r['gname']):
                items.append({'uname': r['uname'], 'gname': r['gname']})
        return items
