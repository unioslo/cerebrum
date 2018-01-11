# -*- coding: utf-8 -*-
# Copyright 2018 University of Oslo, Norway
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
Driver-independent API for accessing databases.

This is a DB-API 2.0 (PEP-249) database wrapper, for use with Cerebrum.

    http://legacy.python.org/dev/peps/pep-0249/

Because the connect() factory function takes care of selecting what DB-API
driver should be used, the need for hardcoding names of specific database
module is reduced -- at least as long as you're only accessing your Cerebrum
database.

However, one might need to collect data from other databases, possibly using a
different driver; how could this best be implemented? Currently, the function
can be told what Database subclass to use in the DB_driver keyword argument.
"""

from __future__ import with_statement

import sys

from types import DictType, StringType
from cStringIO import StringIO

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import SqlScanner
from Cerebrum.Utils import NotSet, read_password
from Cerebrum.extlib import db_row

import cereconf


class CommonExceptionBase(Exception):
    """
    DB-API 2.0 base exception.

    This base exception and the exception classes below will inherit from the
    exception classes in dynamically imported driver modules. This way we can
    catch any kind of db-specific error exceptions by catching
    Cerebrum.database.Error.
    """

    def __str__(self):
        # Call superclass' method to get the error message
        main_message = super(CommonExceptionBase, self).__str__()

        # Occasionally, we need to know what the offending sql is. This is
        # particularily practical in that case.
        body = [main_message, ]
        for attr in ("operation", "sql", "parameters", "binds",):
            if hasattr(self, attr):
                body.append("%s=%s" % (attr, getattr(self, attr)))
        return "\n".join(body)


class Warning(CommonExceptionBase):
    """
    Driver-independent DB-API 2.0 Warning exception.

    Exception raised for important warnings like data truncations while
    inserting, etc.
    """
    pass


class Error(CommonExceptionBase):
    """
    Driver-independent DB-API 2.0 Error exception.

    Exception that is the base class of all other error exceptions. You can use
    this to catch all errors with one single 'except' statement.
    Warnings are not considered errors and thus should not use this class as
    base.
    """
    pass


class InterfaceError(Error):
    """
    Driver-independent DB-API 2.0 InterfaceError exception.

    Exception raised for errors that are related to the database interface
    rather than the database itself.
    """
    pass


class DatabaseError(Error):
    """
    Driver-independent DB-API 2.0 DatabaseError exception.

    Exception raised for errors that are related to the database
    """
    pass


class DataError(DatabaseError):
    """
    Driver-independent DB-API 2.0 DataError exception.

    Exception raised for errors that are due to problems with the processed
    data like division by zero, numeric value out of range, etc.
    """
    pass


class OperationalError(DatabaseError):
    """
    Driver-independent DB-API 2.0 OperationalError exception.

    Exception raised for errors that are related to the database's operation
    and not necessarily under the control of the programmer, e.g.:
      - an unexpected disconnect occurs
      - the data source name is not found
      - a transaction could not be processed
      - a memory allocation error occurred during processing
    etc...
    """
    pass


class IntegrityError(DatabaseError):
    """
    Driver-independent DB-API 2.0 IntegrityError exception.

    Exception raised when the relational integrity of the database is affected,
    e.g. a foreign key check fails.
    """
    pass


class InternalError(DatabaseError):
    """
    Driver-independent DB-API 2.0 InternalError exception.

    Exception raised when the database encounters an internal error, e.g. the
    cursor is not valid anymore, the transaction is out of sync, etc.
    """
    pass


class ProgrammingError(DatabaseError):
    """
    Driver-independent DB-API 2.0 ProgrammingError exception.

    Exception raised for programming errors, e.g.:
      - table not found or already exists
      - syntax error in the SQL statement
      - wrong number of parameters specified
    ... etc.
    """
    pass


class NotSupportedError(DatabaseError):
    """
    Driver-independent DB-API 2.0 NotSupportedError exception.

    Exception raised in case a method or database API was used which is not
    supported by the database, e.g. requesting a .rollback() on a connection
    that does not support transaction or has transactions turned off.
    """
    pass


# Note the naming order. No exception name should be a subclass of latter
# exceptions in this list. If this is not true, the DatabaseErrorWrapper will
# re-raise the wrong exception type.
API_EXCEPTION_NAMES = (
    'NotSupportedError',
    'ProgrammingError',
    'InternalError',
    'IntegrityError',
    'OperationalError',
    'DataError',
    'DatabaseError',
    'InterfaceError',
    'Error',
    'Warning')
# Tuple holding the names of the standard DB-API exceptions.

API_TYPE_NAMES = ("STRING", "BINARY", "NUMBER", "DATETIME")
# Tuple holding the names of the standard types defined by the DB-API.

API_TYPE_CTOR_NAMES = (
    "Date",
    "Time",
    "Timestamp",
    "DateFromTicks",
    "TimeFromTicks",
    "TimestampFromTicks",
    "Binary")
# Tuple holding the names of the standard DB-API type constructors.


class DatabaseErrorWrapper(object):
    """
    Exception context wrapper for calls to the database cursor.

    The idea is based on the django.db.utils.DatabaseExceptionWrapper. Calls
    performed in this context will handle PEP-249 exceptions, and reraise as
    Cerebrum-specific exceptions.
    """

    def __init__(self, database, module, **kwargs):
        """
        Initialize wrapper.

        @type database: Cerebrum.database.Database
        @param database: The database wrapper object. This object contains
            monkey patched exceptions as attributes.

        @type module: module
        @param module: A PEP-249 compatible database module. It must contain
            the DB-API 2.0 exception types as attributes.

        @type kwargs: **dict
        @param kwargs: Each keyword style argument is added to the exception as
            an attribute. This can be used to piggy-back extra information with
            the exception.
        """
        self.db = database  # Should we typecheck this?
        self.mod = module   # Can we typecheck this?

        # Extra attributes for the exception
        self.extra_attrs = dict((n, repr(v)) for n, v in kwargs.iteritems())

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Convert exception types of type API_EXCEPTION_NAMES.

        @type exc_type: type or NoneType
        @param exc_type: The raised exception type, or None if no exception was
            raised in the context

        @type exc_value: Exception or NoneType
        @param exc_value: The raised exception, if an exception was raised in
            the context.

        @type traceback: traceback or NoneType
        @param traceback: The exception traceback, if an exception was raised
            in the context.
        """
        if exc_type is None:
            return

        # Identify the exception
        for api_exc_name in API_EXCEPTION_NAMES:
            crb_exc_type = getattr(self.db, api_exc_name)
            mod_exc_type = getattr(self.mod, api_exc_name)
            if issubclass(exc_type, mod_exc_type):
                # Copy arguments and cause
                try:
                    # PY27
                    args = tuple(exc_value.args)
                except AttributeError:
                    # Pre-2.7 value
                    args = (exc_value,)
                crb_exc_value = crb_exc_type(*args)
                crb_exc_value.__cause__ = exc_value

                # Piggy-back extra attributes
                for attr, value in self.extra_attrs.iteritems():
                    setattr(crb_exc_value, attr, value)

                # PY3: Not python 3 compatible,
                #      There are packages (e.g. six) that wraps calls like this
                #      to be PY2 and PY3 compatible.
                raise crb_exc_type, crb_exc_value, traceback
        # Miss, some other exception type was raised.
        raise exc_type, exc_value, traceback

    def __call__(self, func):
        def inner(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return inner


class Lock(object):
    """Driver-independent class for locking. Default: No locking"""
    def __init__(self, mode='exclusive', **kws):
        self.aquire(mode)

    def __enter__(self):
        return self

    def __exit__(self):
        self.release()

    def acquire(self, mode):
        pass

    def release(self):
        pass


class OraPgLock(Lock):
    """Lock for Oracle and Postgres.
    Locks are only released by commit, so no release is actually done.

    Uses the postgres and oracle LOCK TABLE statement.
    """
    lock_stmt = "LOCK TABLE %s IN %s MODE"

    def __init__(self, cursor=None, table=None, **kws):
        """Init will acquire a lock."""
        self.cursor = cursor
        self.table = table
        super(OraPgLock, self).__init__(**kws)

    def acquire(self, mode):
        self.cursor.execute(OraPgLock.lock_stmt % (self.table, mode))

    def acquire_lock(self, table=None, mode='exclusive'):
        """
        Aquire a lock for some table.

        Locking is not a standard sql feature, but some
        providers have locking. If not implemented, locking
        is a no-op.

        :param table: Database table to lock
        :type table: str

        :param mode: locking mode, see database driver
        :type mode: str

        :rtype: Lock
        """
        return Lock(cursor=self, table=table, mode=mode)


class RowIterator(object):
    """
    """
    def __init__(self, cursor):
        self._csr = cursor
        self._queue = []

    def __iter__(self):
        return self

    def next(self):
        if not self._queue:
            self._queue.extend(self._csr.fetchmany())
        if not self._queue:
            raise StopIteration
        row = self._queue.pop(0)
        return self._csr.wrap_row(row)


class Cursor(object):
    """
    Driver-independent cursor wrapper class.

    Instances are created by calling the Database.cursor() method of an object
    of the appropriate Database subclass.
    """

    def __init__(self, db):
        self._db = db
        real = db.driver_connection()
        self._cursor = real.cursor()
        self._sql_cache = Cache.Cache(mixins=[Cache.cache_mru,
                                              Cache.cache_slots],
                                      size=100)
        self._row_class = None
        # Copy the Database-specific type constructors; these have
        # already been converted into static methods by
        # Database._register_driver_types().
        for ctor in API_TYPE_CTOR_NAMES:
            setattr(self, ctor, getattr(db, ctor))
        for exc_name in API_EXCEPTION_NAMES:
            setattr(self, exc_name, getattr(db, exc_name))

    #
    #
    #   Methods corresponding to DB-API 2.0 cursor object methods.
    #

    # Use the `property' type (new in Python 2.2) for easy access to
    # the default cursor's attributes.

    def _get_description(self):
        return self._cursor.description
    description = property(_get_description, None, None,
                           "DB-API 2.0 .read-only attribute 'description'.")

    def _get_rowcount(self):
        return self._cursor.rowcount
    rowcount = property(_get_rowcount, None, None,
                        "DB-API 2.0 read-only attribute 'rowcount'.")

    def _get_arraysize(self):
        return self._cursor.arraysize

    def _set_arraysize(self, size):
        self._cursor.arraysize = size
    arraysize = property(_get_arraysize, _set_arraysize, None,
                         "DB-API 2.0 read-write attribute 'arraysize'.")

    # .callproc() is optional, hence not implemented here.

    def close(self):
        """Do DB-API 2.0 close."""
        return self._cursor.close()

    def execute(self, operation, parameters=()):
        """Do DB-API 2.0 execute."""
        sql, binds = self._translate(operation, parameters)
        #
        # The Python DB-API 2.0 says that the return value of
        # .execute() is 'unspecified'; however, for maximum
        # compatibility with the underlying database module, we return
        # this 'unspecified' value anyway.
        with DatabaseErrorWrapper(self._db, self._db._db_mod,
                                  operation=operation, sql=sql,
                                  parameters=parameters, binds=binds):
            try:
                return self._cursor.execute(sql, binds)
            finally:
                if self.description:
                    # Retrieve the column names involved in the query.
                    fields = [d[0].lower() for d in self.description]
                    # Make a db_row class that corresponds to this set of
                    # column names.
                    self._row_class = db_row.make_row_class(fields)
                else:
                    # Not a row-returning query; clear self._row_class.
                    self._row_class = None

    def _translate(self, statement, params):
        """Translate SQL and bind params to the driver's dialect."""
        if params:
            #
            # To ease this wrapper's job in converting the bind
            # parameters to the paramstyle required by the driver
            # module, we require `params' to be a mapping (even though
            # the DB-API allows both sequences and mappings).
            assert type(params) == DictType

            # None of the database engines understand _CerebrumCode,
            # so we convert them to plain integers to simplify usage.
            from Cerebrum.Constants import _CerebrumCode
            for k in params:
                if isinstance(params[k], _CerebrumCode):
                    params[k] = int(params[k])
        try:
            driver_sql, pconv = self._sql_cache[statement]
            return (driver_sql, pconv(params))
        except KeyError:
            pass
        out_sql = []
        pconv = self._db.param_converter()
        sql_done = False
        p_item = None
        for token, text in SqlScanner.SqlScanner(StringIO(statement)):
            translation = []
            if sql_done:
                #
                # Token found after end-of-statement indicator; raise
                # an error.  It's the caller's responsibility to feed
                # us one statement at a time.
                raise self.ProgrammingError(
                    "Token '%s' found after end of SQL statement." % text)
            elif p_item:
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
                if name not in params:
                    raise self.ProgrammingError(
                        "Bind parameter %s has no value." % text)
                translation.append(pconv.register(name))
            else:
                translation.append(text)
            if translation:
                out_sql.extend(translation)
        #
        # If the input statement ended with a portability item, no
        # non-SQL_PORTABILITY_ARG token has triggered inclusion of the
        # final p_item into out_sql.
        if p_item:
            out_sql.extend(self._db.sql_repr(*p_item))
            p_item = None
        driver_sql = " ".join(out_sql)
        # Cache for later use.
        self._sql_cache[statement] = (driver_sql, pconv)
        return (driver_sql, pconv(params))

    def executemany(self, operation, seq_of_parameters):
        """Do DB-API 2.0 executemany."""
        ret = None
        for p in seq_of_parameters:
            ret = self.execute(operation, p)
            if self.description is not None:
                # The operation created a result set; this constitutes
                # undefined behaviour for .executemany().
                raise self.ProgrammingError(
                    "executemany produced result set.")
        return ret
# return self._cursor.executemany(operation, seq_of_parameters)

    def fetchone(self):
        """Do DB-API 2.0 fetchone."""
        return self._cursor.fetchone()

    def fetchmany(self, size=None):
        """Do DB-API 2.0 fetchmany."""
        if size is None:
            size = self.arraysize
        return self._cursor.fetchmany(size)

    def fetchall(self):
        """Do DB-API 2.0 fetchall."""
        return self._cursor.fetchall()

    # .nextset() is optional, hence not implemented here.

    def setinputsizes(self, sizes):
        """Do DB-API 2.0 setinputsizes."""
        return self._cursor.setinputsizes(sizes)

    def setoutputsize(self, size, column=None):
        """Do DB-API 2.0 setoutputsize."""
        if column is None:
            return self._cursor.setoutputsize(size)
        else:
            return self._cursor.setoutputsize(size, column)

    def driver_cursor(self):
        """Return the driver cursor object underlying this Cursor."""
        return self._cursor

    def __iter__(self):
        """Return iterator over the current query's results."""
        return RowIterator(self)

    def wrap_row(self, row):
        """Return `row' wrapped in a db_row object."""
        return self._row_class(row)

    def query(self, query, params=(), fetchall=True):
        """
        Perform an SQL query, and return all rows it yields.

        If the query produces any result, this can be returned in two
        ways.  In both cases every row is wrapped in a db_row object.

        1. If `fetchall' is true (the default), all rows are
           immediately fetched from the database, and returned as a
           sequence.

        2. If 'fetchall' is false, this method returns an iterator
           object, suitable for e.g. returning one row on demand per
           iteration in a for loop.  This approach can in some cases
           lead to much lower memory consumption.
        """
        if not fetchall:
            # If the cursor to iterate over is used for other queries
            # before the iteration is finished, things won't work.
            # Hence, we generate a fresh cursor to use for this
            # iteration.
            self = self._db.cursor()
        self.execute(query, params)
        if self.description is None:
            # TBD: This should only occur for operations that do
            # not return rows (e.g. "UPDATE" or "CREATE TABLE");
            # should we raise an exception here?
            return None
        if fetchall:
            # Return all rows, wrapped up in db_row instances.
            R = self._row_class
            return [R(row) for row in self.fetchall()]
        else:
            return iter(self)

    def query_1(self, query, params=()):
        """
        Perform an SQL query that should yield at most one row.

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

        res = self.query(query, params)
        if len(res) == 1:
            if len(res[0]) == 1:
                return res[0][0]
            return res[0]
        elif len(res) == 0:
            raise Errors.NotFoundError(repr(params))
        else:
            raise Errors.TooManyRowsError(repr(params))

    def ping(self):
        """
        Check that communication with the database works.

        Do a database-side no-op with the cursor represented by this
        object.  The no-op should result in an exception being raised
        if the cursor is no longer able to communicate with the
        database.

        Caveat: note that a SELECT sent to the database at this point will
        start a new transaction. If autocommit is off, this new transaction
        will remain idle until another query is sent. Be careful about the
        context in which this method is invoked. This concern must be
        addressed in database-specific manner.
        """
        self.execute("""SELECT 1 AS foo [:from_dual]""")
    # end ping

    def acquire_lock(self, table=None, mode='exclusive'):
        """
        acquire a lock for some table.

        Locking is not a standard sql feature, but some
        providers have locking. If not implemented, locking
        is a no-op.

        :param table: Database table to lock
        :type table: str

        :param mode: locking mode, see database driver
        :type mode: str

        :rtype: Lock
        """
        return Lock(cursor=self, table=table, mode=mode)


#
# Support for conversion from 'named' to the other bind parameter
# styles.
#
class convert_param_base(object):
    """Convert bind parameters to appropriate paramstyle."""

    __slots__ = ('map',)
    # To be overridden in subclasses.
    param_format = None

    def __init__(self):
        self.map = []

    def __call__(self, param_dict):
        #
        # DCOracle2 does not treat bind parameters passed as a list
        # the same way it treats params passed as a tuple.  The DB API
        # states that "Parameters may be provided as sequence or
        # mapping", so this can be construed as a bug in DCOracle2.
        return tuple([param_dict[i] for i in self.map])

    def register(self, name):
        return self.param_format % {'name': name}


class convert_param_nonrepeat(convert_param_base):
    __slots__ = ()

    def register(self, name):
        self.map.append(name)
        return super(convert_param_nonrepeat, self).register(name)


class convert_param_qmark(convert_param_nonrepeat):
    __slots__ = ()
    param_format = '?'


class convert_param_format(convert_param_nonrepeat):
    __slots__ = ()
    param_format = '%%s'


class convert_param_numeric(convert_param_base):
    __slots__ = ()

    def register(self, name):
        if name not in self.map:
            self.map.append(name)
        # Construct return value on our own, as it must include a
        # numeric index associated with `name` and not `name` itself.
        return ':' + str(self.map.index(name) + 1)


class convert_param_to_dict(convert_param_base):
    __slots__ = ()

    def __init__(self):
        # Override to avoid creating self.map; that's not needed here.
        pass

    def __call__(self, param_dict):
        # Simply return `param_dict` as is.
        return param_dict


class convert_param_named(convert_param_to_dict):
    __slots__ = ()
    param_format = ':%(name)s'


class convert_param_pyformat(convert_param_to_dict):
    __slots__ = ()
    param_format = '%%(%(name)s)s'


class Database(object):
    """Abstract superclass for database driver classes."""

    _db_mod = None
    # The name of the DB-API module to use, or a module object.

    # Prior to first instantiation, this class attribute can be a string
    # specifying the full name of the database module that should be
    # imported.

    # During the first instantiation of a Database subclass, that
    # subclass's _db_mod attribute is set to the module object of the
    # dynamically imported database driver module.

    param_converter = None
    # The bind parameter converter class used by this driver class.

    encoding = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get(
        'client_encoding') or 'ISO_8859_1'
    # The default character set encoding to use.

    def __init__(self, do_connect=True, *db_params, **db_kws):
        """
        """
        if self.__class__ is Database:
            #
            # The 'Database' class itself is purely virtual; no
            # instantiation is allowed.
            raise NotImplementedError(
                "Can't instantiate abstract class <Database>.")
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

        self._connect_data = {}

        if do_connect:
            # Start a connection
            self.connect(*db_params, **db_kws)

    def _kickstart(self, module_name):
        """
        Perform necessary magic after importing a new driver module.
        """
        self_class = self.__class__

        # We're in the process of instantiating this subclass for the first
        # time; we need to import the DB-API 2.0 compliant module.
        self_class._db_mod = Utils.dyn_import(module_name)

        # Make the API exceptions available
        for name in API_EXCEPTION_NAMES:
            base = getattr(Utils.this_module(), name)
            setattr(self_class, name, base)

        # The type constructors provided by the driver module should
        # be accessible as (static) methods of the database's
        # connection objects.
        for ctor_name in API_TYPE_CTOR_NAMES:
            if hasattr(self_class, ctor_name):
                # There already is an implementation of this
                # particular ctor in this class, probably for a good
                # reason (e.g. the driver module doesn't supply this
                # type ctor); skip to next ctor.
                # print "Skipping copy of type ctor %s to class %s." % \
                    # (ctor_name, self_class.__name__)
                continue
            f = getattr(self._db_mod, ctor_name)
            setattr(self_class, ctor_name, staticmethod(f))

        # Likewise we copy the driver-specific type objects to the
        # connection object's class.
        for type_name in API_TYPE_NAMES:
            if hasattr(self_class, type_name):
                # Already present as attribute; skip.
                # print "Skipping copy of type %s to class %s." % \
                    # (type_name, self_class.__name__)
                continue
            type_obj = getattr(self._db_mod, type_name)
            setattr(self_class, type_name, type_obj)

        # Set up a "bind parameter converter" suitable for the driver
        # module's `paramstyle' constant.
        if self.param_converter is None:
            converter_name = 'convert_param_%s' % self._db_mod.paramstyle
            cls = getattr(Utils.this_module(), converter_name)
            self_class.param_converter = cls

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

    #
    #   Methods corresponding to DB-API 2.0 connection object methods.
    #
    def close(self):
        """
        Close the database connection.
        """
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        self._db.close()
        self._db = None

    def commit(self):
        """
        Perform a commit on the connection this instance embodies.
        """
        return self._db.commit()

    def rollback(self):
        """
        Perform a rollback on the connection this instance embodies.
        """
        return self._db.rollback()

    def cursor(self):
        """
        Generate and return a fresh cursor object.
        """
        return Cursor(self)

    #
    #   Methods corresponding to DB-API 2.0 cursor object methods.
    #
    #   These methods operate via this object default cursor.
    #
    def _get_description(self):
        return self._cursor.description
    description = property(_get_description,
                           None,
                           None,
                           "DB-API 2.0 .description for default cursor.")

    def _get_rowcount(self):
        return self._cursor.rowcount
    rowcount = property(_get_rowcount,
                        None,
                        None,
                        "DB-API 2.0 .rowcount for default cursor.")

    def _get_arraysize(self):
        return self._cursor.arraysize

    def _set_arraysize(self, size):
        self._cursor.arraysize = size
    arraysize = property(_get_arraysize,
                         _set_arraysize,
                         None,
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

    #
    #
    #   Methods that does not directly correspond to anything in the
    #   DB-API 2.0 spec.
    #
    def driver_connection(self):
        """Return the unwrapped connection object underlying this instance."""
        return self._db

    def query(self, *params, **kws):
        """
        Perform an SQL query, and return all rows it yields.

        If the query produces any result, this can be returned in two
        ways.  In both cases every row is wrapped in a db_row object.

        1. If `fetchall' is true (the default), all rows are
           immediately fetched from the database, and returned as a
           sequence.

        2. If 'fetchall' is false, this method returns an iterator
           object, suitable for e.g. returning one row on demand per
           iteration in a for loop.  This approach can in some cases
           lead to much lower memory consumption.
        """
        return self._cursor.query(*params, **kws)

    def query_1(self, query, params=()):
        """
        Perform an SQL query that should yield at most one row.

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
        return self._cursor.query_1(query, params)

    def pythonify_data(self, data):
        """Convert type of values in row to native Python types."""
        if isinstance(data, (list, tuple,
                             # When doing type conversions, db_row
                             # objects are treated as sequences.
                             db_row.abstract_row)):
            tmp = []
            for i in data:
                tmp.append(self.pythonify_data(i))
            # type(data) should not be affected by sequence conversion.
            data = type(data)(tmp)
        elif isinstance(data, dict):
            tmp = {}
            for k in data.keys():
                tmp[k] = self.pythonify_data(data[k])
            # type(data) should not be affected by dict conversion.
            data = type(data)(tmp)
        return data

    def nextval(self, seq_name):
        """
        Return a new value from sequence SEQ_NAME.

        The sequence syntax varies a bit between RDBMSes, hence there
        is no default implementation of this method.
        """
        return self.query_1("""
        SELECT [:sequence schema=cerebrum name=%s op=next]
        [:from_dual]""" % seq_name)

    def currval(self, seq_name):
        """
        """
        return self.query_1("""
        SELECT [:sequence schema=cerebrum name=%s op=curr]
        [:from_dual]""" % seq_name)

    def setval(self, seq_name, val):
        """
        Sets the value of a sequence.

        @type seq_name : string
        @param seq_name: The name of the sequence to update

        @type val: int
        @param val: The integer we want to set

        @rtype: int
        @return: The integer set in the sequence
        """
        return self.query_1("""
        SELECT [:sequence schema=cerebrum name=%s op=set val=%d]""" %
                            (seq_name, int(val)))

    def ping(self):
        """
        Check that communication with the database works.

        Force the underlying database driver module to raise an
        exception if the database communication channel represented by
        this object for some reason isn't working properly.
        """
        c = self.cursor()
        c.ping()
        c.close()

    def sql_repr(self, op, *args):
        """Translate SQL portability item to SQL dialect of this driver."""
        method = getattr(self, '_sql_port_%s' % op, None)
        if not method:
            raise self.ProgrammingError("Unknown portability op '%s'" % op)
        kw_args = {}
        for k, v in [x.split("=", 1) for x in args]:
            if k in kw_args:
                raise self.ProgrammingError(
                    "Keyword argument '%s' use multiple times in '%s' op." % (
                        k,
                        op))
            kw_args[k] = v
        return method(**kw_args)

    def _sql_port_get_config(self, var):
        if not hasattr(cereconf, var):
            raise ValueError
        val = getattr(cereconf, var)
        if type(val) == str:
            return ["'%s'" % val]
        raise ValueError

    def _sql_port_get_constant(self, name):
        Constants = Utils.Factory.get('Constants')(self)
        return ["%d" % int(getattr(Constants, name))]

    def _sql_port_boolean(self, default=None):
        pass

    # FIXME: deprecated, moved to Utils
    def _read_password(self, database, user):
        return read_password(user, database)

    def sql_pattern(self,
                    column,
                    pattern,
                    ref_name=None,
                    case_sensitive=NotSet):
        """
        Convert a pattern with wildcards into a tuple consisting of
        an SQL expression and the value for comparison.

        * If pattern is None, test for NULL.
        * The name of the reference variable defaults to the column
          name (without any table reference), and can be specified
          explicitly using ref_name.
        * case_sensitive can be explicitly True or False.  If unset,
          the search will be case sensitive if the pattern contains
          upper case letters.
        """
        if pattern is None:
            return "%s IS NULL" % column, pattern
        if ref_name is None:
            ref_name = column.split('.')[-1]
        if case_sensitive is NotSet:
            case_sensitive = pattern.lower() != pattern
        if not case_sensitive:
            pattern = pattern.lower()
            column = "LOWER(%s)" % column
        value = pattern.replace("*", "%")
        value = value.replace("?", "_")
        if not case_sensitive or '%' in value or '?' in value:
            operand = "LIKE"
        else:
            operand = "="
        return "%s %s :%s" % (column, operand, ref_name), value


def connect(*args, **kws):
    """Return a new instance of this installation's Database subclass."""
    if 'DB_driver' in kws:
        mod = sys.modules.get(__name__)
        db_driver = kws['DB_driver']
        del kws['DB_driver']
        try:
            cls = getattr(mod, db_driver)  # keep the original behaviour
        except AttributeError:
            from . import postgres, oracle
            for submod in (postgres, oracle):
                if hasattr(submod, db_driver):
                    cls = getattr(submod, db_driver)
                    break
            else:
                raise Errors.DatabaseConnectionError(
                    'Unable to load DB_driver: {db_driver}'.format(
                        db_driver=db_driver))
    else:
        cls = Utils.Factory.get('DBDriver')
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
