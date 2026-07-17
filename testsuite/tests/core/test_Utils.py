# -*- coding: utf-8 -*-
""" Unit tests for :mod:`Cerebrum.Utils` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import sys

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
