# -*- coding: utf-8 -*-
# Copyright 2002-2018 University of Oslo, Norway
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
""" SqlScanner is a SQL lexer for the database module.

This module is used for:
- counting/separating statements (can be used to prevent certain sql injection)
- translating paramformat from 'named' to whatever the database driver uses.
- TODO: more?

History
-------
`_translate` was extracted from ``Cerebrum.database.Cursor._translate``.

The refactor was done to accommodate other lexers than Cursor._translate, which
used SqlScanner.  The original translate function can be seen in:

    commit: f8d149dbb21cdbf10724b60b6d1c613ebc951b5f
    Merge:  3e4c07061 be7c05022
    Date:   Tue Feb 11 11:42:09 2020 +0100
"""
from __future__ import print_function

import io

from Cerebrum.extlib import Plex

from .errors import ProgrammingError
from .macros import parse_macro_args


# Define names of tokens returned by the scanner.

# SQL keyword or object name.  Text returned: The word that was found,
# e.g. 'select' or 'employee'.
SQL_WORD = 'word'

# Non-alphanumeric SQL operator, e.g. '<>' or '='.  Text returned: The
# operator.
SQL_OPERATOR = 'op'

# SQL special characters, like '*', '.' or ','.  Text returned: The
# special character.
SQL_SPECIAL_CHAR = 'special'

# Bind parameter.  The SqlScanner class understands the 'named'
# paramstyle.  Returned text: The bind parameter, e.g. ':emp_id'.
SQL_BIND_PARAMETER = 'bpar'

# SQL portability function.  Text returned: The name of the
# portability function, e.g. 'table'.
SQL_PORTABILITY_FUNCTION = 'p_func'

# SQL portability argument.  Text returned: 'key=value',
# e.g. 'name=employee'.
SQL_PORTABILITY_ARG = 'p_arg'

# End of statement character.  Text returned: ';'.
SQL_END_OF_STATEMENT = 'stmt_end'

# Opening and closing parenthesis.  Text returned: '(' or ')',
# i.e. the actual parenthesis that was found.
SQL_OPEN_PAREN = 'open_paren'
SQL_CLOSE_PAREN = 'close_paren'

# Decimal integer, with optional prefix sign.  Text returned: The
# integer (as a string).
SQL_INTEGER_LITERAL = 'decimal'

# Floating-point number literal.  Text returned: The literal, as a
# string.
SQL_FLOAT_LITERAL = 'float'

# SQL string literal.  Text returned: The string, with single quotes
# and SQL quote escaping intact; e.g. "'It''s truly a string
# literal!'"
SQL_STRING_LITERAL = 'string'


class SqlScanner(Plex.Scanner):

    def __init__(self, file):
        # TBD: Plex doesn't use new-style classes, can't use super().
        # super(SqlScanner, self).__init__(self.lexicon, file)
        Plex.Scanner.__init__(self, self.lexicon, file)
        self.paren_nesting_level = 0

    def open_paren_action(self, text):
        self.paren_nesting_level += 1
        return SQL_OPEN_PAREN

    def close_paren_action(self, text):
        self.paren_nesting_level -= 1
        return SQL_CLOSE_PAREN

    def statement_end_action(self, text):
        assert self.paren_nesting_level == 0
        return SQL_END_OF_STATEMENT

    def eof(self):
        assert self.paren_nesting_level == 0

    spaces = Plex.Rep1(Plex.Any(" \f\t\n"))
    _letter = Plex.Range("AZaz") | Plex.Any("_")
    _digit = Plex.Range("09")
    _sign = Plex.Any("+-")
    _number = Plex.Rep1(_digit)
    integer = Plex.Opt(_sign) + _number
    _exponent = Plex.Any("Ee") + integer
    float = Plex.Opt(_sign) + (
        (_number + _exponent)
        | (_number + Plex.Any(".") + Plex.Rep(_digit) + Plex.Opt(_exponent))
        | (Plex.Any(".") + _number + Plex.Opt(_exponent)))
    name = _letter + Plex.Rep(_letter | _digit)
    stringlit = (
        Plex.Str("'")
        + Plex.Rep(
            Plex.AnyBut("'")
            # Quotes inside SQL strings are escaped by doubling
            # them.
            | Plex.Str("''"))
        + Plex.Str("'"))
    value = integer | float | name | stringlit
    open_paren = Plex.Any("(")
    close_paren = Plex.Any(")")
    punctuation = Plex.Any(",.*")
    bind_var = Plex.Str(':') + name
    statement_end = Plex.Any(";")
    operator = Plex.Str("+", "-", "*", "/", "||", "=", "<", "<=", ">", ">=",
                        "<>", "!=")

    lexicon = Plex.Lexicon([
        (name, SQL_WORD),
        (integer, SQL_INTEGER_LITERAL),
        (float, SQL_FLOAT_LITERAL),
        (stringlit, SQL_STRING_LITERAL),
        (bind_var, SQL_BIND_PARAMETER),
        (operator, SQL_OPERATOR),
        (punctuation, SQL_SPECIAL_CHAR),
        (spaces, Plex.IGNORE),
        (open_paren, open_paren_action),
        (close_paren, close_paren_action),
        (statement_end, statement_end_action),
        (Plex.Str("--") + Plex.Rep(Plex.AnyBut("\n")), Plex.IGNORE),
        (Plex.Str("/*"), Plex.Begin('c_comment')),
        Plex.State('c_comment', [(Plex.Str("*/"), Plex.Begin('')),
                                 (Plex.AnyChar, Plex.IGNORE)]),
        (Plex.Str('[:'), Plex.Begin('sql_portability')),
        Plex.State(
            'sql_portability',
            [(Plex.Str(']'), Plex.Begin('')),
             (name + Plex.Str('=') + value, SQL_PORTABILITY_ARG),
             (name, SQL_PORTABILITY_FUNCTION),
             (spaces, Plex.IGNORE)
             ])
    ])

    def __iter__(self):
        return self

    def next(self):
        token, text = ret = self.read()
        if token is None:
            raise StopIteration
        return ret


def _translate(stmt, param_cls, get_macro):
    """
    :param stmt: The original sql statement
    :param param_cls:
        a ``paramstyles.Base`` subclass to use for registering placeholder
        names.
    :param get_macro:
        a ``macros.MacroTable`` like callable to translate macros.

    :return:
        Returns a tuple with a translated sql statement, and a callable that
        translates a binds dict into the appropriate value (bind dict, bind
        tuple)
    """
    out_sql = []
    params = param_cls()

    def parse_macro(parts):
        op = parts[0]
        args = parse_macro_args(' '.join(parts[1:]))
        return get_macro(op, args)

    done = False
    macro_parts = None

    for token, text in SqlScanner(io.StringIO(stmt)):
        translation = []
        if done:
            # token found after end-of-statement indicator
            raise ProgrammingError(
                "Token '%s' found after end of SQL statement." % text)

        if macro_parts:
            # We're in the middle of parsing an SQL portability
            # item; collect all of the item's arguments before
            # trying to translate it into the SQL dialect of this
            # Cursor's database backend.
            if token == SQL_PORTABILITY_ARG:
                macro_parts.append(text)
                continue
            else:
                # We've got all the portability item's arguments;
                # translate them into a set of SQL tokens.
                translation.append(parse_macro(macro_parts))
                # ... and indicate that we're no longer collecting
                # arguments for a portability item.
                macro_parts = None

        if token == SQL_END_OF_STATEMENT:
            done = True
        elif token == SQL_PORTABILITY_FUNCTION:
            # Set `macro_parts' to indicate that we should start
            # collecting portability item arguments.
            macro_parts = [text]
        elif token == SQL_BIND_PARAMETER:
            # The name of the bind variable is the token without
            # any preceding ':'.
            name = text[1:]
            translation.append(params.register(name))
        else:
            translation.append(text)

        if translation:
            out_sql.extend(translation)

    # If the input statement ended with a portability token, no
    # non-portability tokens has triggered inclusion of the final macro_parts
    if macro_parts:
        out_sql.append(parse_macro(macro_parts))
        macro_parts = None

    return " ".join(out_sql), params


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 2:
        f = open(sys.argv[1], "r")
    else:
        f = sys.stdin
    stmt = []
    for token, text in SqlScanner(f):
        if not text or token == text:
            value = token
        else:
            value = "%s(%s)" % (token, repr(text))
        print(value)
        stmt.append(text)
        if token == SQL_END_OF_STATEMENT:
            print(" ".join(stmt))
            stmt = []
    # If we found any tokens after the last SQL_END_OF_STATEMENT, we
    # should print these, too.
    if stmt:
        print("Tokens found after last SQL_END_OF_STATEMENT:\n\t",
              " ".join(stmt))
