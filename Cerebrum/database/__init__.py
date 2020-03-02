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
from __future__ import with_statement, print_function

import logging
import sys

from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Utils import NotSet, read_password
from Cerebrum.extlib import db_row

from . import errors
from .errors import (  # noqa: F401
    # the DB-API errors should be available as Cerebrum.database.<name>
    Warning,
    Error,
    InterfaceError,
    DatabaseError,
    DataError,
    OperationalError,
    IntegrityError,
    InternalError,
    ProgrammingError,
    NotSupportedError,
)
from . import macros
from . import paramstyles
from . import translate

import cereconf

logger = logging.getLogger(__name__)


# Tuple holding the names of the standard types defined by the DB-API.
API_TYPE_NAMES = ("STRING", "BINARY", "NUMBER", "DATETIME")

# Tuple holding the names of the standard DB-API type constructors.
API_TYPE_CTOR_NAMES = (
    "Date",
    "Time",
    "Timestamp",
    "DateFromTicks",
    "TimeFromTicks",
    "TimestampFromTicks",
    "Binary")


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


def _pretty_sql(sql, maxlen=None):
    pretty_sql = ' '.join(l.strip() for l in sql.split('\n')).strip()
    if maxlen:
        pretty_sql = pretty_sql[:maxlen] + ('...' if pretty_sql[maxlen:]
                                            else '')
    return pretty_sql


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
        for exc_name in errors.API_EXCEPTION_NAMES:
            setattr(self, exc_name, getattr(db, exc_name))

    @property
    def _translate(self):
        if not hasattr(self, '_translate_func'):
            self._translate_func = translate.Translator(self._db, cereconf)
        return self._translate_func

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
        try:
            sql, binds = self._translate(operation, parameters)
        except Exception as e:
            err = errors.ProgrammingError("Unable to translate: reason=%r" %
                                          repr(e))
            err.operation = operation
            err.parameters = parameters
            raise err

        # logger.debug('cursor execute: %r', _pretty_sql(sql, 400))

        # The Python DB-API 2.0 says that the return value of
        # .execute() is 'unspecified'; however, for maximum
        # compatibility with the underlying database module, we return
        # this 'unspecified' value anyway.
        with errors.DatabaseErrorWrapper(
                self._db,
                self._db._db_mod,
                operation=operation,
                sql=sql,
                parameters=parameters,
                binds=binds):
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


def kickstart(module):
    """ Copy DBAPI 2.0 items from `module` to the decorated class.

    :param Module module:
        A DBAPI 2.0 (PEP-249) compatible database module.

    :return callable:
        Returns a class decorator that copies relevant db-api from the module
        to the decorated class.
    """
    def wrapper(cls):

        # Make the API exceptions available
        for name in errors.API_EXCEPTION_NAMES:
            base = getattr(Utils.this_module(), name)
            setattr(cls, name, base)

        # The type constructors provided by the driver module should
        # be accessible as (static) methods of the database's
        # connection objects.
        for ctor_name in API_TYPE_CTOR_NAMES:
            if hasattr(cls, ctor_name):
                # There already is an implementation of this
                # particular ctor in this class, probably for a good
                # reason (e.g. the driver module doesn't supply this
                # type ctor); skip to next ctor.
                continue
            f = getattr(module, ctor_name)
            setattr(cls, ctor_name, staticmethod(f))

        # Likewise we copy the driver-specific type objects to the
        # connection object's class.
        for type_name in API_TYPE_NAMES:
            if hasattr(cls, type_name):
                # Already present as attribute; skip.
                continue
            type_obj = getattr(module, type_name)
            setattr(cls, type_name, type_obj)

        # make the real db module available as db-mod
        cls._db_mod = module

        return cls
    return wrapper


class Database(object):
    """Abstract superclass for database driver classes."""

    # The name of the DB-API module to use, or a module object.
    #
    # Prior to first instantiation, this class attribute can be a string
    # specifying the full name of the database module that should be
    # imported.
    #
    # During the first instantiation of a Database subclass, that
    # subclass's _db_mod attribute is set to the module object of the
    # dynamically imported database driver module.
    _db_mod = None

    # A table of macros to use by the database dialect
    macro_table = macros.common_macros

    encoding = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get(
        'client_encoding') or 'UTF-8'
    # The default character set encoding to use.

    def __init__(self, do_connect=True, *db_params, **db_kws):
        if self.__class__ is Database:
            raise NotImplementedError(
                "Can't instantiate abstract class <Database>.")

        self._db = None
        self._cursor = None

        self._connect_data = {}

        if do_connect:
            # Start a connection
            self.connect(*db_params, **db_kws)

    @property
    def paramstyle(self):
        return self._db_mod.paramstyle

    @property
    def dialect(self):
        if not hasattr(self, '_dialect'):
            param_cls = paramstyles.get_converter(self.paramstyle)
            self._dialect = translate.Dialect(self.macro_table, param_cls)
        return self._dialect

    #
    #   Methods corresponding to DB-API 2.0 module-level interface.
    #
    def connect(self, *params, **kws):
        """Connect to a database; args are driver-dependent."""

        if self._db is None:
            with errors.DatabaseErrorWrapper(type(self), self._db_mod):
                self._db = self._db_mod.connect(*params, **kws)
                #
                # Open a cursor; this can be used by most methods, so that
                # they won't have to open cursors all over the place.
                self._cursor = self.cursor()
        else:
            # TBD: Should probably use a standard DB-API exception
            # here.
            raise DatabaseError('DB connection already open')

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
                raise DatabaseError(
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
    print("Description:", [x[0] for x in db.description])
    for i in range(len(rows)):
        print(i, rows[i])
    print("EOF")
