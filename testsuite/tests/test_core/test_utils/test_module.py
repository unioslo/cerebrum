#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Unit tests for module utlities. """
from __future__ import print_function, unicode_literals

import pytest

from Cerebrum.utils.module import (
    this_module, import_item, parse, resolve, load_source)


def noop():
    pass


def test_this_module():
    assert this_module().__name__ == __name__


def test_import_item():
    assert import_item(__name__) == this_module()
    assert import_item(__name__, item_name='noop') == noop


def test_parse():
    with pytest.raises(ValueError):
        parse('')


def test_resolve():
    assert resolve(__name__) == this_module()


def test_load_source():
    this = load_source('foo', __file__)
    assert this.__name__ == 'foo'
    assert this.__file__ == __file__

    with pytest.raises(ImportError):
        load_source('bar', __file__ + '.nonexistent')
