#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for event mappings. """
import pytest


@pytest.fixture
def event_map():
    u""" The EventMap module to test. """
    module = pytest.importorskip('Cerebrum.modules.event.mapping')
    return getattr(module, 'EventMap')


@pytest.fixture
def test_cls(event_map):
    u""" EventMap used as an event handler class attribute. """
    class Test(object):

        eventmap = event_map()

        def handle(self, event):
            results = []
            for cb in self.eventmap.get_callbacks(event):
                results.append(cb(self, event))
            return results

        @eventmap('foo', 'bar')
        def foo(self, event):
            return ('foo', event)

        @eventmap('bar', 'baz')
        def bar(self, event):
            return ('bar', event)

        @eventmap('baz')
        def baz(self, event):
            return ('baz', event)
    return Test


def test_get_callbacks(test_cls):
    callbacks = test_cls.eventmap.get_callbacks('bar')
    assert len(callbacks) == 2
    for cb in callbacks:
        assert callable(cb)


def test_set_callback(event_map):
    lut = event_map()
    func = lambda n: n
    lut.add_callback('foo', func)
    assert len(lut.get_callbacks('foo')) == 1


def test_set_callback_error(event_map):
    lut = event_map()
    with pytest.raises(TypeError):
        lut.add_callback('key', 'not callable')


def test_handle(test_cls):
    t = test_cls()

    result = t.handle('foo')
    assert len(result) == 1
    assert ('foo', 'foo') in result
    result = t.handle('baz')
    assert len(result) == 2
    assert ('bar', 'baz') in result
    assert ('baz', 'baz') in result
