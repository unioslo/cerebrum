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
Oracle DB functionality for the people
"""

import datetime
import os

from mx import DateTime

from Cerebrum.database import Cursor, Database, OraPgLock
from Cerebrum.Utils import read_password

import cereconf


class cx_OracleCursor(Cursor):
    """
    A special cursor subclass to handle cx_Oracle's quirks.

    This class is a workaround for cx_Oracle's feature where it refuses to
    accept unused names in bind dictionary in the the execute() method. We
    redefine a dictionary with 'used-only' bind names, and send that
    dictionary to the backend's execute(). This hack implies a performance
    hit, since we parse each statement (at least) twice.
    """

    def execute(self, operation, parameters=()):
        # cx_Oracle operates with datetime.
        for k in parameters:
            if type(parameters[k]) is DateTime.DateTimeType:
                tmp = parameters[k]
                parameters[k] = datetime.datetime(tmp.year, tmp.month, tmp.day,
                                                  tmp.hour, tmp.minute,
                                                  int(tmp.second))

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
                raise ValueError("Cannot remap bind name %s to "
                                 "actual parameter" % next_bind)

        # super().execute will redo a considerable part of the work here. It
        # is a performance hit (FIXME: how much of a performance hit?), but
        # right now (2008-06-30) we do not care.
        retval = super(cx_OracleCursor, self).execute(sql, mybinds)
        return retval
    # end execute

    def query(self, query, params=(), fetchall=True):
        raw_result = list(super(cx_OracleCursor, self).query(
                          query, params=params, fetchall=fetchall))

        # IVR 2009-02-12 FIXME: respect fetchall while making conversions.
        for item in raw_result:
            for j in range(len(item)):
                field = item[j]
                if type(field) is datetime.datetime:
                    item[j] = DateTime.DateTime(field.year,
                                                field.month,
                                                field.day,
                                                field.hour,
                                                field.minute,
                                                int(field.second))
        return raw_result

    def acquire_lock(self, table=None, mode='exclusive'):
        return OraPgLock(cursor=self, table=None, mode=mode)


class OracleBase(Database):
    """Oracle database driver class."""

    rdbms_id = "Oracle"

    def __init__(self, *args, **kws):
        for cls in self.__class__.__mro__:
            if issubclass(cls, OracleBase):
                return super(OracleBase, self).__init__(*args, **kws)
        raise NotImplementedError(
            "Can't instantiate abstract class <OracleBase>.")

    def _sql_port_table(self, schema, name):
        return ['%(schema)s.%(name)s' % locals()]

    def _sql_port_sequence(self, schema, name, op):
        if op == 'next':
            return ['%(schema)s.%(name)s.nextval' % locals()]
        elif op == 'current':
            return ['%(schema)s.%(name)s.currval' % locals()]
        else:
            raise self.ProgrammingError, 'Invalid sequence operation: %s' % op

    def _sql_port_sequence_start(self, value):
        return ['START', 'WITH', value]

    def _sql_port_from_dual(self):
        return ["FROM", "DUAL"]

    def _sql_port_now(self):
        return ['SYSDATE']


class DCOracle2(OracleBase):

    _db_mod = "DCOracle2"

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
        encoding_names = {'ISO_8859_1': "american_america.we8iso8859p1",
                          'UTF-8': "american_america.utf8"}
        os.environ['NLS_LANG'] = encoding_names.get(client_encoding,
                                                    client_encoding)
        #
        # Call superclass .connect with appropriate CONNECTIONSTRING;
        # this will in turn invoke the connect() function in the
        # DCOracle2 module.
        super(Oracle, self).connect(conn_str)

    def pythonify_data(self, data):
        """Convert type of values in row to native Python types."""
        # Short circuit; no conversion is necessary for DCOracle2.
        return data


class cx_Oracle(OracleBase):
    """
    """

    _db_mod = "cx_Oracle"

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
        encoding_names = {'ISO_8859_1': "american_america.we8iso8859p1",
                          'UTF-8': "american_america.utf8"}
        os.environ['NLS_LANG'] = encoding_names.get(client_encoding,
                                                    client_encoding)

        # Call superclass .connect with appropriate CONNECTIONSTRING;
        # this will in turn invoke the connect() function in the
        # cx_Oracle module.
        super(cx_Oracle, self).connect(conn_str)
    # end connect

    def cursor(self):
        return cx_OracleCursor(self)
    # end cursor

    def pythonify_data(self, data):
        """Convert type of value(s) in data to native Python types."""
        if isinstance(data, datetime.datetime):
            return DateTime.DateTime(data.year, data.month, data.day,
                                     data.hour, data.minute, data.second)
        return super(cx_Oracle, self).pythonify_data(data)
    # end pythonify_data

    # IVR 2009-02-12 FIXME: We should override nextval() here to query the
    # schema name directly from the underlying connection object. This should
    # be possible from cx_Oracle 5.0

Oracle = DCOracle2
