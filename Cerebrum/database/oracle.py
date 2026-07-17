# -*- coding: utf-8 -*-
#
# Copyright 2018-2025 University of Oslo, Norway
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
Oracle DB functionality for the people
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import codecs
import datetime
import os

import cx_Oracle as cx_oracle_module  # noqa: N813
import six

from Cerebrum.database import (
    Cursor,
    Database,
    ENABLE_MXDB,
    kickstart,
)
from Cerebrum.Utils import read_password
from Cerebrum.utils import date_compat

from . import macros

import cereconf


#
# Oracle type conversion
#
# Type Handlers with cx_Oracle are documented here:
#
#  <https://cx-oracle.readthedocs.io/en/8.3.0/user_guide/bind.html#changing-bind-data-types-using-an-input-type-handler>
#  <https://cx-oracle.readthedocs.io/en/8.3.0/user_guide/sql_execution.html#outputtypehandlers>
#
#  <https://python-oracledb.readthedocs.io/en/latest/user_guide/bind.html#inputtypehandlers>
#  <https://python-oracledb.readthedocs.io/en/latest/user_guide/sql_execution.html#outputtypehandlers>
#
# TODO: Should we normalize unicode data in the driver itself? That would kill
# our ability to read/write and compare unicode data as-is, but would also make
# sure that anything unicode in Cerebrum is as intended.
#


def bytes2unicode(value):
    return value.decode('ascii')


if ENABLE_MXDB:
    import mx.DateTime

    def datetime2mx(value):
        """ datetime.datetime to mx.DateTime. """
        return mx.DateTime.DateTime(
            value.year, value.month, value.day,
            value.hour, value.minute, int(value.second),
        )
else:
    def datetime2mx(value):
        """ datetime.datetime to mx.DateTime. """
        raise NotImplementedError("no mx.DateTime support (ENABLE_MXDB)")


def mx2datetime(value):
    return datetime.datetime(value.year, value.month, value.day,
                             value.hour, value.minute, int(value.second))


def cx_InputTypeHandler(cursor, value, numElements):  # noqa: N802, N803
    """ Convert value from Cerebrum to cx_Oracle. """

    # bytestring -> unicode
    if isinstance(value, bytes):
        return cursor.var(
            six.text_type,
            arraysize=numElements,
            inconverter=bytes2unicode,
        )

    if isinstance(value, six.text_type):
        # TODO: Normalize?
        return

    if date_compat.is_mx_datetime(value):
        # mx.DateTime -> datetime.datetime
        return cursor.var(
            datetime.datetime,
            arraysize=numElements,
            inconverter=mx2datetime,
        )


def cx_OutputTypeHandler(cursor, name, defaultType, size,  # noqa: N802, N803
                         precision, scale):
    """ Convert value from cx_Oracle to Cerebrum. """

    if ENABLE_MXDB and defaultType == cx_oracle_module.DATETIME:
        # datetime.datetime -> mx.DateTime
        return cursor.var(
            datetime.datetime,
            size,
            arraysize=cursor.arraysize,
            outconverter=datetime2mx,
        )

    if defaultType in (cx_oracle_module.STRING, cx_oracle_module.FIXED_CHAR):
        # string-like -> unicode
        #
        # TODO: Normalize here? We have no control over the data in FS, but
        # then again, we might need the ability to get the data as-is as well.
        return cursor.var(six.text_type, size, cursor.arraysize)


class cx_OracleCursor(Cursor):  # noqa: N801
    """
    A special cursor subclass to handle cx_Oracle's quirks.

    This class is a workaround for cx_Oracle's feature where it refuses to
    accept unused names in bind dictionary in the the execute() method. We
    redefine a dictionary with 'used-only' bind names, and send that
    dictionary to the backend's execute(). This hack implies a performance
    hit, since we parse each statement (at least) twice.
    """

    def execute(self, operation, parameters=()):
        # Translate Cerebrum-specific hacks ([:]-syntax we love, e.g.). We
        # must do this, before feeding operation to the backend, since we've
        # effectively extended sql syntax.
        sql, binds = self._translate(operation, parameters)

        # Now that we have raw sql, we need to check if binds contains some
        # superfluous identifiers. If it does, we have to purge them, since
        # cx_Oracle bails with an error when there are more binds than free
        # variables.

        # 1. Prepare the statement (so that the backend can report some useful
        #    information about this.) This costs extra time, but it is
        #    inevitable, since bindnames() requires a prepared statement.
        self._cursor.prepare(sql)

        # 2. Extract the bind names. This is the list we compare to binds. The
        #    problem is of course that this bastard upcases the names.
        actual_binds = self._cursor.bindnames()

        mybinds = dict()
        for next_bind in actual_binds:
            if next_bind in binds:
                mybinds[next_bind] = binds[next_bind]
            elif next_bind.lower() in binds:
                mybinds[next_bind.lower()] = binds[next_bind.lower()]
            else:
                # what to do?
                raise ValueError(
                    "Cannot remap bind name %s to actual parameter"
                    % repr(next_bind)
                )

        # super().execute will redo a considerable part of the work here. It
        # is a performance hit (FIXME: how much of a performance hit?), but
        # right now (2008-06-30) we do not care.
        return super(cx_OracleCursor, self).execute(sql, mybinds)


ora_macros = macros.MacroTable(macros.common_macros)


@ora_macros.register('table')
def ora_op_table(schema, name, context=None):
    return '{}.{}'.format(six.text_type(schema), six.text_type(name))


@ora_macros.register('now')
def ora_op_now(context=None):
    # TODO: Why SYSDATE over the standard CURRENT_TIMESTAMP?
    return 'SYSDATE'


@ora_macros.register('from_dual')
def ora_op_from_dual(context=None):
    """ Oracle mock-table for selecting constants or performing functions. """
    return 'FROM DUAL'


@ora_macros.register('sequence')
def ora_op_sequence(schema, name, op, context=None):
    schema = six.text_type(schema)
    name = six.text_type(name)
    op = six.text_type(op)

    if op == 'next':
        return '{}.{}.nextval'.format(schema, name)
    elif op == 'curr':
        return '{}.{}.currval'.format(schema, name)
    else:
        raise ValueError('Invalid sequence operation: %r' % (op,))


class OracleBase(Database):
    """Oracle database driver class."""

    rdbms_id = "Oracle"
    macro_table = ora_macros

    def __init__(self, *args, **kws):
        for cls in self.__class__.__mro__:
            if issubclass(cls, OracleBase):
                return super(OracleBase, self).__init__(*args, **kws)
        raise NotImplementedError(
            "Can't instantiate abstract class <OracleBase>.")


@kickstart(cx_oracle_module)
class cx_Oracle(OracleBase):  # noqa: N801

    def connect(self, user=None, password=None, service=None,
                client_encoding=None):
        cdata = self._connect_data
        cdata.clear()
        cdata['arg_user'] = user
        cdata['arg_password'] = password
        cdata['arg_service'] = service
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME
        if user is None:
            user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        if password is None:
            password = read_password(user, service)
        conn_str = '%s/%s@%s' % (user, password, service)
        cdata['conn_str'] = conn_str
        if client_encoding is None:
            client_encoding = self.encoding
        else:
            self.encoding = client_encoding

        # The encoding names in Oracle don't look like PostgreSQL's,
        # so we translate them into a single standard.
        # TODO: Fix this, so that all valid encodings will actually work?
        encoding_names = {'iso8859-1': "american_america.we8iso8859p1",
                          'utf-8': "american_america.utf8"}
        codec_info = codecs.lookup(client_encoding)
        os.environ['NLS_LANG'] = encoding_names.get(codec_info.name,
                                                    client_encoding)

        # Call superclass .connect with appropriate CONNECTIONSTRING;
        # this will in turn invoke the connect() function in the
        # cx_Oracle module.
        super(cx_Oracle, self).connect(conn_str)

        self._db.inputtypehandler = cx_InputTypeHandler
        self._db.outputtypehandler = cx_OutputTypeHandler

    def cursor(self):
        return cx_OracleCursor(self)
