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

# FIXME: Remove PgSQL dependency
import pyPgSQL.PgSQL
import Cerebrum
from Cerebrum.extlib import sets

from Builder import Attribute
from Searchable import Searchable
from Dumpable import Dumpable
from Builder import Builder
from Caching import Caching
from SpineExceptions import DatabaseError, NotFoundError

__all__ = [
    'DatabaseAttr', 'DatabaseClass', 'ConvertableAttribute',
]

class ConvertableAttribute(object):
    """Mixin for attributes which need to be converted.

    This mixin is for attributes which may need to be converted when loaded or
    saved in the database. Attributes which inherit this class should accept
    convert_to and convert_from in their __init__-method, so they can be
    overridden for that specific attribute.
    """
    
    def convert_to(self, value):
        if hasattr(value, 'get_primary_key'):
            key = value.get_primary_key()
            assert len(key) == 1
            return key[0]
        else:
            return value

    def convert_from(self, db, value):
        if value is None:
            return None
        # Depends on the db-driver, should be done in a cleaner way.
        if isinstance(value, pyPgSQL.PgSQL.PgNumeric):
            value = int(value)
        # Inject db-object if data_type is a DatabaseTransactionClass
        if issubclass(self.data_type, DatabaseTransactionClass):
            return self.data_type(db, value)

        return self.data_type(value)

class DatabaseAttr(Attribute, ConvertableAttribute):
    """Object representing an attribute from the database.

    Used to represent an attribute which can be found in the database.
    The value of this attribute will be loaded/saved from/to the
    database.

    You can include your own methods for converting to and from the
    database with the attr 'convert_to' and 'convert_from'.

    Since this attribute has knowledge of the database, you can use it
    with the generic search/create/delete-methods found in DatabaseClass.
    """
    
    def __init__(self, name, table, data_type, exceptions=None, write=False,
                 convert_to=None, convert_from=None, optional=False):

        if exceptions is None:
            exceptions = []
        exceptions += [DatabaseError]

        Attribute.__init__(self, name, data_type, exceptions=exceptions,
                write=write, optional=optional)

        self.table = table

        if convert_to is not None:
            self.convert_to = convert_to
        if convert_from is not None:
            self.convert_from = convert_from

def get_real_name(map, attr, table=None):
    """Finds the real name for attr in map.

    Map should be a dict with dicts in it, where the table is the key in
    the outer dict, and you have DatabaseAttr.name as key in the inner
    dict, the value of the inner dict should be the real name the slot has
    in the database. The map is also used when primary-keys have diffrent
    name in diffrent databases.
    """
    if table is None:
        table = attr.table
    if table in map and attr.name in map[table]:
        return map[table][attr.name]
    else:
        return attr.name

class DatabaseTransactionClass(Builder, Caching):
    def __init__(self, db, *args, **vargs):
        self._database = db
        return super(DatabaseTransactionClass, self).__init__(*args, **vargs)

    def get_database(self):
        return self._database

    def create_primary_key(self, db, *args, **vargs):
        return (db, ) + super(DatabaseTransactionClass, self).create_primary_key(*args, **vargs)
    create_primary_key = classmethod(create_primary_key)

    def get_primary_key(self):
        key = super(DatabaseTransactionClass, self).get_primary_key()
        return key[1:]

class DatabaseClass(DatabaseTransactionClass, Searchable, Dumpable):
    """Mixin class which adds support for the database.

    This class adds support for working directly against the database,
    with generic load/save for attributes, generic create/delete for
    classes, and generic searching.
    
    All SQL-calls in Spine/cerebrum should be implementet here.
    """
    
    db_constants = {}
    db_attr_aliases = {}
    db_table_order = []

    def _get_sql(cls, alias=''):
        if alias:
            alias = '%s_' % alias
        attributes = []
        slots = []
        joins = []
        args = {}

        # We assume every primary key is from the same table
        primary = cls.primary[0].table

        tables = {}

        for attr in cls.slots:
            if not isinstance(attr, DatabaseAttr):
                continue
            optional = tables.get(attr.table, True)
            tables[attr.table] = optional and attr.optional
            real_name = cls._get_real_name(attr)

            # example: alias1_entity_info.entity_id AS alias1__id
            attributes.append('%s%s.%s AS %s%s' % (alias, attr.table, real_name, alias, attr.name))
            slots.append(attr)

        for table, optional in tables.items():
            if table == primary:
                continue
            # example JOIN account_info alias1_account_info ON (alias1_entity_info.entity_id = alias1_account_info.entity_id)
            preds = []
            x = {}
            x['how'] = optional and 'LEFT JOIN' or 'JOIN'
            x['table'] = table
            x['alias'] = alias
            x['primary'] = primary
            for attr in cls.primary:
                x['name1'] = cls._get_real_name(attr)
                x['name2'] = cls._get_real_name(attr, table)
                preds.append('%(alias)s%(primary)s.%(name1)s = %(alias)s%(table)s.%(name2)s' % x)

            # constants
            for name, constant in cls.db_constants.get(table, {}).items():
                x['name'] = name
                preds.append('%(alias)s%(table)s.%(name)s = :%(alias)s%(name)s' % x)
                args['%(alias)s%(name)s' % x] = constant
            x['preds'] = ' AND '.join(preds)

            joins.append('%(how)s %(table)s %(alias)s%(table)s ON (%(preds)s)' % x)

        return slots, attributes, primary, joins, args

    _get_sql = classmethod(_get_sql)
    
    def _load_all_db(self):
        """Load 'attributes' from the database.

        This method load attributes in 'attributes' from the database
        through one SQL call.
        """
        slots, attributes, table, joins, args = self._get_sql()
        primary = []
        for i in self.primary:
            primary.append('%s.%s = :%s' % (i.table, self._get_real_name(i), i.name))
            args[i.name] = i.convert_to(getattr(self, i.get_name_private()))


        sql = 'SELECT %s FROM %s %s WHERE %s' % (', '.join(attributes), table, ' '.join(joins), ' AND '.join(primary))

        db = self.get_database()
        row = db.query_1(sql, args)
        
        if len(attributes) == 1:
            row = {attributes[0].name:row}

        for i in self.slots:
            if i in self.primary:
                continue
            if not isinstance(i, DatabaseAttr):
                continue
            value = row[i.name]
            value = i.convert_from(db, value)
            setattr(self, i.get_name_private(), value)

    def _save_all_db(self):
        """Save all attributes to the database.
        
        This method will save all attributes in this class which have
        been updated, and is a subclass of DatabaseAttr, through one
        SQL-call for each db-table.
        """
        db = self.get_database()
        for table, attributes in self._get_sql_tables().items():
            # only update tables with changed attributes
            changed_attributes = []
            for i in attributes:
                if i not in self.updated:
                    continue
                changed_attributes.append(i)
                self.updated.remove(i)

            if not changed_attributes:
                continue

            changed = []
            for attr in changed_attributes:
                changed.append('%s = :%s' % (self._get_real_name(attr), attr.name))

            keys = []
            for attr in self.primary:
                keys.append('%s.%s = :%s' % (table, self._get_real_name(attr, table), attr.name))

            sql = 'UPDATE %s SET %s WHERE %s' % (table, ', '.join(changed), ' AND '.join(keys))

            args = {}
            for i in self.primary + changed_attributes:
                args[i.name] = attr.convert_to(getattr(self, i.get_name_private()))

            db.execute(sql, args)

    def _delete_from_db(self):
        """Generic method for deleting this instance from the database.
        
        Creates the SQL query and executes it to remove the rows in the
        database which this instance fills. The reverse of db_table_order
        is used if set, and primary slots is used to create the where clause.
        """
        db = self.get_database()
        table_order = self.db_table_order[:]
        table_order.reverse()

        # Prepare primary keys for each table to delete from
        tables = {}
        for attr in self.primary:
            if not isinstance(attr, DatabaseAttr):
                continue
            if attr.table not in tables:
                tables[attr.table] = {}
            value = attr.convert_to(getattr(self, attr.get_name_get())())
            tables[attr.table][self._get_real_name(attr)] = value
        
        # If db_table_order is set, we delete in the opposite order.
        for table in (table_order or tables.keys()):
            sql = "DELETE FROM %s WHERE " % table
            sql += " AND ".join(['%s = :%s' % (a, a) for a in tables[table].keys()])
            db.execute(sql, tables[table])

    def _create(cls, db, *args, **vargs):
        """Generic method for creating instances in the database.
        
        Creates the SQL query and executes it to create instances of the
        class 'cls' in the database. This method is "private" because you
        need to supply the primary key for the new instance. You should
        also check that enough arguments are given to create a new
        instance.

        Example of "public" create method:
        def create_example(self, example):
            db = self.get_database()
            id = int(db.nextval('example'))
            Example._create(db, id, example)
            return Example(id, write_locker=self.get_writelock_holder())

        Notice the write_locker argument when returning the new object.
        """
        db = self.get_database()
        map = cls.map_args(*args, **vargs)
        tables = cls._get_sql_tables()

        for table in (cls.db_table_order or tables.keys()):
            tmp = {}
            for attr in [attr for attr in tables[table] if attr in map.keys()]:
                tmp[cls._get_real_name(attr, table)] = attr.convert_to(map[attr])
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

    def _get_real_name(cls, *args, **vargs):
        return get_real_name(cls.db_attr_aliases, *args, **vargs)

    _get_real_name = classmethod(_get_real_name)

    def create_search_method(cls):
        """Generic method for searching for instances of class 'cls'.

        Used when creating a searchclass for class 'cls', to add a method
        which searches for instances of the class.
        """
        def search(self, *args, **vargs):
            """Search for instances of the original class.

            Creates SQL query for finding instances of the original class
            which matches arguments given in args and vargs.
            Returns a list of objects returned from the SQL query.
            
            If the DatabaseAttr has the attribute 'like', string comparison
            is used and wildcards are supported in the where clause. 'less'
            and 'more' gives '<' and '>' in the where clause.
            """
            pass
        return search
    
    create_search_method = classmethod(create_search_method)
    
    def build_methods(cls):
        """Create get/set methods for slots."""
        for attr in cls.slots:
            if not isinstance(attr, DatabaseAttr):
                continue

            if not hasattr(cls, attr.get_name_load()):
                setattr(cls, attr.get_name_load(), cls._load_all_db)

            if attr.write and not hasattr(cls, attr.get_name_save()):
                setattr(cls, attr.get_name_save(), cls._save_all_db)

        super(DatabaseClass, cls).build_methods()
        cls.build_search_class()
        cls.build_dumper_class()
 
    build_methods = classmethod(build_methods)

# arch-tag: 9e06972b-c3b1-45ff-bdad-e32d35d3ab81
