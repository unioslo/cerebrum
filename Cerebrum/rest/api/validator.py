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
""" Simple input validation and transform utils.

The transform `Chain` can typically be used in e.g. argparse to validate and
process a a value.

>>> foo = Chain()
>>> foo.add(Integer(min_val=1, max_val=3))

Rules can transform the input:
>>> print foo('2')
2
>>> foo('foo')
Traceback (most recent call last):
    ...
TypeError: Invalid integer 'foo'

Rules can validate input:
>>> foo(0)
Traceback (most recent call last):
    ...
ValueError: value is too small (actual=0, min=1)


TODO: Replace this module with the `webargs` package.

"""


class Chain(object):

    def __init__(self):
        self.rules = []

    def __call__(self, value):
        for rule in self.rules:
            value = rule(value)
        return value

    def add(self, rule):
        """ Add validator/transformator.

        :param callable rule:
            Any callable that accepts one argument, and returns one value.
        """
        assert callable(rule)
        self.rules.append(rule)


class String(object):
    """ String transform and validation. """

    def __init__(self, min_len=0, max_len=None, trim=False):
        """
        :param int min_len: Minimum string length.
        :param int max_len: Maximum string length.
        :param bool trim: Trim value.
        """
        self.min_len = min_len
        self.max_len = max_len
        self.trim = trim

    def __call__(self, value):
        value = unicode(value)
        if self.trim:
            value = value.strip()
        l = len(value)
        if l < self.min_len:
            raise ValueError(
                "value is too short (actual={:d}, min={:d})".format(
                    l, self.min_len))
        if self.max_len is not None and l > self.max_len:
            raise ValueError(
                "value is too long (actual={:d}, max={:d})".format(
                    l, self.max_len))
        return value


class Integer(object):
    """ Integer transform and validation. """

    def __init__(self, min_val=None, max_val=None):
        """
        :param int min_len: Minimum value.
        :param int max_len: Maximum value.
        """
        self.min_val = min_val
        self.max_val = max_val

    def __call__(self, value):
        try:
            value = int(value)
        except ValueError:
            raise TypeError("Invalid integer {!r}".format(value))
        if self.min_val is not None and value < self.min_val:
            raise ValueError(
                "value is too small (actual={:d}, min={:d})".format(
                    value, self.min_val))
        if self.max_val is not None and value > self.max_val:
            raise ValueError(
                "value is too big (actual={:d}, max={:d})".format(
                    value, self.max_val))
        return value
