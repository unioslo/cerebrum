#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for cfg. """
import pytest
import re

from Cerebrum.config import settings

@pytest.fixture
def setting():
    s = settings.Setting(doc="Test", default="default")
    return s


def test_setting_default(setting):
    assert setting.get_value() == "default"


def test_setting_set(setting):
    setting.set_value("foo")
    assert setting.get_value() == "foo"


def test_setting_del(setting):
    setting.set_value("foo")
    assert setting.get_value() == "foo"
    setting.reset_value()
    assert setting.get_value() != "foo"


def test_setting_doc(setting):
    assert setting.doc.startswith(str(type(setting)))
    assert re.search("description: Test", setting.doc, flags=re.M)


@pytest.fixture
def numeric():
    s = settings.Numeric(doc="Numeric", minval=-0.5, maxval=9)
    s.set_value(5)
    return s


def test_numeric(numeric):
    assert numeric.get_value() == 5


def test_numeric_set(numeric):
    numeric.set_value(6)
    assert numeric.get_value() == 6
    numeric.set_value(-0.5)
    assert numeric.get_value() == -0.5
    numeric.set_value(9)
    assert numeric.get_value() == 9


def test_numeric_set_too_small(numeric):
    with pytest.raises(ValueError):
        numeric.set_value(-1)


def test_numeric_set_too_big(numeric):
    with pytest.raises(ValueError):
        numeric.set_value(10)


def test_numeric_del(numeric):
    numeric.reset_value()
    assert numeric.get_value() == settings.NotSet


def test_numeric_doc(numeric):
    assert numeric.doc.startswith(str(type(numeric)))
    assert re.search("types[^\n]+<type 'int'>", numeric.doc, flags=re.M)
    assert re.search("min[^-0-9\n]+-?[0-9]+", numeric.doc, flags=re.M)
    assert re.search("max[^-0-9\n]+-?[0-9]+", numeric.doc, flags=re.M)


def test_numeric_wrong_type(numeric):
    with pytest.raises(TypeError):
        numeric.set_value(None)
    with pytest.raises(TypeError):
        numeric.set_value("58")


def test_numeric_invalid_default():
    with pytest.raises(TypeError):
        settings.Numeric(default="string")


@pytest.fixture
def choice():
    s = settings.Choice(doc="Choice", choices=set((1, "foo")))
    s.set_value("foo")
    return s


def test_choice_get(choice):
    assert choice.get_value() == "foo"


def test_choice_set(choice):
    choice.set_value(1)
    assert choice.get_value() == 1


def test_choice_doc(choice):
    assert choice.doc.startswith(str(type(choice)))
    assert re.search("choices[^\n]+foo", choice.doc, flags=re.M)


def test_choice_invalid_choices():
    with pytest.raises(TypeError):
        settings.Choice(choices=[1, 2, 3])


def test_choice_invalid_default():
    with pytest.raises(ValueError):
        settings.Choice(choices=set((1, 2)), default=3)


@pytest.fixture
def string():
    s = settings.String(doc="String",
                        minlen=3,
                        maxlen=8,
                        regex='^Foo',
                        default='Foo')
    s.set_value('Foo bar')
    return s


def test_string_get(string):
    assert string.get_value() == 'Foo bar'


def test_string_get_default(string):
    string.reset_value()
    assert string.get_value() == 'Foo'


def test_string_set(string):
    string.set_value('Foo baz')
    assert string.get_value() == 'Foo baz'


def test_string_regex_error(string):
    with pytest.raises(ValueError):
        string.set_value('Bar baz')


@pytest.fixture
def iterable(string):
    s = settings.Iterable(string,
                          doc="Iterable",
                          min_items=1,
                          max_items=3,
                          default={'Foo', })
    s.set_value({'Foo', 'FooBar', })
    return s


def test_iterable_get(iterable):
    assert len(iterable.get_value()) == 2
    assert 'Foo' in iterable.get_value()
    assert 'FooBar' in iterable.get_value()


def test_iterable_get_default(iterable):
    iterable.reset_value()
    assert iterable.get_value() == ['Foo', ]


def test_iterable_set(iterable):
    iterable.set_value(['Foo', 'FooBar', 'FooBaz', ])
    assert iterable.get_value() == ['Foo', 'FooBar', 'FooBaz', ]


def test_iterable_set_too_few(iterable):
    with pytest.raises(ValueError):
        iterable.set_value(set())


def test_iterable_set_too_many(iterable):
    with pytest.raises(ValueError):
        iterable.set_value({'Foo1', 'Foo2', 'Foo3', 'Foo4', })


def test_iterable_set_invalid_item_value(iterable):
    with pytest.raises(ValueError):
        iterable.set_value({'Bar1', })
