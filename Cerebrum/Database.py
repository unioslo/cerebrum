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

"""Driver-independent API for accessing databases."""

# TBD: Because the connect() factory function takes care of selecting
#      what DB-API driver should be used, the need for hardcoding
#      names of specific database module is reduced -- at least as
#      long as you're only accessing your Cerebrum database.
#
#      However, one might need to collect data from other databases,
#      possibly using a different driver; how could this best be
#      implemented?
#
#      Currently, the function can be told what Database subclass to
#      use in the DB_driver keyword argument.

import sys
from types import DictType, StringType
from cStringIO import StringIO

from Cerebrum import Errors
from Cerebrum import cereconf
from Cerebrum import Utils
from Cerebrum import SqlScanner
from Cerebrum.extlib import db_row


# Exceptions defined in DB-API 2.0; the exception classes below are
# automatically added to the __bases__ attribute of exception classes
# in dynamically imported driver modules.
class Warning(StandardError):
    """Driver-independent base class of DB-API Warning exceptions.

    Exception raised for important warnings like data truncations
    while inserting, etc."""
    pass
class Error(StandardError):
    """Driver-independent base class of DB-API Error exceptions.

    Exception that is the base class of all other error
    exceptions. You can use this to catch all errors with one single
    'except' statement. Warnings are not considered errors and thus
    should not use this class as base."""
    pass
class InterfaceError(Error):
    """Driver-independent base class of DB-API InterfaceError exceptions.
    
    Exception raised for errors that are related to the database
    interface rather than the database itself."""
    pass
class DatabaseError(Error):
    """Driver-independent base class of DB-API DatabaseError exceptions.

    Exception raised for errors that are related to the database."""
    pass
class DataError(DatabaseError):
    """Driver-independent base class of DB-API DataError exceptions.

    Exception raised for errors that are due to problems with the
    processed data like division by zero, numeric value out of range,
    etc."""
    pass
class OperationalError(DatabaseError):
    """Driver-independent base class of DB-API OperationalError exceptions.

    Exception raised for errors that are related to the database's
    operation and not necessarily under the control of the programmer,
    e.g. an unexpected disconnect occurs, the data source name is not
    found, a transaction could not be processed, a memory allocation
    error occurred during processing, etc."""
    pass
class IntegrityError(DatabaseError):
    """Driver-independent base class of DB-API IntegrityError exceptions.

    Exception raised when the relational integrity of the database is
    affected, e.g. a foreign key check fails."""
    pass
class InternalError(DatabaseError):
    """Driver-independent base class of DB-API InternalError exceptions.

    Exception raised when the database encounters an internal error,
    e.g. the cursor is not valid anymore, the transaction is out of
    sync, etc."""
    pass
class ProgrammingError(DatabaseError):
    """Driver-independent base class of DB-API ProgrammingError exceptions.

    Exception raised for programming errors, e.g. table not found or
    already exists, syntax error in the SQL statement, wrong number of
    parameters specified, etc."""
    pass
class NotSupportedError(DatabaseError):
    """Driver-independent base class of DB-API NotSupportedError exceptions.

    Exception raised in case a method or database API was used which
    is not supported by the database, e.g. requesting a .rollback() on
    a connection that does not support transaction or has transactions
    turned off."""
    pass

API_EXCEPTION_NAMES = (
    "Warning", "Error", "InterfaceError", "DatabaseError",
    "DataError", "OperationalError", "IntegrityError",
    "InternalError", "ProgrammingError", "NotSupportedError")
"""Tuple holding the names of the standard DB-API exceptions."""

API_TYPE_NAMES = (
    "STRING", "BINARY", "NUMBER", "DATETIME")
"""Tuple holding the names of the standard types defined by the DB-API."""

API_TYPE_CTOR_NAMES = (
    "Date", "Time", "Timestamp", "DateFromTicks",
    "TimeFromTicks", "TimestampFromTicks", "Binary")
"""Tuple holding the names of the standard DB-API type constructors."""

class Cursor(object):
    """Driver-independent cursor wrapper class.

    Instances are created by calling the .cursor() method of an object
    of the appropriate Database subclass."""
    
    def __init__(self, db):
        self._db = db
        real = db.driver_connection()
        self._cursor = real.cursor()
        # Copy the Database-specific type constructors; these have
        # already been converted into static methods by
        # Database._register_driver_types().
        for ctor in API_TYPE_CTOR_NAMES:
            setattr(self, ctor, getattr(db, ctor))
        for exc_name in API_EXCEPTION_NAMES:
            setattr(self, exc_name, getattr(db, exc_name))

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

    def execute(self, operation, parameters=()):
        """Do DB-API 2.0 .execute()."""
        sql, binds = self._translate(operation, parameters)
        #
        # The Python DB-API 2.0 says that the return value of
        # .execute() is 'unspecified'; however, for maximum
        # compatibility with the underlying database module, we return
        # this 'unspecified' value anyway.
        return self._cursor.execute(sql, *binds)
##        return self._cursor.execute(operation, *parameters)

    def _translate(self, statement, params):
        """Translate SQL and bind params to the driver's dialect."""
        if params:
            #
            # To ease this wrapper's job in converting the bind
            # parameters to the paramstyle required by the driver
            # module, we require `params' to be a mapping (even though
            # the DB-API allows both sequences and mappings).
            assert type(params) == DictType
        out_sql = []
        out_params = self._db.param_converter()
        sql_done = False
        p_item = None
        for token, text in SqlScanner.SqlScanner(StringIO(statement)):
            translation = []
            if sql_done:
                #
                # Token found after end-of-statement indicator; raise
                # an error.  It's the caller's responsibility to feed
                # us one statement at a time.
                raise self.ProgrammingError, \
                      "Token '%s' found after end of SQL statement." % text
            elif p_item is not None:
                #
                # We're in the middle of parsing an SQL portability
                # item; collect all of the item's arguments before
                # trying to translate it into the SQL dialect of this
                # Cursor's database backend.
                if token == SqlScanner.SQL_PORTABILITY_ARG:
                    p_item.append(text)
                    continue
                else:
                    #
                    # We've got all the portability item's arguments;
                    # translate them into a set of SQL tokens.
                    translation.extend(self._db.sql_repr(*p_item))
                    # ... and indicate that we're no longer collecting
                    # arguments for a portability item.
                    p_item = None
            if token == SqlScanner.SQL_END_OF_STATEMENT:
                sql_done = True
            elif token == SqlScanner.SQL_PORTABILITY_FUNCTION:
                #
                # Set `p_item' to indicate that we should start
                # collecting portability item arguments.
                p_item = [text]
            elif token == SqlScanner.SQL_BIND_PARAMETER:
                # The name of the bind variable is the token without
                # any preceding ':'.
                name = text[1:]
                if not params.has_key(name):
                    raise self.ProgrammingError, \
                          "Bind parameter %s has no value." % text
                translation.append(out_params.register(name, params[name]))
            else:
                translation.append(text)
            if translation:
                out_sql.extend(translation)
        return (" ".join(out_sql), out_params.get_data())

    def executemany(self, operation, seq_of_parameters):
        """Do DB-API 2.0 .executemany()."""
        # TBD: Optimize _translate() to avoid having to do the same
        #      "input SQL" -> "backend-specific SQL" translationfor
        #      each set of bind params.
        ret = None
        for p in seq_of_parameters:
            ret = self.execute(operation, p)
            if self.description is not None:
                # The operation created a result set; this constitutes
                # undefined behaviour for .executemany().
                raise self.ProgrammingError, \
                      ".executemany() produced result set."
        return ret
##        return self._cursor.executemany(operation, seq_of_parameters)

    def fetchone(self):
        """Do DB-API 2.0 .fetchone()."""
        return self._cursor.fetchone()

    def fetchmany(self, size=None):
        """Do DB-API 2.0 .fetchmany()."""
        if size is None:
            size = self.arraysize
        return self._cursor.fetchmany(size=size)

    def fetchall(self):
        """Do DB-API 2.0 .fetchall()."""
        return self._cursor.fetchall()

    # .nextset() is optional, hence not implemented here.

    def setinputsizes(self, sizes):
        """Do DB-API 2.0 .setinputsizes()."""
        return self._cursor.setinputsizes(sizes)

    def setoutputsize(self, size, column=None):
        """Do DB-API 2.0 .setoutputsize()."""
        if column is None:
            return self._cursor.setoutputsize(size)
        else:
            return self._cursor.setoutputsize(size, column)

    def driver_cursor(self):
        """Return the driver cursor object underlying this Cursor."""
        return self._cursor

    def __iter__(self):
        """Cursor objects support iteration."""
        return self

    def next(self):
        """Return the next row in the Cursor's result set."""
        row = self.fetchone()
        if row is not None:
            return row
        raise StopIteration
        
    def query(self, query, params=()):
        """Perform an SQL query, and return all rows it yields.

        The result of the query, if any, is returned as a sequence of
        db_row objects."""

##         query = query.strip()
##         assert query.lower().startswith("select")
        self.execute(query, params)
        if self.description is None:
            # TBD: This should only occur for operations that do
            # not return rows (e.g. "UPDATE" or "CREATE TABLE");
            # should we raise an exception here?
            return None
        # Retrieve the column names involved in the query.
        fields = [ d[0].lower() for d in self.description ]
        # Make a db_row class that corresponds to this set of
        # column names.
        R = db_row.make_row_class(fields)
        # Return all rows, wrapped up in db_row instances.
        return [ R(row) for row in self.fetchall() ]

    def query_1(self, query, params=()):
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
           row object (and not the row object itself)."""

        res = self.query(query, params)
        if len(res) == 1:
            if len(res[0]) == 1:
                return res[0][0]
            return res[0]
        elif len(res) == 0:
            raise Errors.NotFoundError
        else:
            raise Errors.TooManyRowsError


#
# Support for conversion from 'named' to the other bind parameter
# styles.
#
class bind_param_converter(object):
    def __init__(self, init_data):
        self._data = init_data

    param_format = ''
    def register(self, name, value):
        raise NotImplementedError

    def get_data(self):
        return [self._data]


class params_as_sequence(bind_param_converter):
    handle_repeat = False
    def __init__(self):
        super(params_as_sequence, self).__init__([])
        if self.handle_repeat:
            self._name2idx = {}

    def register(self, name, value):
        if self.handle_repeat:
            if self._name2idx.has_key(name):
                index = self._name2idx[name]
                assert self._data[index - 1] == value
            else:
                self._data.append(value)
                index = len(self._data)
                self._name2idx[name] = index
        else:
            self._data.append(value)
        return self.param_format % locals()


class paramstyle_qmark(params_as_sequence):
    param_format = '?'


class paramstyle_numeric(params_as_sequence):
    handle_repeat = True
    param_format = ':%(index)d'


class paramstyle_format(params_as_sequence):
    param_format = '%%s'


class params_as_dict(bind_param_converter):
    def __init__(self):
        super(params_as_dict, self).__init__({})

    def register(self, name, value):
        if self._data.has_key(name):
            assert self._data[name] == value
        else:
            self._data[name] = value
        return self.param_format % locals()
        

class paramstyle_named(params_as_dict):
    param_format = ':%(name)s'


class paramstyle_pyformat(params_as_dict):
    param_format = '%%(%(name)s)s'


class Database(object):
    """Abstract superclass for database driver classes."""

    _db_mod = None
    """The name of the DB-API module to use, or a module object.
    
    Prior to first instantiation, this class attribute can be a string
    specifying the full name of the database module that should be
    imported.
    
    During the first instantiation of a Database subclass, that
    subclass's _db_mod attribute is set to the module object of the
    dynamically imported database driver module."""

    param_converter = None
    """The bind parameter converter class used by this driver class."""

    def __init__(self, do_connect=True, *db_params, **db_kws):
        if self.__class__ is Database:
            #
            # The 'Database' class itself is purely virtual; no
            # instantiation is allowed.
            raise NotImplementedError, \
                  "Can't instantiate abstract class <Database>."
        # Figure out if we need to import the driver module.
        mod = self._db_mod or self.__class__.__name__
        if type(mod) == StringType:
            #
            # Yup, need to import; name of driver module is now in
            # `mod'.  All first-time instantiation magic is done in
            # _kickstart().
            self._kickstart(mod)

        self._db = None
        self._cursor = None

        if do_connect:
            # Start a connection
            self.connect(*db_params, **db_kws)

    def _kickstart(self, module_name):
        """Perform necessary magic after importing a new driver module."""
        self_class = self.__class__
        #
        # We're in the process of instantiating this subclass for the
        # first time; we need to import the DB-API 2.0 compliant
        # module.
        self_class._db_mod = Utils.dyn_import(module_name)
        #
        # At the time of importing the driver module, that module's
        # DB-API compliant exceptions are made to inherit from the
        # general-purpose exceptions defined in this module.  This
        # allows us to catch database exceptions in a
        # driver-independent manner.
        for name in API_EXCEPTION_NAMES:
            base = getattr(Utils.this_module(), name)
            exc = getattr(self._db_mod, name)
            if base not in exc.__bases__:
                exc.__bases__ += (base,)
            if hasattr(self_class, name):
##                 print "Skipping copy of exception %s to class %s." % \
##                       (name, self_class.__name__)
                continue
            setattr(self_class, name, exc)
        #
        # The type constructors provided by the driver module should
        # be accessible as (static) methods of the database's
        # connection objects.
        for ctor_name in API_TYPE_CTOR_NAMES:
            if hasattr(self_class, ctor_name):
                #
                # There already is an implementation of this
                # particular ctor in this class, probably for a good
                # reason (e.g. the driver module doesn't supply this
                # type ctor); skip to next ctor.
##                 print "Skipping copy of type ctor %s to class %s." % \
##                       (ctor_name, self_class.__name__)
                continue
            f = getattr(self._db_mod, ctor_name)
            setattr(self_class, ctor_name, staticmethod(f))
        #
        # Likewise we copy the driver-specific type objects to the
        # connection object's class.
        for type_name in API_TYPE_NAMES:
            if hasattr(self_class, type_name):
                # Already present as attribute; skip.
##                 print "Skipping copy of type %s to class %s." % \
##                       (type_name, self_class.__name__)
                continue
            type_obj = getattr(self._db_mod, type_name)
            setattr(self_class, type_name, type_obj)
        #
        # Set up a "bind parameter converter" suitable for the driver
        # module's `paramstyle' constant.
        if self.param_converter is None:
            converter_name = 'paramstyle_%s' % self._db_mod.paramstyle
            cls = getattr(Utils.this_module(), converter_name)
            self_class.param_converter = cls

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 module-level interface.
    #
    def connect(self, *params, **kws):
        """Connect to a database; args are driver-dependent."""
        if self._db is None:
            self._db = self._db_mod.connect(*params, **kws)
            #
            # Open a cursor; this can be used by most methods, so that
            # they won't have to open cursors all over the place.
            self._cursor = self.cursor()
        else:
            # TBD: Should probably use a standard DB-API exception
            # here.
            raise Errors.DatabaseConnectionError

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 connection object methods.
    #
    def close(self):
        """Close the database connection."""
        self._db.close()
        self._db = None

    def commit(self):
        """Perform a commit() on the connection this instance embodies."""
        return self._db.commit()

    def rollback(self):
        """Perform a rollback() on the connection this instance embodies."""
        return self._db.rollback()

    def cursor(self):
        """Generate and return a fresh cursor object."""
        return Cursor(self)

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 cursor object methods.
    #
    #   These methods operate via this object default cursor.
    #
    def _get_description(self): return self._cursor.description
    description = property(_get_description, None, None,
                           "DB-API 2.0 .description for default cursor.")
    def _get_rowcount(self): return self._cursor.rowcount
    rowcount = property(_get_rowcount, None, None,
                        "DB-API 2.0 .rowcount for default cursor.")
    def _get_arraysize(self): return self._cursor.arraysize
    def _set_arraysize(self, size): self._cursor.arraysize = size
    arraysize = property(_get_arraysize, _set_arraysize, None,
                         "DB-API 2.0 .arraysize for default cursor.")

    def execute(self, operation, parameters=()):
        """Do DB-API 2.0 .execute() on instance's default cursor."""
        return self._cursor.execute(operation, parameters)

    def executemany(self, operation, seq_of_parameters):
        """Do DB-API 2.0 .executemany() on instance's default cursor."""
        return self._cursor.executemany(operation, seq_of_parameters)

    def fetchone(self):
        """Do DB-API 2.0 .fetchone() on instance's default cursor."""
        return self._cursor.fetchone()

    def fetchmany(self, size=None):
        """Do DB-API 2.0 .fetchmany() on instance's default cursor."""
        return self._cursor.fetchmany(size=(size or self.arraysize))

    def fetchall(self):
        """Do DB-API 2.0 .fetchall() on instance's default cursor."""
        return self._cursor.fetchall()

    def setinputsizes(self, sizes):
        """Do DB-API 2.0 .setinputsizes() on instance's default cursor."""
        return self._cursor.setinputsizes(sizes)

    def setoutputsize(self, size, column=None):
        """Do DB-API 2.0 .setoutputsize() on instance's default cursor."""
        if column is None:
            return self._cursor.setoutputsize(size)
        else:
            return self._cursor.setoutputsize(size, column)

    ####################################################################
    #
    #   Methods that does not directly correspond to anything in the
    #   DB-API 2.0 spec.
    #
    def driver_connection(self):
        """Return the unwrapped connection object underlying this instance."""
        return self._db

    def query(self, query, params=()):
        """Perform an SQL query, and return all rows it yields.

        The result of the query, if any, is returned as a sequence of
        db_row objects."""

        return self._cursor.query(query, params)

    def query_1(self, query, params=()):
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
           row object (and not the row object itself)."""

        return self._cursor.query_1(query, params)

    def nextval(self, seq_name):
        """Return a new value from sequence SEQ_NAME.

        The sequence syntax varies a bit between RDBMSes, hence there
        is no default implementation of this method."""

        return self.query_1("""
        SELECT [:sequence schema=cerebrum name=%s op=next]
        [:from_dual]""" % seq_name)

    def sql_repr(self, op, *args):
        """Translate SQL portability item to SQL dialect of this driver."""
        method = getattr(self, '_sql_port_%s' % op)
        if not method:
            raise self.ProgrammingError, "Unknown portability op '%s'" % op
        kw_args = {}
        for k, v in [x.split("=", 1) for x in args]:
            if k in kw_args:
                raise self.ProgrammingError, \
                      "Keyword argument '%s' use multiple times in '%s' op." \
                      % (k, op)
            kw_args[k] = v
        return method(**kw_args)


class PostgreSQL(Database):
    """PostgreSQL driver class."""

    _db_mod = "pyPgSQL.PgSQL"

    def connect(self, user=None, password=None, service=None):
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME
        if user is None:
            user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        #if password is None:
        #    password = self._read_password(service, user)
        super(PostgreSQL, self).connect(user = user, password = password,
                                        database = service)

    # According to its documentation, this driver module implements
    # the Binary constructor as a method of the connection object.
    #
    # The reason given for this deviance from the DB-API specification
    # is that in PostgreSQL, Large objects has no meaning outside the
    # context of a connection.
    #
    # However, as it turns out, the connection object of this driver
    # doesn't really have a Binary constructor, either.  Thus, the
    # best we can do is to raise a NotImplementedError. :-(
    def Binary(string): raise NotImplementedError
    Binary = staticmethod(Binary)

    def _sql_port_table(self, schema, name):
        return [name]

    def _sql_port_sequence(self, schema, name, op):
        if op == 'next':
            return ["nextval('%s')" % name]
        elif op == 'current':
            return ["currval('%s')" % name]
        else:
            raise ValueError, 'Invalid sequnce operation: %s' % op

    def _sql_port_from_dual(self):
        return []

    def _sql_port_now(self):
        return ['NOW()']


class Oracle(Database):
    """Oracle database driver class."""

    _db_mod = "DCOracle2"

    def connect(self, user=None, password=None, service=None):
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME
        if user is None:
            user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        if password is None:
            password = self._read_password(service, user)
        conn_str = '%s/%s@%s' % (user, password, service)
        #
        # Call superclass .connect with appropriate CONNECTIONSTRING;
        # this will in turn invoke the connect() function in the
        # DCOracle2 module.
        super(Oracle, self).connect(conn_str)

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

    def _sql_port_table(self, schema, name):
        return ['%(schema)s.%(name)s' % locals()]

    def _sql_port_sequence(self, schema, name, op):
        if op == 'next':
            return ['%(schema)s.%(name)s.nextval' % locals()]
        elif op == 'current':
            return ['%(schema)s.%(name)s.currval' % locals()]
        else:
            raise self.ProgrammingError, 'Invalid sequence operation: %s' % op

    def _sql_port_from_dual(self):
        return ["FROM", "DUAL"]

    def _sql_port_now(self):
        return ['SYSDATE']


def connect(*args, **kws):
    """Return a new instance of this installation's Database subclass."""
    mod = sys.modules.get(__name__)
    db_driver = cereconf.DATABASE_DRIVER
    if kws.has_key('DB_driver'):
        db_driver = kws['DB_driver']
        del kws['DB_driver']
    cls = getattr(mod, db_driver)
    return cls(*args, **kws)

if __name__ == '__main__':
    db = connect(database='cerebrum')
    rows = db.query(
        """SELECT * FROM
          [:table schema=cerebrum name=entity_info] i,
          [:table schema=cerebrum name=entity_type_code] t
        WHERE t.code_str='p'""")
    print "Description:", [x[0] for x in db.description]
    for i in range(len(rows)):
        print i, rows[i]
    print "EOF"
