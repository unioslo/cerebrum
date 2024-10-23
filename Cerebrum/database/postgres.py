# -*- coding: utf-8 -*-
#
# Copyright 2018-2024 University of Oslo, Norway
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
PostgreSQL / PsycoPG2 DB functionality for the people
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import os
import sys
import uuid

import psycopg2
import psycopg2.extensions
import six

from Cerebrum.database import (
    Cursor,
    Database,
    ENABLE_MXDB,
    kickstart,
)
from Cerebrum.Utils import read_password
from Cerebrum.utils.funcwrap import deprecate
from Cerebrum.utils.transliterate import to_ascii

from . import macros

import cereconf


#
# Postgres data type conversion
#
PG_TYPE_UNICODE = psycopg2.extensions.UNICODE
PG_TYPE_UNICODEARRAY = psycopg2.extensions.UNICODEARRAY
PG_TYPE_DATE = psycopg2.extensions.DATE
PG_TYPE_DATETIME = psycopg2.DATETIME
PG_TYPE_DECIMAL = psycopg2.extensions.DECIMAL
PG_TYPE_NUMBER = psycopg2.NUMBER


# Unicode data types
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)


# mx.DateTime data types
if ENABLE_MXDB:
    import mx.DateTime

    def mxdate(value, cursor):
        """ psycopg2 type, DATE -> mx.DateTime. """
        dt = PG_TYPE_DATE(value, cursor)
        if dt is None:
            return None
        return mx.DateTime.DateTime(dt.year, dt.month, dt.day)

    def mxdatetime(value, cursor):
        """ psycopg2 type, DATETIME -> mx.DateTime. """
        dt = PG_TYPE_DATETIME(value, cursor)
        if dt is None:
            return None
        return mx.DateTime.DateTime(dt.year, dt.month, dt.day,
                                    dt.hour, dt.minute, dt.second)

    def mxdatetimetype(value):
        """ psycopg2 adapter, mx.DateTimeType -> Timestamp. """
        return psycopg2.Timestamp(value.year, value.month, value.day,
                                  value.hour, value.minute, int(value.second))

    # DATE -> mx.DateTime
    psycopg2.extensions.register_type(
        psycopg2.extensions.new_type(
            PG_TYPE_DATE.values, str('MXDATE'), mxdate))

    # TIMESTAMP -> mx.DateTime
    psycopg2.extensions.register_type(
        psycopg2.extensions.new_type(
            PG_TYPE_DATETIME.values, str('MXDATETIME'), mxdatetime))

    psycopg2.extensions.register_adapter(mx.DateTime.DateTimeType,
                                         mxdatetimetype)


def safebytes(value):
    """ psycopg2 adapter, bytes -> unicode.

    This method ensures that no weird, invalid encoded data gets sent to the
    database. Only ASCII-encoded bytestrings can be used as arguments.
    """
    return psycopg2.extensions.adapt(value.decode('ascii'))


psycopg2.extensions.register_adapter(bytes, safebytes)


# PY3:
# We would *probably* be OK just using ints across the board, but let's keep
# using long in PY2 just in case.
try:
    _long = long
except NameError:
    _long = int
try:
    _maxint = sys.maxint
except AttributeError:
    _maxint = None


def numtype(value, cursor):
    """ psycopg2 type, DECIMAL/NUMBER -> float/int/long. """
    # The PsycoPG driver returns floats for all columns of type
    # numeric.  The PyPgSQL driver only does this if the column is
    # defined to have digits.  This method makes PsycoPG behave
    # the same way
    desc = cursor.description[0]
    # DECIMAL is a subtype of NUMBER, so we need to use the same handler here.
    if desc.type_code == PG_TYPE_DECIMAL:
        value = PG_TYPE_DECIMAL(value, cursor)
    else:
        value = PG_TYPE_NUMBER(value, cursor)

    if value is None:
        pass
    elif desc.scale and desc.scale > 0:
        value = float(value)
    elif _maxint and value <= _maxint:
        # Only PY2; int if number can fit in int
        value = int(value)
    else:
        # long in PY2, int in PY3
        value = _long(value)

    return value


psycopg2.extensions.register_type(
    psycopg2.extensions.new_type(
        PG_TYPE_NUMBER.values, str('PYPGNUM'), numtype))


def get_pg_savepoint_id():
    """
    Return a unique identifier suitable for savepoints.

    A valid identifier in Postgres is:

    * <= 63 characters
    * SQL identifiers and key words must begin with a letter (a-z, but also
      letters with diacritical marks and non-Latin letters) or an underscore
      (_). Subsequent characters in an identifier or key word can be letters,
      underscores, digits (0-9) (...)

    Source:
    <http://www.postgresql.org/docs/8.1/static/sql-syntax.html#SQL-SYNTAX-IDENTIFIERS>

    UUID4 is an easy choice, provided we manipulate it somewhat.
    """
    return "unique" + str(uuid.uuid4()).replace('-', '_')


def _format_pg_app_name(progname=None):
    """
    Format an application_name for use with postgresql.

    Postgresql supports setting an application_name for connections, which can
    be seen e.g. in pg_stat_activity.  The name must consist of ascii chars and
    be 64 chars or less.
    """
    fmt = 'cerebrum (%s)'
    # application_name can be 64 chars total, ascii only
    remaining = 63 - len(fmt) + 2
    progname = to_ascii(progname or 'no name')
    if len(progname) > remaining:
        progname = progname[:remaining-3] + '...'
    return fmt % progname


class PsycoPG2Cursor(Cursor):
    """
    """
    def ping(self):
        """Check if the database is still reachable.

        Caveat: regardless of the autocommit settings, we want to make sure
        that ping-ing happens as its own transaction and DOES NOT affect the
        state of the environment in which ping has been invoked.
        """
        identifier = get_pg_savepoint_id()
        channel = self.driver_cursor()
        channel.execute("SAVEPOINT %s" % identifier)
        try:
            channel.execute("""SELECT 1 AS foo""")
        finally:
            channel.execute("ROLLBACK TO SAVEPOINT %s" % identifier)


pg_macros = macros.MacroTable(macros.common_macros)


@pg_macros.register('now')
def pg_op_now(context=None):
    # TODO: Why NOW() over the standard CURRENT_TIMESTAMP?
    return 'NOW()'


@pg_macros.register('sequence')
def pg_op_sequence(schema, name, op, val=None, context=None):
    """
    Postgres sequence manipulation

    Note that postgres adds an additional 'set' op.
    """
    name = six.text_type(name)
    op = six.text_type(op)

    if op == 'next':
        return "nextval('{}')".format(name)
    elif op == 'curr':
        return "currval('{}')".format(name)
    elif op == 'set':
        return "setval('{}', {})".format(name, int(val))
    else:
        raise ValueError('Invalid sequence operation: %r' % (op,))


@pg_macros.register('sequence_start')
@deprecate('Please avoid using the [:sequence_start] macro')
def pg_op_sequence_start(value, context=None):
    # TODO: Why not 'START WITH'?
    return 'START {}'.format(int(value))


class PostgreSQLBase(Database):
    """PostgreSQL driver base class."""

    rdbms_id = "PostgreSQL"
    macro_table = pg_macros

    def __init__(self, *args, **kws):
        for cls in self.__class__.__mro__:
            if issubclass(cls, PostgreSQLBase):
                return super(PostgreSQLBase, self).__init__(*args, **kws)
        raise NotImplementedError(
            "Can't instantiate abstract class <PostgreSQLBase>.")


@kickstart(psycopg2)
class PsycoPG2(PostgreSQLBase):
    """PostgreSQL driver class using psycopg."""

    def connect(self,
                user=None,
                password=None,
                service=None,
                client_encoding=None,
                host=None,
                port=None):
        dsn = []
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME
        if user is None:
            user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        if host is None:
            host = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('host')
        if port is None:
            port = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('port')
        if password is None and user is not None:
            password = read_password(user, service, host)

        if service is not None:
            dsn.append('dbname=' + service)
        if user is not None:
            dsn.append('user=' + user)
        if password is not None:
            dsn.append('password=' + password)
        if host is not None:
            dsn.append('host=' + host)
        if port is not None:
            dsn.append('port=' + str(port))

        dsn_string = ' '.join(dsn)

        if client_encoding is None:
            client_encoding = self.encoding
        else:
            self.encoding = client_encoding

        script_name = os.path.basename(sys.argv[0])
        if self._app_hint:
            app_name = _format_pg_app_name('{} - {}'.format(self._app_hint,
                                                            script_name))
        else:
            app_name = _format_pg_app_name(script_name)

        super(PsycoPG2, self).connect(dsn_string, application_name=app_name)

        self._db.set_isolation_level(1)  # read-committed
        self.execute("SET CLIENT_ENCODING TO '%s'" % client_encoding)
        self.commit()

    def cursor(self):
        return PsycoPG2Cursor(self)

    def ping(self):
        """psycopg2-specific version of ping.

        The main issue here is that psycopg2 opens a new transaction upon the
        first execute(). Unless autocommit is on (which it is not for us),
        that transaction remains open until a commit/rollback. Constants.py
        uses its own private connection and that connection+transaction could
        remain in the <IDLE> state indefinitely.
        """

        import psycopg2.extensions as ext
        conn = self.driver_connection()
        status = conn.get_transaction_status()
        c = self.cursor()
        c.ping()
        c.close()
        # It is NOT safe to roll back, unless there are just this cursor's
        # actions in the transaction...
        if status in (ext.TRANSACTION_STATUS_IDLE,):
            self.rollback()
