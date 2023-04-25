# -*- coding: utf-8 -*-
#
# Copyright 2022 University of Oslo, Norway
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
Utilities for generating database expressions and preparing parameters.

TODO
----

- Move :func:`Cerebrum.Utils.argument_to_sql` here

- Replace use of :func:`Cerebrum.Utils.prepare_string` with
  :class:`.Pattern`

- Replace use of :func:`Cerebrum.database.Database.sql_pattern` with
  :class:`.Pattern`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import six

from Cerebrum.Utils import NotSet, argument_to_sql
from Cerebrum.utils import reprutils


def _not_none(value):
    """
    Check that value is not None/NotSet.

    This is typically used as transform-callback in
    ``argument_to_sql`` if no other transforms are suitable.
    """
    if value is None:
        raise ValueError("unexpected None-value")
    if value is NotSet:
        raise ValueError("unexpected NotSet-value")
    return value


class _Range(object):
    """
    Abstract range (lower/upper limits).

    Note that if both a gt/ge and a lt/le is given, then the two
    values must be comparable.
    """
    def __init__(self, gt=None, ge=None, lt=None, le=None):
        gt = self._convert(gt)
        ge = self._convert(ge)
        if gt is not None and ge is not None:
            raise TypeError('invalid range: gt/ge is incompatible')

        self.start = ge if gt is None else gt
        self.start_inclusive = gt is None

        lt = self._convert(lt)
        le = self._convert(le)
        if lt is not None and le is not None:
            raise TypeError('invalid range: lt/le is incompatible')

        self.stop = le if lt is None else lt
        self.stop_inclusive = lt is None

        if all(i is None for i in (self.start, self.stop)):
            raise TypeError('invalid range: must provide a limit')

        if (self.start is not None
                and self.stop is not None
                and self.start > self.stop):
            raise ValueError('invalid range: start >= stop')

    def __repr__(self):
        pairs = []
        if self.start is not None:
            pairs.append(('ge' if self.start_inclusive else 'gt', self.start))
        if self.stop is not None:
            pairs.append(('le' if self.stop_inclusive else 'lt', self.stop))
        pretty = ' '.join(attr + '=' + repr(value) for attr, value in pairs)
        return '<{name} {fields}>'.format(name=type(self).__name__,
                                          fields=pretty)

    def _convert(self, value):
        if value is None:
            return None
        return value

    def get_sql_select(self, colname, ref):
        binds = {}
        conds = []
        ref_start = ref + '_start'
        ref_stop = ref + '_stop'

        if self.start is not None:
            start_op = '>=' if self.start_inclusive else '>'
            conds.append('{} {} :{}'.format(colname, start_op, ref_start))
            binds[ref_start] = self.start
        if self.stop is not None:
            stop_op = '<=' if self.stop_inclusive else '<'
            conds.append('{} {} :{}'.format(colname, stop_op, ref_stop))
            binds[ref_stop] = self.stop
        return '({})'.format(' AND '.join(conds)), binds


class NumberRange(_Range):

    def _convert(self, value):
        if value is None:
            return None
        return int(value)


# class DateRange(_Range):
#     pass


# class DatetimeRange(_Range):
#     pass


class Pattern(reprutils.ReprFieldMixin):
    r"""
    Simplified Cerebrum pattern matching.

    The Cerebrum user input pattern is a simple glob-like pattern:

    - '*' matches zero or more characters
    - '?' matches a single character
    - '\*' matches a literal '*'
    - '\?' matches a literal '?'
    - '\\' matches a literal '\'


    To query database using Pattern:

    >>> Pattern(r"Foo-*", case_sensitive=False).get_sql_select('col', 'ref')
    ('(col ILIKE :ref)', {'ref': 'Foo-%'})

    >>> Pattern(r"% _").get_sql_select('col', 'ref')
    ('(col LIKE :ref)', {'ref': '\\% \\_'})

    >>> Pattern(r"* ?").get_sql_select('col', 'ref')
    ('(col LIKE :ref)', {'ref': '% _'})

    >>> Pattern(r"\* \?").get_sql_select('col', 'ref')
    ('(col LIKE :ref)', {'ref': '* ?'})
    """

    repr_id = False
    repr_module = False
    repr_fields = ('pattern', 'case_sensitive')

    TOKEN_STRING = 'string'
    TOKEN_WILDCARD = 'wildcard'
    WILDCARDS = {
        '*': '%',
        '?': '_',
    }

    @classmethod
    def _sql_escape(cls, value):
        for char in cls.WILDCARDS.values():
            value = value.replace(char, '\\' + char)
        return value

    @classmethod
    def tokenize(cls, pattern, escape='\\'):
        """ tokenize input pattern.

        Tokenizes the cerebrum pattern.  The un-escaped '*' and '?' are the
        only possible matches for the 'wildcard' token.

        :param pattern:
            A pattern (e.g. `ba?-*`)

        :rtype: generator
        :returns:
            yields pairs of <token-type>, <token-string>
        """
        buffer = ''
        is_escaped = False
        for charno, char in enumerate(pattern, 1):
            if is_escaped:
                buffer += char
                is_escaped = False
                continue

            if char == escape:
                is_escaped = True
                continue

            if char in cls.WILDCARDS:
                if buffer:
                    yield cls.TOKEN_STRING, buffer
                yield cls.TOKEN_WILDCARD, char
                buffer = ''
            else:
                buffer += char
        if is_escaped:
            # the last character was an un-escaped escape
            raise ValueError('invalid pattern (%d): %s' %
                             (charno, repr(pattern)))
        if buffer:
            yield cls.TOKEN_STRING, buffer

    @classmethod
    def dwim(cls, pattern):
        """
        Get a new pattern that auto selects case sensitivity.

        DWIM - Do What I Mean - sets case_sensitive=True if the pattern
        contains upper case characters.
        """
        return cls(pattern, pattern != pattern.lower())

    def __init__(self, pattern, case_sensitive=True):
        """
        :param pattern: A simple cerebrum search pattern.
        :param case_sensitive: If case sensitive matching should be used
        """
        self._raw_pattern = pattern
        self._tokens = tuple(self.tokenize(pattern))
        self.case_sensitive = case_sensitive

    @property
    def pattern(self):
        """ input pattern, as provided. """
        return self._raw_pattern

    @property
    def tokens(self):
        """ tokenized tuples. """
        return self._tokens

    @property
    def sql_pattern(self):
        """ sql LIKE/ILIKE formatted pattern string. """
        return ''.join(self.WILDCARDS[value]
                       if token == self.TOKEN_WILDCARD
                       else self._sql_escape(value)
                       for token, value in self._tokens)

    def get_sql_select(self, colname, ref):
        """
        Get SQL matching rule for this pattern.

        >>> Pattern('ba?-*', False).get_sql_select('my_t.my_col', 'my_val')
        ('(my_t.my_col ILIKE :my_val)', {'my_val': 'ba_-%'})

        :param colname: the column name to match
        :param ref: the binding name to use

        :rtype: tuple
        :returns:
            A tuple with: (<sql expression str>, <bindings dict>)
        """
        op = 'LIKE' if self.case_sensitive else 'ILIKE'
        cond = '({} {} :{})'.format(colname, op, ref)
        binds = {ref: self.sql_pattern}
        return cond, binds


def pattern_helper(colname,
                   value=NotSet,
                   case_pattern=None,
                   icase_pattern=None,
                   nullable=False):
    """
    Helper to prepare a string column query condition.

    Helps to generate conditions for matching exact string values, string
    patterns, or NULL.

    >>> pattern_helper("foo", ("bar", "baz"), None, "bar baz*")
    (
        "(foo IN (:foo0, :foo1) OR foo ILIKE :foo_i_pattern)",
        {'foo0': 'bar', 'foo1': 'baz', 'foo_i_pattern': 'bar baz%'},
    )

    >>> pattern_helper("x.foo", None, "*Bar?", nullable=True)
    (
        "(x.foo IS NULL OR x.foo LIKE :x_foo_c_pattern)",
        {'x_foo_c_pattern': '%Bar_'}
    )

    :param str colname: column name (with prefix, e.g. "en.entity_name")
    :param str value: value check (sequence of strings, string, None, NotSet)
    :param str case_pattern: case-sensitive pattern
    :param str icase_pattern: case-insensitive pattern
    :param bool nullable:
        If True, a (column IS NULL) OR-condition is added when `value is None`.
        This is usually what you want if the column allows NULL-values.
    """
    conds = []
    binds = {}

    if nullable and value is None:
        conds.append("{} IS NULL".format(colname))

    elif value is not None and value is not NotSet:
        conds.append(
            argument_to_sql(value, colname, binds, six.text_type))

    bind_like = colname.replace('.', '_') + '_c_pattern'
    bind_ilike = colname.replace('.', '_') + '_i_pattern'

    # case-sensitive pattern
    if case_pattern:
        c_pattern = Pattern(case_pattern, case_sensitive=True)
        c_cond, c_bind = c_pattern.get_sql_select(colname, bind_like)
        conds.append(c_cond)
        binds.update(c_bind)

    # case-insensitive pattern
    if icase_pattern:
        i_pattern = Pattern(icase_pattern, case_sensitive=False)
        i_cond, i_bind = i_pattern.get_sql_select(colname, bind_ilike)
        conds.append(i_cond)
        binds.update(i_bind)

    if len(conds) > 1:
        return '({})'.format(' OR '.join(conds)), binds
    elif conds:
        return conds[0], binds
    return None, {}


def date_helper(colname, value=NotSet, gt=None, ge=None, lt=None, le=None,
                nullable=False):
    """
    Helper to prepare a date/timestamp column query condition.

    Helps to generate conditions for matching exact date/datetime values,
    date/datetime ranges, or NULL.

    >>> a, b, c = (datetime.date(2023, 4, i) for i in (15, 17, 19))
    >>> date_helper("foo", (a, b), ge=c)
    (
        '((foo IN (:foo0, :foo1)) OR (foo >= :foo_range_start))',
        {'foo0': datetime.date(2023, 4, 15),
         'foo1': datetime.date(2023, 4, 17),
         'foo_range_start': datetime.date(2023, 4, 19)})

    >>> date_helper("foo", None, gt=a, lt=b)
    (
        '(foo > :foo_range_start AND foo < :foo_range_stop)',
        {'foo_range_start': datetime.date(2023, 4, 15),
         'foo_range_stop': datetime.date(2023, 4, 17)})

    :param str colname: column name (with prefix, e.g. "en.entity_name")
    :param value: value check (sequence of dates, date, None, NotSet)
    :param gt/ge: add range start condition (exclusive/inclusive)
    :param lt/le: add range end condition (exclusive/inclusive)
    :param bool nullable:
        If True, a (column IS NULL) OR-condition is added when `value is None`.
        This is usually what you want if the column allows NULL-values.
    """
    conds = []
    binds = {}

    if nullable and value is None:
        conds.append("{} IS NULL".format(colname))

    if value is not None and value is not NotSet:
        conds.append(
            argument_to_sql(value, colname, binds, _not_none))

    if any((lt, le, gt, ge)):
        bind_prefix = colname.replace('.', '_') + '_range'
        date_range = _Range(gt=gt, ge=ge, lt=lt, le=le)
        r_cond, r_bind = date_range.get_sql_select(colname, bind_prefix)
        conds.append(r_cond)
        binds.update(r_bind)

    if len(conds) > 1:
        return '({})'.format(' OR '.join(conds)), binds
    elif conds:
        return conds[0], binds
    return None, {}
