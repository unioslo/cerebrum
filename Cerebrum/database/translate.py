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
SQL dialect adapter.

This module contains functionality to translate Cerebrum SQL queries to queries
that fits in with the actual db driver.  It's the main entry point for
translating macros and paramstyle.
"""
from __future__ import print_function

import logging
import os
import six

from Cerebrum import Cache

# TODO: Remove feature toggle for selecting translate() implementation.
if os.environ.get('CEREBRUM_SQL_LEXER', '').lower() == 'plex':
    from .lexer_plex import _translate
else:
    from .lexer_sqlparse import _translate

logger = logging.getLogger(__name__)


def make_statement_cache(size=100):
    return Cache.Cache(mixins=[Cache.cache_slots, Cache.cache_mru], size=size)


class Dialect(object):
    """
    The database dialect is essentially just a placeholder that holds two
    things:

    1. A macro table (``macros.MacroTable`` object) that implements
       certain database specific macros.

       The choice of macro table is typically set in a `.Database` subclass.

    2. A parameter type (``paramstyles.Base`` subclass) that can be used to
       translate placeholders, and to register expected placeholders so that we
       can verify that our query gets all its expected parameters/bindings.

       The choice of parameter type is typically decided by the db driver
       *paramstyle*.
    """

    def __init__(self, macro_table, param_cls):
        self.macro_table = macro_table
        self.param_cls = param_cls


# TODO: Optimize caching
# ----------------------
# We could get a significant speedup in services that re-create a database
# object often by moving the Translator cache *outside* of the Translator
# object, as each db cursor has its own object/cache.
#
# If implemented, we'd have to handle that:
#
# - Different dialects should use different caches
# - Statement translation may change if the dialect.macro_table changes
# - Statement translation may change if the dialect.param_cls changes
# - Statement translation may change if the macro context changes
#   ([:get_constant], [:get_config]).
#
# Also, if cache is moved to e.g. module level or another thread shared object,
# we must remember to protect cache access with threading locks (i.e. wrap
# everyting between cache lookup to potential cache update in a
# `with cache_lock` threading.Lock context manager).


class Translator(object):
    """
    A translator class for pre-processing sql statements.

    This object is the main callable that translates a given *abstract*
    cerebrum database statement *with* a parameters dict into a db driver
    specific sql statement with a suitable collections of parameters.
    """

    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.cache = make_statement_cache()
        self.dialect = db.dialect

    def get_macro(self, op, params):
        context = {'db': self.db, 'config': self.config}
        return self.dialect.macro_table(op, params, context=context)

    def __call__(self, statement, params):
        params = params or {}
        if not isinstance(params, dict):
            raise ValueError('Params must be dict')

        # None of the database engines understand _CerebrumCode,
        # so we convert them to plain integers to simplify usage.
        from Cerebrum.Constants import _CerebrumCode
        for k in params:
            if isinstance(params[k], _CerebrumCode):
                params[k] = int(params[k])

        if not isinstance(statement, six.text_type):
            statement = statement.decode('ascii')

        try:
            fixed_stmt, param_fixer = self.cache[statement]
            return fixed_stmt, param_fixer(params)
        except KeyError:
            pass

        fixed_stmt, param_fixer = _translate(
            statement,
            self.dialect.param_cls,
            self.get_macro)

        # Cache for later use.
        self.cache[statement] = (fixed_stmt, param_fixer)
        return fixed_stmt, param_fixer(params)
