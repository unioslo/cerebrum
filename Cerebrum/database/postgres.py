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
PostgreSQL / PsycoPG2 DB functionality for the people
"""

import datetime
import uuid
import os
import re
import sys

from mx import DateTime

from Cerebrum.database import Cursor, Database, OraPgLock
from Cerebrum.Utils import read_password

import cereconf


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

    def execute(self, operation, parameters=()):
        # IVR 2008-10-30 TBD: This is not really how the psycopg framework
        # is supposed to be used. There is an adapter mechanism, and we should
        # really register our type conversion hooks there.
        for k in parameters:
            if type(parameters[k]) is DateTime.DateTimeType:
                ts = parameters[k]
                parameters[k] = self.Timestamp(ts.year, ts.month, ts.day,
                                               ts.hour, ts.minute,
                                               int(ts.second))
            elif (type(parameters[k]) is unicode and
                  self._db.encoding != 'UTF-8'):
                # pypgsql1 does not support unicode (only utf-8)
                parameters[k] = parameters[k].encode(self._db.encoding)
        if (type(operation) is unicode and
                self._db.encoding != 'UTF-8'):
            operation = operation.encode(self._db.encoding)

        # A static method is slightly faster than a lambda.
        def utf8_decode(s):
            """Converts a str containing UTF-8 octet sequences into
            unicode objects."""
            return s.decode('UTF-8')

        ret = super(PsycoPG2Cursor, self).execute(operation, parameters)
        self._convert_cols = {}
        if self.description is not None:
            for n in range(len(self.description)):
                if (self.description[n][1] == self._db.NUMBER and
                        self.description[n][5] <= 0):  # pos 5=scale in DB-API
                    self._convert_cols[n] = long
                elif (self._db.encoding == 'UTF-8' and
                      self.description[n][1] == self._db.STRING):
                    self._convert_cols[n] = utf8_decode
        db_mod = self._db._db_mod

        def date_to_mxdatetime(dt):
            return DateTime.DateTime(dt.year, dt.month, dt.day)

        def datetime_to_mxdatetime(dt):
            return DateTime.DateTime(dt.year, dt.month, dt.day,
                                     dt.hour, dt.minute, dt.second)

        if self.description is not None:
            for n, item in enumerate(self.description):
                if item[1] == db_mod._psycopg.DATE:
                    self._convert_cols[n] = date_to_mxdatetime
                elif item[1] == db_mod._psycopg.DATETIME:
                    self._convert_cols[n] = datetime_to_mxdatetime
                # we want to coerce Decimal (python 2.5 + psycopg2) to float,
                # since we do not know how our code base will react to Decimal
                # 1 - typecode, 5 - scale. psycopg2 returns decimals for
                # elements that have scale > 0.
                elif item[1] == db_mod._psycopg.DECIMAL and item[5] > 0:
                    self._convert_cols[n] = float
        return ret

    def query(self, query, params=(), fetchall=True):
        # The PsycoPG driver returns floats for all columns of type
        # numeric.  The PyPgSQL driver only does this if the column is
        # defined to have digits.  This method makes PsycoPG behave
        # the same way
        ret = super(PsycoPG2Cursor, self).query(
            query, params=params, fetchall=fetchall)
        if fetchall and self._convert_cols:
            for r in range(len(ret)):
                for n, conv in self._convert_cols.items():
                    if ret[r][n] is not None:
                        ret[r][n] = conv(ret[r][n])
        return ret

    def wrap_row(self, row):
        """Return `row' wrapped in a db_row object."""
        ret = self._row_class(row)
        for n, conv in self._convert_cols.items():
            if ret[n] is not None:
                ret[n] = conv(ret[n])
        return ret

    def acquire_lock(self, table=None, mode='exclusive'):
        return OraPgLock(cursor=self, table=table, mode='exclusive')


class PostgreSQLBase(Database):
    """PostgreSQL driver base class."""

    rdbms_id = "PostgreSQL"

    def __init__(self, *args, **kws):
        for cls in self.__class__.__mro__:
            if issubclass(cls, PostgreSQLBase):
                return super(PostgreSQLBase, self).__init__(*args, **kws)
        raise NotImplementedError(
            "Can't instantiate abstract class <PostgreSQLBase>.")

    def _sql_port_table(self, schema, name):
        return [name]

    def _sql_port_sequence(self, schema, name, op, val=None):
        if op == 'next':
            return ["nextval('%s')" % name]
        elif op == 'curr':
            return ["currval('%s')" % name]
        elif op == 'set' and val is not None:
            return ["setval('%s', %s)" % (name, val)]
        else:
            raise ValueError('Invalid sequnce operation: %s' % op)

    def _sql_port_sequence_start(self, value):
        return ['START', value]

    def _sql_port_from_dual(self):
        return []

    def _sql_port_now(self):
        return ['NOW()']


class PsycoPG2(PostgreSQLBase):
    """PostgreSQL driver class using psycopg."""

    _db_mod = "psycopg2"

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

        super(PsycoPG2, self).connect(dsn_string)
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
