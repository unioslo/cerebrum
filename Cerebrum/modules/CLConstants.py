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

import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor

class _ChangeTypeCode(DatabaseAccessor):
    def __init__(self, category, type):
        self.category = category
        self.type = type
        self.int = None

    def __str__(self):
        return "%s:%s" % (self.category, self.type)

    def __int__(self):
        if self.int is None:
            self.int = int(self.sql.query_1("""
            SELECT change_type_id FROM [:table schema=cerebrum name=change_type]
            WHERE category=:category AND type=:type""", {
                'category': self.category,
                'type': self.type}))
        return self.int

class CLConstants(object):

    """Singleton whose members make up all needed coding values.

    Defines a number of variables that are used to get access to the
    string/int value of the corresponding database key."""

    g_add = _ChangeTypeCode('e_group', 'add')
    g_rem = _ChangeTypeCode('e_group', 'rem')
    g_create = _ChangeTypeCode('e_group', 'create')
    g_destroy = _ChangeTypeCode('e_group', 'destroy')

    a_create =  _ChangeTypeCode('e_account', 'create')
    a_password =  _ChangeTypeCode('e_account', 'password')
    p_def_fg =  _ChangeTypeCode('e_account', 'def_fg')
    p_move =  _ChangeTypeCode('e_account', 'move')

    def map_const(self, num):
        skip = dir(_ChangeTypeCode.sql)
        for x in filter(lambda x: x[0] != '_' and not x in skip, dir(self)):
            v = getattr(self, x)
            if int(v) == num:
                return v
        return None

    def __init__(self, database):
        super(CLConstants, self).__init__(database)

        # TBD: Works, but is icky -- _CerebrumCode or one of its
        # superclasses might use the .sql attribute themselves for
        # other purposes; should be cleaned up.
        _ChangeTypeCode.sql = database

def main():
    from Cerebrum.Utils import Factory
    from Cerebrum import Errors

    Cerebrum = Factory.get('Database')()
    co = CLConstants(Cerebrum)

    skip = dir(Cerebrum)
    skip.append('map_const')
    for x in filter(lambda x: x[0] != '_' and not x in skip, dir(co)):
        try:
            print "co.%s: %s = %d" % (x, getattr(co, x), getattr(co, x))
        except Errors.NotFoundError:
            print "NOT FOUND: co.%s" % x

if __name__ == '__main__':
    main()
