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

import pyPgSQL.PgSQL
from Cerebrum.extlib import sets

from Builder import Attribute
from GroBuilder import GroBuilder
from Searchable import Searchable
from Dumpable import Dumpable

class DatabaseAttr(Attribute):
    def __init__(self, name, table, data_type,
                 write=False, from_db=None, to_db=None, optional=False):
        Attribute.__init__(self, name, data_type, write=write)

        self.table = table
        self.optional = optional

        if to_db is not None:
            self.to_db = to_db
        if from_db is not None:
            self.from_db = from_db

    def to_db(self, value):
        if isinstance(value, GroBuilder):
            key = value.get_primary_key()
            assert len(key) == 1
            return key[0]
        else:
            return value

    def from_db(self, value):
        return self.data_type(value)

class DatabaseClass(GroBuilder, Searchable, Dumpable):
    db_attr_aliases = {}
    db_table_order = []

    def _load_db_attributes(self, attributes):
        db = self.get_database()
        
        tables = sets.Set([i.table for i in attributes])

        sql = 'SELECT '
        sql += ', '.join(['%s.%s AS %s' % (attr.table, self._get_real_name(attr), attr.name) for attr in attributes])
        sql += ' FROM '
        sql += ', '.join(tables)
        sql += ' WHERE '

        tmp = []
        for table in tables:
            tmp.append(' AND '.join(['%s.%s = :%s' % (table, self._get_real_name(attr, table), attr.name) for attr in self.primary]))
        sql += ' AND '.join(tmp)

        keys = {}
        for i in self.primary:
            keys[i.name] = i.to_db(getattr(self, '_' + i.name))

        row = db.query_1(sql, keys)
        if len(attributes) == 1:
            row = {attributes[0].name:row}

        for i in attributes:
            value = row[i.name]
            if isinstance(value, pyPgSQL.PgSQL.PgNumeric):
                value = int(value)
            value = i.from_db(value)
            setattr(self, i.get_name_private(), value)

    def _save_all_db(self):
        db = self.get_database()

        for table, attributes in self._get_sql_tables().items():

            # only update tables with changed attributes
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
            sql += ' AND '.join(tmp)

            keys = {}
            for i in self.primary + attributes:
                keys[i.name] = attr.to_db(getattr(self, i.get_name_private()))

            db.execute(sql, keys)

    def _delete(self):
        db = self.get_database()
        table_order = self.db_table_order[:].reverse()

        tables = {}
        for attr in self.primary:
            if not isinstance(attr, DatabaseAttr):
                continue
            if attr.table not in tables:
                tables[attr.table] = {}
            tables[attr.table][self._get_real_name(attr)] = attr.to_db(getattr(self, 'get_'+attr.name)())
        
        for table in (table_order or tables.keys()):
            sql = "DELETE FROM %s WHERE " % table
            tmp = []
            for attr in tables[table].keys():
                tmp.append("%s = :%s" % (attr, attr))
            sql += " AND ".join(tmp)
            db.execute(sql, tables[table])

    def _create(cls, db, *args, **vargs):
        map = cls.map_args(*args, **vargs)
        tables = cls._get_sql_tables()

        for table in (cls.db_table_order or tables.keys()):
            tmp = {}
            for attr in [attr for attr in tables[table] if attr in map.keys()]:
                tmp[cls._get_real_name(attr, table)] = attr.to_db(map[attr])
            sql = "INSERT INTO %s (%s) VALUES (:%s)" % (
                    table, ", ".join(tmp.keys()), ", :".join(tmp.keys()))
            db.execute(sql, tmp)

    _create = classmethod(_create)

    def _get_sql_tables(cls):
        tables = {}
        
        for attr in cls.slots:
            if not isinstance(attr, DatabaseAttr):
                continue
            
            if attr.table not in tables:
                tables[attr.table] = []
            tables[attr.table].append(attr)
            
        return tables

    _get_sql_tables = classmethod(_get_sql_tables)

    def _get_real_name(cls, attr, table=None):
        if table is None:
            table = attr.table
        if table in cls.db_attr_aliases and attr.name in cls.db_attr_aliases[table]:
            return cls.db_attr_aliases[table][attr.name]
        else:
            return attr.name

    _get_real_name = classmethod(_get_real_name)

    def create_search_method(cls):
        def search(self, **vargs): 
            db = self.get_database()
            
            tables = {}
            attributes = {}
            main_attrs = []
            for attr in self.slots:
                if isinstance(attr, DatabaseAttr):
                    if attr.optional and attr.name not in vargs:
                        continue
                    for i in cls.slots:
                        if i.name == attr.name:
                            main_attrs.append(attr)
                    attributes[attr.name] = attr
                    tables[attr.table] = attr.table

            where = []
            if len(tables) > 1:
                # we need to make sure all primary keys are the same
                jee = tables.keys()
                for i in cls.primary:
                    tmp = '%s.%s = %%s.%%s' % (jee[0], cls._get_real_name(i, jee[0]))
                    for table in jee[1:]:
                        where.append(tmp % (table, cls._get_real_name(i, table)))

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
                    value = row['%s' % attr.name]
                    if isinstance(value, pyPgSQL.PgSQL.PgNumeric):
                        value = int(value)
                    tmp[attr.name] = attr.from_db(value)
                objects.append(cls(**tmp))
            
            return objects
        return search
    
    create_search_method = classmethod(create_search_method)
    
    def build_methods(cls):
        optionals = []
        attributes = []
        for i in cls.slots:
            if isinstance(i, DatabaseAttr):
                if i.optional:
                    optionals.append(i)
                else:
                    attributes.append(i)

        for i in optionals + attributes:
            setattr(cls, 'save_' + i.name, cls._save_all_db)

        def load_db_attributes(self):
            self._load_db_attributes(attributes)
        for i in attributes:
            setattr(cls, 'load_' + i.name, load_db_attributes)

        for i in optionals:
            def create(attr):
                def load_db_attribute(self):
                    self._load_db_attributes([attr])
                return load_db_attribute
            setattr(cls, 'load_' + i.name, create(i))

        super(DatabaseClass, cls).build_methods()
        cls.build_search_class()
        cls.build_dumper_class()
 
    build_methods = classmethod(build_methods)

# arch-tag: 82d3bc09-ba4a-46dc-a714-7d78aaf21bde
