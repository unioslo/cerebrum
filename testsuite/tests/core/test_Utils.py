#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Testing of Utils.py's functionality."""

import re
import sys

import pytest

import Cerebrum.Utils as Utils

# Data
messages_en_word = 'ynzwdpzm'
messages_no_word = 'llduloxr'
messages_dict = {'both_langs': {'en': messages_en_word,
                                'no': messages_no_word, },
                 'only_en':    {'en': messages_en_word, },
                 'only_no':    {'no': messages_no_word, },
                 'only_nn':    {'nn': messages_no_word, },
                 'none':       {}, }

# Helper functions


def noop():
    """ A simple no-op function. """
    pass


def raise1():
    """ Function to raise ValueError. """
    raise ValueError("raise1")


# Utils.format_exception_context
@pytest.mark.parametrize('args', ((), (None,), (None, None)))
def test_format_exception_context_wrong_args(args):
    """ Utils.format_exception_context with invalid arguments. """
    with pytest.raises(TypeError):
        Utils.format_exception_context(*args)


def test_format_exception_context_no_exc():
    """ Utils.format_exception_context with empty arguments. """
    retval = Utils.format_exception_context(None, None, None)
    assert retval == ''


def test_format_exception_context1():
    """ Utils.format_exception_context with valid arguments. """
    try:
        raise ValueError("ioshivfq")
    except ValueError:
        message = Utils.format_exception_context(*sys.exc_info())
        pattern = " ".join((
            "Exception",
            r"(?:<type 'exceptions.ValueError'>|<class 'ValueError'>)",
            r"occured \(in context.*:",
        ))
        assert re.search(pattern, message)
        assert "ioshivfq" in message


# Utils.exception_wrapper

def test_exception_wrapper_returns_callable():
    """ Utils.exception_wrapper returns callable. """
    assert hasattr(Utils.exception_wrapper(noop), '__call__')
    Utils.exception_wrapper(noop)()


@pytest.mark.parametrize('args', ((), (None,) * 5))
def test_exception_wrapper_arg_count(args):
    """ Utils.exception_wrapper with invalid arguments. """
    with pytest.raises(TypeError):
        Utils.exception_wrapper(*args)


def test_exception_wrapper_behaviour():
    """ Utils.exception_wrapper with valid arguments. """
    # Ignoring all exceptions with defaults always yields None
    assert Utils.exception_wrapper(noop, None)() is None
    # Ignoring the exception raised with defaults always yields None
    assert Utils.exception_wrapper(raise1, ValueError)() is None
    # Exceptions can be given as tuples ...
    assert Utils.exception_wrapper(raise1, (ValueError,))() is None
    # ... lists
    assert Utils.exception_wrapper(raise1, [ValueError, ])() is None
    # ... or sets without affecting the result
    assert Utils.exception_wrapper(raise1, set((ValueError,)))() is None

    # Exception not matching the spec are not caught
    with pytest.raises(ValueError):
        Utils.exception_wrapper(raise1, AttributeError)()

    # Return value with no exceptions is not altered
    assert Utils.exception_wrapper(noop, None, '')() is None
    # Return value with exceptions matches the arg
    assert Utils.exception_wrapper(raise1, ValueError, '')() == ''


# Utils.NotSet

def test_notset_single():
    """ Utils.NotSet comparison behaviour. """
    ns1 = Utils.NotSet
    ns2 = Utils.NotSet
    ns3 = Utils._NotSet()

    assert ns1 is ns2
    assert ns1 is ns3
    assert ns1 == ns2 == ns3
    assert not bool(ns1)


# Utils.dyn_import

def dyn_import_test():
    """ Utils.dyn_import puts modules in sys.modules. """

    for name in ("Cerebrum.Utils", "Cerebrum.modules", "Cerebrum.modules.no"):
        Utils.dyn_import(name)
        assert name in sys.modules

    x = "Cerebrum.modules.no"
    assert Utils.dyn_import(x) is sys.modules[x]


def test_argument_to_sql_droptables():
    """ Utils.argument_to_sql with Bobby Tables. """
    binds = {}
    name = "Robert'; DROP TABLE Students;--"
    sql = Utils.argument_to_sql(name, 'name', binds)
    assert sql == '(name = :name)'
    # This function should not sanitize. That's
    # for the transform to do:
    assert binds == {'name': name}


def test_argument_to_sql_transform():
    """ Utils.argument_to_sql with transform function. """
    binds = {}
    sql = Utils.argument_to_sql(None, 'foo', binds, type)
    assert sql == '(foo = :foo)'
    assert binds == {'foo': type(None)}


def test_argument_to_sql_sequence():
    """ Utils.argument_to_sql with sequence. """
    sequence = [1, 2, 3]
    for seq_type in (tuple, set, list):
        binds = {}
        sql = Utils.argument_to_sql(seq_type(sequence), 'foo', binds)
        assert sql == '(foo IN (:foo0, :foo1, :foo2))'
        assert binds == {'foo0': 1, 'foo1': 2, 'foo2': 3}
