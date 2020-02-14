# -*- coding: utf-8 -*-
# Copyright 2020 University of Oslo, Norway
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
DB-API 2.0 exceptions.


History
-------
This module was extracted from ``Cerebrum.database`` in order to avoid circular
imports.

The original exceptions was present in ``Cerebrum.database`` in commit:

    commit: f8d149dbb21cdbf10724b60b6d1c613ebc951b5f
    Merge:  3e4c07061 be7c05022
    Date:   Tue Feb 11 11:42:09 2020 +0100
"""
import six


# Tuple holding the names of the standard DB-API exceptions.
#
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
    'Warning',
)


class _CommonExceptionBase(Exception):
    """
    DB-API 2.0 base exception.

    This base exception and the exception classes below will inherit from the
    exception classes in dynamically imported driver modules. This way we can
    catch any kind of db-specific error exceptions by catching
    Cerebrum.database.Error.
    """

    def __str__(self):
        # Call superclass' method to get the error message
        main_message = super(_CommonExceptionBase, self).__str__()

        # Occasionally, we need to know what the offending sql is. This is
        # particularily practical in that case.
        body = [main_message, ]
        for attr in ("operation", "sql", "parameters", "binds",):
            if hasattr(self, attr):
                body.append("%s=%s" % (attr, getattr(self, attr)))
        return "\n".join(body)


class Warning(_CommonExceptionBase):
    """
    Driver-independent DB-API 2.0 Warning exception.

    Exception raised for important warnings like data truncations while
    inserting, etc.
    """
    pass


class Error(_CommonExceptionBase):
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


class DatabaseErrorWrapper(object):
    """
    Exception context wrapper for calls to objects that implements the DB-API.

    The idea is based on the django.db.utils.DatabaseExceptionWrapper. Calls
    performed in this context will handle PEP-249 exceptions, and reraise as
    Cerebrum-specific exceptions.
    """

    def __init__(self, to_module, from_module, **kwargs):
        """
        Initialize wrapper.

        :type to_module: object
        :param to_module:
            Source of the *desired* exception types.

            A PEP-249 compatible database or database module that contains the
            DB-API 2.0 exception types as attributes.

        :type from_module: object
        :param from_module:
            Source of the *expected* exception types.

            A PEP-249 compatible database module. It must contain the
            DB-API 2.0 exception types as attributes.

        :type kwargs: **dict
        :param kwargs:
            Each keyword style argument is added to the exception as an
            attribute. This can be used to piggy-back extra information with
            the exception.
        """
        self.to_module = to_module
        self.from_module = from_module

        # Extra attributes for the exception
        self.extra_attrs = dict((n, repr(v)) for n, v in kwargs.items())

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
            crb_exc_type = getattr(self.to_module, api_exc_name)
            mod_exc_type = getattr(self.from_module, api_exc_name)
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

                six.reraise(crb_exc_type, crb_exc_value, traceback)

        # Miss, some other exception type was raised.
        six.reraise(exc_type, exc_value, traceback)

    def __call__(self, func):
        def inner(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return inner
