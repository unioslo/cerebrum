# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

from Builder import Attribute
from GroBuilder import GroBuilder
from Searchable import Searchable

class DatabaseAttr(Attribute):
    def __init__(self, name, table, data_type, sequence=False, dbattr_name=None,
                 write=False, from_db=None, to_db=None):
        Attribute.__init__(self, name, data_type, sequence=sequence, write=write)

        self.dbattr_name = dbattr_name or name
        self.table = table

        if to_db is not None:
            self.to_db = to_db
        if from_db is not None:
            self.from_db = from_db

        assert type(self.dbattr_name) == str

    def to_db(self, value):
        if isinstance(value, GroBuilder):
            key = value.get_primary_key()
            assert len(key) == 1
            return key[0]
        else:
            return value

    def from_db(self, value):
        if issubclass(self.data_type, GroBuilder):
            return self.data_type(int(value)) # kind of stupid thing to do
        else:
            return self.data_type(value)

class DatabaseClass(GroBuilder, Searchable):
    db_aliases = {}
    db_extra = {}

    def _load_all_db(self):
        db = self.get_database()
        
        tables = []
        attributes = []

        for table, attrs in self._get_sql_tables().items():
            tables.append(table)
            attributes += attrs

        sql = 'SELECT '
        sql += ', '.join(['%s.%s AS %s' % (attr.table, self._get_real_name(attr), attr.name) for attr in attributes])
        sql += ' FROM '
        sql += ', '.join(tables)
        sql += ' WHERE '

        tmp = []
        for table in tables:
            tmp.append(' AND '.join(['%s.%s = :%s' % (table, self._get_real_name(attr, table), attr.name) for attr in self.primary]))
            if table in self.db_extra:
                tmp.append(self.db_extra[table])
        sql += ' AND '.join(tmp)

        keys = {}
        for i in self.primary:
            keys[i.name] = getattr(self, '_' + i.name)

        row = db.query_1(sql, keys)

        for i in attributes:
            value = i.from_db(row[i.name])
            setattr(self, i.get_name_private(), value)

    def _get_sql_tables(self):
        tables = {}

        for attr in self.slots:
            if not isinstance(attr, DatabaseAttr):
                continue

            if attr.table not in tables:
                tables[attr.table] = []

            tables[attr.table].append(attr)

        return tables

    def _save_all_db(self):
        db = self.get_database()

        for table, attributes in self._get_sql_tables().items():
            attributes = [i for i in attributes if i in self.updated]
            if not attributes:
                continue
            sql = 'UPDATE %s SET %s' % (
                table,
                ', '.join(['%s=:%s' % (self._get_real_name(attr), attr.name) for attr in attributes])
            )

            sql += ' WHERE '
            tmp = []
            for attr in self.primary:
                tmp.append('%s.%s = :%s' % (table, self._get_real_name(attr, table), attr.name))
            if table in self.db_extra:
                tmp.append(self.db_extra[table])
            sql += ' AND '.join(tmp)

            keys = {}
            for i in self.primary + attributes:
                keys[i.name] = attr.to_db(getattr(self, i.get_name_private()))

            db.execute(sql, keys)

    def _get_real_name(cls, attr, table=None):
        if table is None:
            table = attr.table
        if table in cls.db_aliases and attr.dbattr_name in cls.db_aliases[table]:
            return cls.db_aliases[table][attr.dbattr_name]
        else:
            return attr.dbattr_name

    _get_real_name = classmethod(_get_real_name)

    def create_search_method(cls):
        def search(self, **vargs): 
            db = self.get_database()
            
            tables = {}
            attributes = {}
            main_attrs = []
            for attr in self.slots:
                if isinstance(attr, DatabaseAttr):
                    for i in cls.slots:
                        if i.name == attr.name:
                            main_attrs.append(attr)
                    attributes[attr.name] = attr
                    tables[attr.table] = attr.table

            where = []
            values = {}
            for key, value in vargs.items():
                if value is None or key not in attributes.keys():
                    continue
                attr = attributes[key]
                real_key = cls._get_real_name(attr)
                if attributes[key].data_type == str:
                    where.append('LOWER(%s.%s) LIKE :%s' % (attr.table, real_key, key))
                    value = value.replace("*","%")
                    value = value.replace("?","_")
                    value = value.lower()
                else:
                    where.append('%s.%s = :%s' % (attr.table, real_key, key))
                    value = attr.to_db(value)
                values[key] = value

            for table in tables.keys():
                if table in cls.db_extra: where.append(self.db_extra[table])
            
            sql = 'SELECT '
            sql += ', '.join(['%s.%s AS %s' % (attr.table, cls._get_real_name(attr), attr.name) for attr in main_attrs])
            sql += ' FROM '
            sql += ', '.join(tables.keys())
            if where:
                sql += ' WHERE '
                sql += ' AND '.join(where)

            objects = []
            for row in db.query(sql, values):
                tmp = {}
                for attr in main_attrs:
                    tmp[attr.name] = attr.from_db(row['%s' % attr.name])
                objects.append(cls(**tmp))
            
            return objects
        return search
    
    create_search_method = classmethod(create_search_method)
    
    def build_methods(cls):
        for i in cls.slots:
            setattr(cls, 'load_' + i.name, cls._load_all_db)
        for i in cls.slots:
            setattr(cls, 'save_' + i.name, cls._save_all_db)

        super(DatabaseClass, cls).build_methods()
 
    build_methods = classmethod(build_methods)

# arch-tag: 82d3bc09-ba4a-46dc-a714-7d78aaf21bde
