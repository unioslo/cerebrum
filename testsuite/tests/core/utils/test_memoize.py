#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2015 University of Oslo, Norway
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
""" Tests for Cerebrum.utils.funcwrap function wrappers. """

from Cerebrum.utils.funcwrap import memoize


class SomeClass(object):

    """ Example object. """

    def __init__(self, a_value):
        self._value = a_value

    @property
    def value(self):
        """ Get the object value. """
        return self._value

    @value.setter
    def value(self, a_value):
        """ Set the object value. """
        self._value = a_value

    @memoize
    def get_memoized_multiplied_value(self, factor):
        """ Get value multiplied by a factor. """
        return self.value * factor

    @memoize
    def get_memoized_value(self):
        """ Get value. """
        return self.value


def test_memoize_without_args():
    """ Checks that memoize works as expected for functions without args. """
    i = SomeClass(5)
    initial_value = i.get_memoized_value()
    i.value = 10
    memoized_value = i.get_memoized_value()
    assert initial_value == memoized_value


def test_memoize_with_args():
    """ Checks that memoize works as expected for functions with args. """
    i = SomeClass(5)
    i_10 = i.get_memoized_multiplied_value(10)
    assert i_10 == i.value * 10

    # Different factor, different result
    i_100 = i.get_memoized_multiplied_value(100)
    assert i_100 == i.value * 100

    # We change the internal value, but multiply with same argument as in i_10.
    # The product should be different (7 * 10), but we've already memoized the
    # result for multiplying with 10
    i.value = 7
    i_10_again = i.get_memoized_multiplied_value(10)
    assert i_10 == i_10_again


def test_memoize_per_object():
    """ Checks that memoize works as expected on object methods. """
    i = SomeClass(10)
    j = SomeClass(20)

    i_value = i.get_memoized_value()
    j_value = j.get_memoized_value()

    assert i_value != j_value
