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
from Cerebrum import Constants
from Cerebrum.Constants import _CerebrumCode

class _ChangeTypeCode(_CerebrumCode):
    _lookup_code_column = 'change_type_id'
    # _lookup_str_column = 'status_str'
    _lookup_table = '[:table schema=cerebrum name=change_type]'
    # _insert_dependency = _PersonAffiliationCode
    _lookup_desc_column = 'msg_string'
    
    def __init__(self, category, type, msg_string):
        super(_ChangeTypeCode, self).__init__(category)
        self.category = category
        self.type = type
        self.int = None
        self.msg_string = msg_string
        
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

    def insert(self):
        self._pre_insert_check()
        self.sql.execute("""
        INSERT INTO %(code_table)s
          (%(code_col)s, category, type ,%(desc_col)s)
        VALUES
          ( %(code_seq)s, :category, :type, :desc)""" % {
            'code_table': self._lookup_table,
            'code_col': self._lookup_code_column,
            'desc_col': self._lookup_desc_column,
            'code_seq': self._code_sequence},
                         {'category': self.category,
                          'type': self.type,
                          'desc': self.msg_string})
        

class CLConstants(Constants.Constants):

    """Singleton whose members make up all needed coding values.

    Defines a number of variables that are used to get access to the
    string/int value of the corresponding database key."""

    g_add = _ChangeTypeCode('e_group', 'add',
                            'added %(subject)s to %(dest)s')
    g_rem = _ChangeTypeCode('e_group', 'rem',
                            'removed %(subject)s from %(dest)s')
    g_create = _ChangeTypeCode('e_group', 'create',
                               'created %(subject)s')
    g_destroy = _ChangeTypeCode('e_group', 'destroy',
                                'destroyed %(subject)s')

    a_create =  _ChangeTypeCode('e_account', 'create',
                                'created %(subject)s')
    a_password =  _ChangeTypeCode('e_account', 'password',
                                  'new password for %(subject)s')
    p_def_fg =  _ChangeTypeCode('e_account', 'def_fg',
                                'set %(dest)s as default group for %(subject)s')
    p_move =  _ChangeTypeCode('e_account', 'move',
                              '%(subject)s moved to %(param_name)s')
    s_add =  _ChangeTypeCode('spread', 'add',
                             'add spread for %(subject)s')
    s_del =  _ChangeTypeCode('spread', 'delete',
                             'delete spread for %(subject)s')
    
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
