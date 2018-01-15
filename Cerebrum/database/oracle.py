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

import codecs
import datetime
import os

import cx_Oracle as cx_oracle_module
import six
from mx import DateTime

from Cerebrum.database import Cursor, Database, OraPgLock, kickstart
from Cerebrum.Utils import read_password

import cereconf


#
# Oracle type conversion
#
# Type Handlers with cx_Oracle are documented here:
#   http://www.oracle.com/technetwork/articles/dsl/tuininga-cx-oracle-084866.html
#
# TODO: Should we normalize unicode data in the driver itself? That would kill
# our ability to read/write and compare unicode data as-is, but would also make
# sure that anything unicode in Cerebrum is as intended.
#


def normalize(unicode_string):
    return unicode_string


def bytes2unicode(value):
    return value.decode('ascii')


def datetime2mx(value):
    return DateTime.DateTime(value.year, value.month, value.day, value.hour,
                             value.minute, int(value.second))


def mx2datetime(value):
    return datetime.datetime(value.year, value.month, value.day,
                             value.hour, value.minute, int(value.second))


def cx_InputTypeHandler(cursor, value, numElements):
    if isinstance(value, bytes):
        # inconverter vs outconverter
        return cursor.var(six.text_type,
                          arraysize=numElements,
                          inconverter=bytes2unicode)
    elif isinstance(value, six.text_type):
        # TODO: Normalize?
        # return cursor.var(six.text_type,
        #                   arraysize=numElements,
        #                   inconverter=normalize)
        pass
    elif isinstance(value, DateTime.DateTimeType):
        return cursor.var(datetime.datetime,
                          arraysize=numElements,
                          inconverter=mx2datetime)


def cx_OutputTypeHandler(cursor, name, defaultType, size, precision, scale):
    """ Type casting handler for the cx_Oracle database. """

    if defaultType == cx_oracle_module.DATETIME:
        return cursor.var(datetime.datetime, size,
                          arraysize=cursor.arraysize,
                          outconverter=datetime2mx)
    if defaultType in (cx_oracle_module.STRING, cx_oracle_module.FIXED_CHAR):
        # TODO: Normalize here? We have no control over the data in FS, but
        # then again, we might need the ability to get the data as-is as well.
        return cursor.var(six.text_type, size, cursor.arraysize)


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
        return super(cx_OracleCursor, self).execute(sql, mybinds)

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


@kickstart(cx_oracle_module)
class cx_Oracle(OracleBase):

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

    # IVR 2009-02-12 FIXME: We should override nextval() here to query the
    # schema name directly from the underlying connection object. This
    # should be possible from cx_Oracle 5.0
