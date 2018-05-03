#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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

from functools import wraps
from Cerebrum.Utils import Factory
from Cerebrum.ChangeLog import ChangeLog
from . import context


_CLS_DB = Factory.get('Database')
_CLS_CONST = Factory.get('Constants')


class DatabaseContext(object):
    """ Interface to the Cerebrum database.

    Example:
        app = Flask('name')
        db = DatabaseContext(app)
        with app.app_context():
            db.connection.query("SELECT 'foo' as bar")
            db.rollback()

        @db.autocommit
        def foo():
            db.connection.query("SELECT 'foo' as bar")
            raise Exception('rollback')

        with app.app_context():
            foo()
    """

    _change_by = context.ContextValue('database_change_by')
    _db_conn = context.ContextValue('database')
    _const = context.ContextValue('constants')

    def __init__(self, app=None):
        self.__change_program = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """ Setup app context. """
        self.__change_program = app.name
        self.dryrun = app.config.get('DRYRUN', False)
        app.teardown_appcontext(self.close)

    @property
    def connection(self):
        """ database connection. """
        if self._db_conn is None:
            self._db_conn = _CLS_DB()
            if isinstance(self._db_conn, ChangeLog):
                self._db_conn.cl_init()
            self._update_changelog()
        return self._db_conn

    @property
    def const(self):
        """ constants. """
        if self._const is None:
            self._const = _CLS_CONST(self.connection)
        return self._const

    def commit(self):
        """ Commit changes.

        If 'DRYRUN' is set to true, this method will actaully perform a
        rollback.
        """
        if self._db_conn is None:
            return
        if self.dryrun:
            self._db_conn.rollback()
        if self._db_conn is not None:
            self._db_conn.commit()

    def rollback(self):
        """ Roll back changes. """
        if self._db_conn is None:
            return
        self._db_conn.rollback()

    def autocommit(self, func):
        """ Auto commit if function succeeds. """
        @wraps(func)
        def handle(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                self.commit()
                return result
            except Exception:
                self.rollback()
                raise
        return handle

    def _update_changelog(self):
        """ Update ChangeLog with change attributes. """
        if self._db_conn is None:
            return
        if not isinstance(self._db_conn, ChangeLog):
            return
        self._db_conn.change_by = self._change_by
        self._db_conn.change_program = self.__change_program

    def set_change_by(self, user_id):
        """ Set ChangeLog.change_by. """
        self._change_by = user_id
        self._update_changelog()

    def close(self, exception):
        """ Close the database connection.

        This method should be called at the end of each request.
        """
        if self._db_conn is not None:
            self._db_conn.close()
        context.ContextValue.clear_object(self)
