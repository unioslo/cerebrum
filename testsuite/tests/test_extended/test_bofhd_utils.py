#!/usr/bin/env python
# -*- coding: utf-8 -*-
u""" Tests for Cerebrum.modules.bofhd.bofhd_utils """

import pytest


@pytest.fixture
def util_module():
    return pytest.importorskip('Cerebrum.modules.bofhd.bofhd_utils')


@pytest.fixture
def copy_func(util_module):
    return getattr(util_module, 'copy_func')


@pytest.fixture
def copy_command(util_module):
    return getattr(util_module, 'copy_command')


@pytest.fixture
def Src():
    class _cls(object):

        allstars = {
            'foo': 3,
            'bar': 2,
            'baz': 1,
        }

        def foo(self):
            return 'foo'

        @classmethod
        def bar(cls):
            return 'bar'

        @staticmethod
        def baz():
            return 'baz'

    return _cls


def test_copy_method(Src, copy_func):
    @copy_func(Src, methods=['foo', ])
    class Dest(object):
        pass

    assert Src().foo() == Dest().foo()


def test_copy_classmethod(Src, copy_func):
    @copy_func(Src, methods=['bar', ])
    class Dest(object):
        pass

    assert Dest.bar() == Src.bar()


def test_copy_staticmethod(Src, copy_func):
    @copy_func(Src, methods=['baz', ])
    class Dest(object):
        pass

    assert Dest.baz() == Src.baz()


def test_copy_multiple_times(Src, copy_func):
    @copy_func(Src, methods=['foo', ])
    @copy_func(Src, methods=['bar', ])
    class Dest(object):
        pass

    assert Dest.bar() == Src.bar()
    assert Src().foo() == Dest().foo()


def test_copy_multiple_methods(Src, copy_func):
    @copy_func(Src, methods=['foo', 'bar', 'baz'])
    class Dest(object):
        pass

    assert Src().foo() == Dest().foo()
    assert Dest.bar() == Src.bar()
    assert Dest.baz() == Src.baz()


def test_not_replace_method(Src, copy_func):
    class Dest(object):
        def foo(self):
            return self

    with pytest.raises(RuntimeError):
        copy_func(Src, methods=['foo', ])(Dest)


def test_copy_missing_method(Src, copy_func):
    class Dest(object):
        pass

    with pytest.raises(RuntimeError):
        copy_func(Src, methods=['i_dont_exist', ])(Dest)


def test_copy_command(Src, copy_command):
    @copy_command(Src, 'allstars', 'allstars', commands=['foo', ])
    class Dest(object):
        def foo(self):
            return 5

    assert len(getattr(Dest, 'allstars')) == 1
    assert 'foo' in Dest.allstars
    assert Dest.allstars['foo'] == Src.allstars['foo']


def test_copy_command_not_implemented(Src, copy_command):
    class Dest(object):
        pass

    with pytest.raises(RuntimeError):
        copy_command(Src, 'allstars', 'allstars', commands=['foo', ])(Dest)


def test_copy_command_multiple(Src, copy_command):
    @copy_command(Src, 'allstars', 'allstars', commands=['foo', 'bar', ])
    class Dest(object):
        foo = lambda *args: None
        bar = lambda *args: None

    assert len(getattr(Dest, 'allstars')) == 2
    assert 'foo' in Dest.allstars
    assert 'bar' in Dest.allstars


def test_copy_command_wrap_multiple(Src, copy_command):
    @copy_command(Src, 'allstars', 'allstars', commands=['foo', ])
    @copy_command(Src, 'allstars', 'allstars', commands=['bar', ])
    class Dest(object):
        allstars = {'bat': 5, }
        foo = lambda *args: None
        bar = lambda *args: None

    assert len(getattr(Dest, 'allstars')) == 3
    assert 'foo' in Dest.allstars
    assert 'bar' in Dest.allstars
    assert 'bat' in Dest.allstars


def test_copy_command_exists(Src, copy_command):
    class Dest(object):
        n = {'baz': 5, }
        foo = lambda *args: None
        bar = lambda *args: None

    with pytest.raises(RuntimeError):
        copy_command(Src, 'allstars', 'n', commands=['bar', 'baz', ])(Dest)
