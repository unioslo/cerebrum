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
Implementation of a sqlparse filter stack that translates Cerebrum statements.
"""
from __future__ import print_function, unicode_literals

import logging
import os

import six
from sqlparse import tokens
from sqlparse.engine import FilterStack
from sqlparse.filters import SerializerUnicode

from .macros import parse_macro


logger = logging.getLogger(__name__)
MacroToken = tokens.Name.Macro

# Note: enables excessive debug logging by our filters.
#
# This will cause substantial slow-down in daemons where the database/sql-cache
# is short-lived (api, bofhd, etc...).
# Use this flag only to enable debug logging while debugging in test
# environments.
if os.environ.get('CEREBRUM_SQL_DEBUG', '').lower() in ('yes', 'true', '1'):
    debug_log = True
else:
    debug_log = False


class IdentifyMacroFilter(object):
    """
    A sqlparse preprocessor filter that identifies Macro tokens.

    Macro tokens are recognized as Name tokens by sqlparse -- we need to
    examine all name tokens, and check if they look like valid macros.
    """
    def process(self, stream):
        for ttype, value in stream:
            if ttype == tokens.Name:
                try:
                    name, params = parse_macro(value)
                except ValueError:
                    # not a macro
                    yield ttype, value
                else:
                    if debug_log:
                        logger.debug('found macro=%r -> name=%r, params=%r',
                                     value, name, params)
                    yield MacroToken, value
            else:
                yield ttype, value


class ProcessMacroFilter(object):
    """
    A sqlparse preprocessor filter that translates macros.

    .. note:: Requires a IdentifyMacroFilter to run first!

    This filter resolves all Macro tokens using the given `translate_macro`
    callback.
    """
    # expect = (
    #     None,
    #     tokens.Text.Whitespace,
    #     tokens.Text.Whitespace.Newline,
    #     tokens.Punctuation,
    # )

    def __init__(self, translate_macro):
        self.translate_macro = translate_macro

    def _process_macro(self, name, params):
        result = self.translate_macro(name, params)
        if debug_log:
            logger.debug('translated macro(%r, %r) = %r',
                         name, params, result)
        # TODO: Should we parse the result as well? It might be useful to
        #       generate the correct tokens for our macro result!
        yield MacroToken, result

    def process(self, stream):
        for ttype, value in stream:
            if ttype == MacroToken:
                name, params = parse_macro(value)
                for tt, val in self._process_macro(name, params):
                    yield tt, val
            else:
                yield ttype, value


class _FindWhitespaceErrors(object):

    def __init__(self, log=False, fix=False):
        self.log = log
        self.fix = fix

    def _fmt_sql(self, tokens):
        return ''.join(t[1] for t in tokens)

    def process(self, stream):
        q = []
        prev = None, None

        for ttype, value in stream:
            q.append((ttype, value))

            if ttype == MacroToken and prev[0] == tokens.Keyword:
                if self.log:
                    logger.error(
                        'missing whitespace between %r and %r (%s ...)',
                        prev, (ttype, value), self._fmt_sql(q))
                if self.fix:
                    yield tokens.Text.Whitespace, ' '
            elif ttype == tokens.Keyword and prev[0] == MacroToken:
                if self.log:
                    logger.error(
                        'missing whitespace between %r and %r (%s ...)',
                        prev, (ttype, value), self._fmt_sql(q))
                if self.fix:
                    yield tokens.Text.Whitespace, ' '

            yield ttype, value
            prev = ttype, value


class TranslatePlaceholderFilter(object):
    """
    A sqlparse preprocessor filter that translates placeholders.

    This filter uses a ``paramstyles.Base`` register to translate placeholders
    into a given paramstyle, and to collect all known placeholder names for a
    given query.

    .. warning::
        This filter is stateful - it keeps a reference to a paramstyles object!
    """

    def __init__(self, param_register):
        self.params = param_register

    def process(self, stream):
        for ttype, value in stream:
            if ttype == tokens.Name.Placeholder:
                if not value[0] == ':':
                    raise ValueError("invalid placeholder style: '%s'" %
                                     (value,))
                name = value[1:]

                yield ttype, self.params.register(name)
            else:
                yield ttype, value

        if debug_log:
            logger.debug('found %d params: %s',
                         len(self.params.names), repr(self.params.names))


def get_sqlparse_stack(params_register, get_macro):
    """
    Get an sqlparse filter stack for Cerebrum SQL.

    .. warning::
        The resulting filter stack is stateful -- it should only be used to
        parse a single statement!
    """
    stack = FilterStack()

    # Translate macros from Name to MacroToken -- must come first
    stack.preprocess.append(IdentifyMacroFilter())

    # Translate identified MacroToken values into valid SQL
    stack.preprocess.append(ProcessMacroFilter(get_macro))

    # TODO: Remove when we are sure no queries will fail
    stack.preprocess.append(_FindWhitespaceErrors(log=True, fix=True))

    # Translate placeholders into the proper paramstyle, and register
    # placeholder names.
    stack.preprocess.append(TranslatePlaceholderFilter(params_register))

    # NOTE: Do not enable grouping, it'll double the cost of stack.run().
    #
    #       Observe that other filters may *require* grouping -- using
    #       build_filter_stack may cause grouping to be enabled!
    # stack.enable_grouping()
    return stack


def format_statement(stmt):
    """ Format a sqlparse.sql.Statement into text """
    return ' '.join(six.text_type(s) for s in stmt.flatten())


def _translate(stmt, param_cls, get_macro):
    """
    A translate function for use with Dialect
    """
    params = param_cls()

    stack = get_sqlparse_stack(params, get_macro)

    # Serialize each statement into a string
    # NOTE: This may cause some issues with incorrectly formatted statements
    #       (missing whitespace surrounding e.g. macros in input stmt).
    #       Apparently the old translate function adds whitespace between
    #       *all* tokens.
    stack.postprocess.append(SerializerUnicode())

    statements = stack.run(stmt, None)
    statement = next(statements)

    # Check for additional statements, for two reasons:
    #
    # 1. If we have multiple statements, then something is probably very wrong!
    #    Cerebrum execute() calls should *only* have one statement, so we may
    #    have a(n) sql injection vuln.
    # 2. If we have multiple statements, our `params` object may have invalid
    #    data, as all statements have registered placeholders in the same
    #    object.
    try:
        second_statement = next(statements)
    except StopIteration:
        pass
    else:
        raise ValueError("Statement %r found after end of SQL statement." %
                         (second_statement,))

    return statement, params
