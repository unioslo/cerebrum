#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2016 University of Oslo, Norway
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
""" Database context for a flask app. """

from __future__ import unicode_literals

from flask import g
from Cerebrum.Utils import Factory


_CLS_DB = Factory.get(b'Database')
_CLS_CONST = Factory.get(b'Constants')


def _connect():
    return _CLS_DB(client_encoding='utf-8')


class DatabaseContext(object):
    """Interface to the Cerebrum database."""

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """ Setup app context. """
        self.dryrun = app.config.get('DRYRUN', False)
        app.teardown_appcontext(self.teardown)

    def teardown(self, exception):
        """ Close the database connection.

        This method should be called at the end of each request.
        """
        conn = getattr(g, '_database', None)
        try:
            if conn is not None:
                if exception:
                    conn.rollback()
                elif self.dryrun:
                    conn.rollback()
                else:
                    conn.commit()
                conn.close()
        finally:
            for attr in ('_database', '_constants'):
                if hasattr(g, attr):
                    delattr(g, attr)

    @property
    def connection(self):
        """ database connection. """
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = _connect()
        return db

    @property
    def const(self):
        """ constants. """
        const = getattr(g, '_constants', None)
        if const is None:
            const = g._constants = _CLS_CONST(self.connection)
        return const
