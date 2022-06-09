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

- Move py:func:`Cerebrum.Utils.argument_to_sql` here
- Replace use of py:func:`Cerebrum.Utils.prepare_string` with
  py:class:`.Pattern`.
- Replace use of py:func:`Cerebrum.database.Database.sql_pattern` with
  py:class:`.Pattern`.
"""
from Cerebrum.utils import reprutils


def _int_or_none(value):
    if value is None:
        return None
    return int(value)


class _Range(object):
    """
    Abstract range (lower/upper limits).
    """
    def __init__(self, gt=None, ge=None, lt=None, le=None):
        gt = self._convert(gt)
        ge = self._convert(ge)
        if gt is not None and ge is not None:
            raise ValueError('invalid range: gt/ge is incompatible')

        self.start = ge if gt is None else gt
        self.start_inclusive = gt is None

        lt = self._convert(lt)
        le = self._convert(le)
        if lt is not None and le is not None:
            raise ValueError('invalid ranle: lt/le is incompatible')

        self.stop = le if lt is None else lt
        self.stop_inclusive = lt is None

        if all(i is None for i in (self.start, self.stop)):
            raise ValueError('invalid range: must provide a limit')

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

    >>> Pattern(r"Foo-*" case_sensitive=False).sql_pattern('col', 'ref')
    ("col ILIKE :ref", {'ref': r'Foo-%'})

    >>> Pattern(r"% _").sql_pattern('col', 'ref')
    ("col LIKE :ref", {'ref': r'\% \_})

    >>> Pattern(r"* ?").sql_pattern('col', 'ref')
    ("col LIKE :ref", {'ref': r'% _'})

    >>> Pattern(r"\* \?").sql_pattern('col', 'ref')
    ("col LIKE :ref", {'ref': r'? *'})
    """

    repr_id = False
    repr_module = False
    repr_fields = ('pattern', 'case_sensitive')

    TOKEN_STRING = 'string'
    TOKEN_WILDCARD = 'wildcard'

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

            if char == '*':
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
        wildcards = {'*': '%', '?': '_'}
        return ''.join(wildcards[value]
                       if token == self.TOKEN_WILDCARD
                       else value.replace('%', '\\%').replace('_', '\\_')
                       for token, value in self._tokens)

    def get_sql_select(self, colname, ref):
        """
        Get SQL matching rule for this pattern.

        >>> Pattern('ba?-*', False).get_sql_select('my_t.my_col', 'my_val')
        ('my_t.my_col ILIKE :my_val', {'my_val': 'ba_-%'})

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
