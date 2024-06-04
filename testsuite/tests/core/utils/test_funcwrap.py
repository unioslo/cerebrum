# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.utils.file_stream`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.utils import funcwrap


#
# test memoize
#


@pytest.fixture
def mem_cls():
    """ A class with some memoized methods. """

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

        @funcwrap.memoize
        def get_memoized_value(self):
            """ Get value. """
            return self.value

        @funcwrap.memoize
        def get_memoized_multiplied_value(self, factor):
            """ Get value multiplied by a factor. """
            return self.value * factor

    return SomeClass


def test_memoize_without_args(mem_cls):
    """ Checks that memoize works as expected for functions without args. """
    i = mem_cls(5)
    initial_value = i.get_memoized_value()
    i.value = 10
    memoized_value = i.get_memoized_value()
    assert initial_value == memoized_value


def test_memoize_with_args(mem_cls):
    """ Checks that memoize works as expected for functions with args. """
    i = mem_cls(5)
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


def test_memoize_per_object(mem_cls):
    """ Checks that memoize works as expected on object methods. """
    i = mem_cls(10)
    j = mem_cls(20)

    i_value = i.get_memoized_value()
    j_value = j.get_memoized_value()

    assert i_value != j_value


#
# test debug wrappers
#


def test_debug_call(capsys):

    @funcwrap.debug_call(args=True, ret=True, prefix="foo_module")
    def foo(*args, **kwargs):
        return str("retval")

    foo(1, False, bar=str("baz"))
    _, err = capsys.readouterr()
    lines = err.split("\n")
    print(err)

    # calls to bar() should print a header line + multiple lines of stack trace
    assert len(lines) > 1
    assert lines[0] == (
        "enter function foo_module.foo "
        "with args=(1, False) kwargs={'bar': 'baz'}"
    )
    assert lines[1] == (
        "exit function foo_module.foo with return='retval'"
    )


def test_trace_call(capsys):

    @funcwrap.trace_call(prefix="foo_module")
    def bar(*args):
        pass

    bar()
    _, err = capsys.readouterr()
    lines = err.split("\n")

    # calls to bar() should print a header line + multiple lines of stack trace
    assert len(lines) > 1
    assert lines[0] == "called foo_module.bar:"


#
# test deprecate
#


def test_deprecate():

    @funcwrap.deprecate("this is a test")
    def baz(*args):
        pass

    with pytest.deprecated_call():
        baz("something")
