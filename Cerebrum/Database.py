# Copyright 2002 University of Oslo, Norway
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

"""

# TODO: Because the connect() factory function takes care of selecting
#       what DB-API driver should be used, the need for hardcoding
#       names of specific database module is reduced -- at least as
#       long as you're only accessing your Cerebrum database.
#
#       However, one might need to collect data from other databases,
#       possibly using a different driver; how could this best be
#       implemented?

import sys
from types import StringType

from Cerebrum import Errors
from Cerebrum import cereconf
from Cerebrum import Utils
from Cerebrum.extlib import db_row


def _add_to_tuple(name, obj):
    mod = Utils.this_module()
    obj_list = list(getattr(mod, name))
    if obj not in obj_list:
        obj_list.append(obj)
        setattr(mod, name, tuple(obj_list))

# Exceptions defined in DB-API 2.0; the module-global tuples below
# will contain the corresponding exceptions from all the driver
# modules that have been loaded.
_EXCEPTION_NAMES = ("Error", "Warning", "InterfaceError", "DatabaseError",
                    "InternalError", "OperationalError", "ProgrammingError",
                    "IntegrityError", "DataError", "NotSupportedError")
for e in _EXCEPTION_NAMES:
    setattr(Utils.this_module(), e, ())

_TYPE_NAMES = ("STRING", "BINARY", "NUMBER", "DATETIME")
for t in _TYPE_NAMES:
    setattr(Utils.this_module(), t, ())


class Cursor(object):
    def __init__(self, csr):
        self._cursor = csr

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 cursor object methods.
    #

    # Use the `property' type (new in Python 2.2) for easy access to
    # the default cursor's attributes.
    def _get_description(self): return self._cursor.description
    description = property(_get_description, None, None,
                           "DB-API 2.0 .read-only attribute 'description'.")
    def _get_rowcount(self): return self._cursor.rowcount
    rowcount = property(_get_rowcount, None, None,
                        "DB-API 2.0 read-only attribute 'rowcount'.")
    def _get_arraysize(self): return self._cursor.arraysize
    def _set_arraysize(self, size): self._cursor.arraysize = size
    arraysize = property(_get_arraysize, _set_arraysize, None,
                         "DB-API 2.0 read-write attribute 'arraysize'.")

    # .callproc() is optional, hence not implemented here.

    # .close() has already been used for the connection-closing
    # method.  A method that closes the default cursor while leaving
    # the connection up is probably not very useful.

    def execute(self, operation, *parameters):
        "Do DB-API 2.0 .execute()."
        #
        # The Python DB-API 2.0 says that the return value of
        # .execute() is 'unspecified'; however, for maximum
        # compatibility with the underlying database module, we return
        # this 'unspecified' value anyway.
        return self._cursor.execute(operation, *parameters)

    def executemany(self, operation, seq_of_parameters):
        "Do DB-API 2.0 .executemany()."
        return self._cursor.executemany(operation, seq_of_parameters)

    def fetchone(self):
        "Do DB-API 2.0 .fetchone()."
        return self._cursor.fetchone()

    def fetchmany(self, size=None):
        "Do DB-API 2.0 .fetchmany()."
        if size is None:
            size = self.arraysize
        return self._cursor.fetchmany(size=size)

    def fetchall(self):
        "Do DB-API 2.0 .fetchall()."
        return self._cursor.fetchall()

    # .nextset() is optional, hence not implemented here.

    def setinputsizes(self, sizes):
        "Do DB-API 2.0 .setinputsizes()."
        return self._cursor.setinputsizes(sizes)

    def setoutputsize(self, size, column=None):
        "Do DB-API 2.0 .setoutputsize()."
        if column is None:
            return self._cursor.setoutputsize(size)
        else:
            return self._cursor.setoutputsize(size, column)

    def query(self, query, *params):
        """Perform an SQL query, and return all rows it yields.

        The result of the query, if any, is returned as a sequence of
        db_row objects.

        """
##         query = query.strip()
##         assert query.lower().startswith("select")
        self.execute(query, params)
        if self.description is None:
            # TBD: This should only occur for operations that do
            # not return rows (e.g. "UPDATE" or "CREATE TABLE");
            # should we raise an exception here?
            return None
        # Retrieve the column names involved in the query.
        fields = [ d[0] for d in self.description ]
        # Make a db_row class that corresponds to this set of
        # column names.
        R = db_row.make_row_class(fields)
        # Return all rows, wrapped up in db_row instances.
        return [ R(row) for row in self.fetchall() ]

    def query_1(self, query, *params):
        """Perform an SQL query that should yield at most one row.

        Like query(), but:

        1. The method can raise the exceptions NotFoundError
           (indicating a query returned no rows) or TooManyRowsError
           (query returned more than one row).

        2. When the query returns a single row, but each returned row
           contains multiple columns, the method will return a single
           row object.

        3. Otherwise (i.e. the query returns a single row with a
           single column) the method will return the value within the
           row object (and not the row object itself).

        """
        res = self.query(query, *params)
        if len(res) == 1:
            if len(res[0]) == 1:
                return res[0][0]
            return res[0]
        elif len(res) == 0:
            raise Errors.NotFoundError
        else:
            raise Errors.TooManyRowsError


class Database(object):
    """Abstract superclass for database driver classes."""

    # Class attribute.
    #
    # Prior to first instantiation, this can be a string specifying
    # the full name of the database module that should be imported.
    #
    # During the first instantiation of a Database subclass, that
    # subclass's attribute is set to the database module object that
    # has been dynamically imported.
    _db_mod = None

    def __init__(self, do_connect=1, *db_params, **db_kws):
        if self.__class__ is Database:
            #
            # The 'Database' class itself is purely virtual; no
            # instantiation is allowed.
            raise NotImplementedError, \
                  "Can't instantiate abstract class <Database>."
        #
        # Figure out the name of the module we need to import.
        mod = self._db_mod or self.__class__.__name__
        if type(mod) == StringType:
            #
            # Do the import of the DB-API 2.0 compliant module.
            self.__class__._db_mod = Utils.dyn_import(mod)
            self._register_driver_exceptions()
            self._register_driver_types()

        self._db = None
        self._cursor = None

        if do_connect:
            #
            # Start a connection
            self.connect(*db_params, **db_kws)

    def _register_driver_exceptions(self):
        'Copy DB-API 2.0 error classes from the appropriate driver module.'
        for name in _EXCEPTION_NAMES:
            exc = getattr(self._db_mod, name)
            setattr(self.__class__, name, exc)
            #
            # Add the freshly imported module's exceptions to the
            # global exception tuples in this module.
            _add_to_tuple(name, exc)

    def _register_driver_types(self):
        'Copy DB-API 2.0 types from the appropriate driver module.'
        for ctor_name in ("Date", "Time", "Timestamp", "DateFromTicks",
                          "TimeFromTicks", "TimestampFromTicks", "Binary"):
            f = getattr(self._db_mod, ctor_name)
            setattr(self.__class__, ctor_name, f)
        for type_name in _TYPE_NAMES:
            type_obj = getattr(self._db_mod, type_name)
            setattr(self.__class__, type_name, type_obj)
            #
            # Add the freshly imported module's type objects to the
            # global type tuples in this module.
            _add_to_tuple(type_name, type_obj)

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 module-level interface.
    #
    def connect(self, *params, **kws):
        "Connect to a database; args are driver-dependent."
        if self._db is None:
            self._db = self._db_mod.connect(*params, **kws)
            #
            # Open a cursor; this can be used by most methods, so that they
            # won't have to open cursors all over the place.
            self._cursor = self.create_cursor()
        else:
            raise Errors.DatabaseConnectionError

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 connection object methods.
    #
    def close(self):
        self._db.close()
        self._db = None

    def commit(self):
        'Perform a commit() on the connection this instance embodies.'
        return self._db.commit()

    def rollback(self):
        'Perform a rollback() on the connection this instance embodies.'
        return self._db.rollback()

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 cursor object methods.
    #

    def _get_description(self): return self._cursor.description
    description = property(_get_description, None, None,
                           "DB-API 2.0 .description for default cursor.")
    def _get_rowcount(self): return self._cursor.rowcount
    rowcount = property(_get_rowcount, None, None,
                        'DB-API 2.0 .rowcount for default cursor.')
    def _get_arraysize(self): return self._cursor.arraysize
    def _set_arraysize(self, size): self._cursor.arraysize = size
    arraysize = property(_get_arraysize, _set_arraysize, None,
                         'DB-API 2.0 .arraysize for default cursor.')

    def execute(self, operation, *parameters):
        "Do DB-API 2.0 .execute() on instance's default cursor."
        return self._cursor.execute(operation, *parameters)

    def executemany(self, operation, seq_of_parameters):
        "Do DB-API 2.0 .executemany() on instance's default cursor."
        return self._cursor.executemany(operation, seq_of_parameters)

    def fetchone(self):
        "Do DB-API 2.0 .fetchone() on instance's default cursor."
        return self._cursor.fetchone()

    def fetchmany(self, size=None):
        "Do DB-API 2.0 .fetchmany() on instance's default cursor."
        return self._cursor.fetchmany(size=(size or self.arraysize))

    def fetchall(self):
        "Do DB-API 2.0 .fetchall() on instance's default cursor."
        return self._cursor.fetchall()

    def setinputsizes(self, sizes):
        "Do DB-API 2.0 .setinputsizes() on instance's default cursor."
        return self._cursor.setinputsizes(sizes)

    def setoutputsize(self, size, column=None):
        "Do DB-API 2.0 .setoutputsize() on instance's default cursor."
        if column is None:
            return self._cursor.setoutputsize(size)
        else:
            return self._cursor.setoutputsize(size, column)

    ####################################################################
    #
    #   Methods that does not directly correspond to anything in the
    #   DB-API 2.0 spec.
    #
    def create_cursor(self):
        "Generate and return a fresh cursor object."
        return Cursor(self._db.cursor())

    def query(self, query, *params):
        """Perform an SQL query, and return all rows it yields.

        The result of the query, if any, is returned as a sequence of
        db_row objects.

        """
        return self._cursor.query(query, *params)

    def query_1(self, query, *params):
        """Perform an SQL query that should yield at most one row.

        Like query(), but:

        1. The method can raise the exceptions NotFoundError
           (indicating a query returned no rows) or TooManyRowsError
           (query returned more than one row).

        2. When the query returns a single row, but each returned row
           contains multiple columns, the method will return a single
           row object.

        3. Otherwise (i.e. the query returns a single row with a
           single column) the method will return the value within the
           row object (and not the row object itself).

        """
        return self._cursor.query_1(query, *params)

    def nextval(self, seq_name):
        """Return a new value from sequence SEQ_NAME.

        The sequence syntax varies a bit between RDBMSes, hence there
        is no default implementation of this method.

        """
        raise NotImplementedError



class PostgreSQL(Database):
    """PostgreSQL driver class."""
    _db_mod = "pyPgSQL.PgSQL"

    def nextval(self, seq_name):
        return self.query_1("SELECT nextval('%s')" % seq_name)



class Oracle(Database):
    """Oracle database driver class."""
    _db_mod = "DCOracle2"

    def connect(self, user=None, password=None, service=None):
        if service is None:
            # TODO: This shouldn't be hardcoded.
            service = 'SYDRUTV.uio.no'
        if user is None:
            # TODO: This shouldn't be hardcoded.
            user = 'cerebrum_user'
        if password is None:
            password = self._read_password(service, user)
        conn_str = '%s/%s@%s' % (user, password, service)
        #
        # Call superclass .connect with appropriate CONNECTIONSTRING;
        # this will in turn invoke the connect() function in the
        # DCOracle2 module.
        super(DCOracle2, self).connect(conn_str)

    def _read_password(self, database, user):
        import os
        filename = os.path.join(cereconf.DB_AUTH_DIR,
                                'passwd-%s@%s' % (user.lower(),
                                                  database.lower()))
        f = file(filename)
        try:
            # .rstrip() removes any trailing newline, if present.
            dbuser, dbpass = f.readline().rstrip().split('\t', 1)
            assert dbuser == user
            return dbpass
        finally:
            f.close()

    def nextval(self, seq_name):
        return self.query_1("SELECT %s.nextval FROM DUAL" % seq_name)



def connect(*args, **kws):
    "Return a new instance of the Database subclass used by this installation."
    db_driver = cereconf.DATABASE_DRIVER
    mod = sys.modules.get(__name__)
    cls = getattr(mod, db_driver)
    return cls(*args, **kws)
