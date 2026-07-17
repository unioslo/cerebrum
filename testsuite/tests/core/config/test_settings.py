#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for cfg. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import os
import re

import pytest
import six

from Cerebrum.config import settings


def test_notset_singleton():
    another_notset = settings.NotSetType()
    assert another_notset is settings.NotSet


def test_notset_bool():
    assert bool(settings.NotSet) is False


def test_notset_str():
    assert six.text_type(settings.NotSet) == "NotSet"


def test_notset_repr():
    assert repr(settings.NotSet) == "NotSet"


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
    assert re.search(r"description: Test", setting.doc, flags=re.M)


def test_setting_no_default():
    required_setting = settings.Setting(doc="Test")
    assert required_setting.get_value() is settings.NotSet


def test_setting_no_default_override():
    required_setting = settings.Setting(doc="Test")
    assert required_setting.get_value("foo") == "foo"


def test_setting_empty_allowed():
    """ Check that a default, empty value is valid. """
    setting = settings.Setting(doc="Test", default=None)
    setting.validate(None)
    assert True  # reached without exception


def test_setting_serialize(setting):
    """ Check that the default serializer is the identity function. """
    assert setting.serialize("foo") == "foo"


def test_setting_unserialize(setting):
    """ Check that the default deserializer is the identity function. """
    assert setting.unserialize("foo") == "foo"


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
    assert re.search(r"types: ", numeric.doc, flags=re.M)
    assert re.search(r"min[^-0-9\n]+-?[0-9]+", numeric.doc, flags=re.M)
    assert re.search(r"max[^-0-9\n]+-?[0-9]+", numeric.doc, flags=re.M)


def test_numeric_wrong_type(numeric):
    with pytest.raises(TypeError):
        numeric.set_value(None)
    with pytest.raises(TypeError):
        numeric.set_value("58")


def test_numeric_invalid_default():
    with pytest.raises(TypeError):
        settings.Numeric(default="string")


def test_numeric_empty_allowed():
    """ Check that a default, empty value is valid. """
    setting = settings.Numeric(doc="Test", default=None)
    setting.validate(None)
    assert True  # reached without exception


@pytest.fixture
def choice():
    s = settings.Choice(doc="Choice", choices=set((1, "foo")))
    s.set_value("foo")
    return s


def test_choice_get(choice):
    """ Check that we can get a choice setting value. """
    assert choice.get_value() == "foo"


def test_choice_set(choice):
    """ Check that we can set a valid choice value. """
    choice.set_value(1)
    assert choice.get_value() == 1


def test_choice_doc(choice):
    assert re.search(r"choices: ", choice.doc, flags=re.M)


def test_choice_invalid_choices():
    """ Check that the choice restriction must be correct type (set-like). """
    with pytest.raises(TypeError):
        # disallowing *lists* is a bit strict, maybe?
        settings.Choice(choices=[1, 2, 3])


def test_choice_invalid_default():
    """ Check that default values must be valid choices. """
    with pytest.raises(ValueError):
        settings.Choice(choices=set((1, 2)), default=3)


def test_choice_empty_warn():
    """ Check that having *no* choices issues a warning. """
    with pytest.warns(Warning):
        settings.Choice(doc="Choice")


@pytest.mark.filterwarnings("ignore:")
def test_choice_empty_never_valid():
    """ Check that no value is valid if there are no choices. """
    s = settings.Choice(doc="Choice")
    with pytest.raises(ValueError):
        s.validate("foo")


@pytest.mark.filterwarnings("ignore:")
def test_choice_empty_allowed():
    """ Check that a default, empty value is valid. """
    s = settings.Choice(doc="Choice", default=None)
    s.validate(None)
    assert True  # reached without exception


@pytest.fixture
def string():
    s = settings.String(doc="String",
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


def test_string_empty_allowed():
    """ Check that a default, empty value is valid. """
    setting = settings.String(doc="Test", default=None)
    setting.validate(None)
    assert True  # reached without exception


def test_string_minlen():
    """ Check that minlen is validated. """
    string = settings.String(doc="String", minlen=3)
    with pytest.raises(ValueError):
        string.set_value("a")


def test_string_maxlen():
    """ Check that maxlen is validated. """
    string = settings.String(doc="String", maxlen=3)
    with pytest.raises(ValueError):
        string.set_value("1234")


def test_string_len():
    """ Check that a valid length is allowed. """
    string = settings.String(doc="String", minlen=1, maxlen=3)
    string.set_value("12")


def test_string_doc():
    """ Check that a valid length is allowed. """
    string = settings.String(doc="String", minlen=1, maxlen=3, regex="^Foo")
    doc_struct = string.doc_struct
    assert doc_struct
    assert all(n in doc_struct for n in ('min length', 'max length', 'regex'))
    assert doc_struct['min length'] == 1
    assert doc_struct['max length'] == 3
    assert doc_struct['regex'] == "/^Foo/"


@pytest.fixture
def filepath(string):
    return settings.FilePath(doc="FilePath")


def test_filepath_empty_allowed():
    """ Check that a default, empty value is valid. """
    filepath = settings.FilePath(doc="Test", default=None)
    filepath.validate(None)
    assert True  # reached without exception


def test_filepath_always_optional(filepath):
    """ Check that an empty value is allowed even if required. """
    # TODO: This is probably not desired behaviour, but an artifact of a
    # previous bug/workaround.  Probably a setting was set as required (i.e.
    # without an empty, default value), when it actually was optional.
    filepath.validate(settings.NotSet)
    assert True  # reached without exception


def test_filepath_missing(tmpfile, filepath):
    """ Check that missing files are invalid values. """
    filepath = settings.FilePath(doc="Test")
    os.unlink(tmpfile)  # ensure file doesn't exist
    with pytest.raises(ValueError):
        filepath.validate(tmpfile)


def test_filepath_no_access_rules(tmpfile):
    """ Check that permissions doesn't matter without permission rules. """
    filepath = settings.FilePath(doc="Test")
    os.chmod(tmpfile, 0)  # no access to file
    filepath.validate(tmpfile)
    assert True  # reached without exception


def test_filepath_read_access(tmpfile):
    """ Check that readable files are valid when r-access is required. """
    filepath = settings.FilePath(doc="Test", permission_read=True)
    os.chmod(tmpfile, 0o400)  # read-only access
    filepath.validate(tmpfile)
    assert True  # reached without exception


def test_filepath_read_noaccess(tmpfile):
    """ Check that unreadable files are invalid when r-access is required. """
    filepath = settings.FilePath(doc="Test", permission_read=True)
    os.chmod(tmpfile, 0o200)  # write-only access
    with pytest.raises(ValueError):
        filepath.validate(tmpfile)


def test_filepath_write_access(tmpfile):
    """ Check that writable files are valid when w-access is required. """
    filepath = settings.FilePath(doc="Test", permission_write=True)
    os.chmod(tmpfile, 0o200)  # write-only access
    filepath.validate(tmpfile)
    assert True  # reached without exception


def test_filepath_write_noaccess(tmpfile):
    """ Check that unwritable files are invalid when w-access is required. """
    filepath = settings.FilePath(doc="Test", permission_write=True)
    os.chmod(tmpfile, 0o400)  # read-only access
    with pytest.raises(ValueError):
        filepath.validate(tmpfile)


def test_filepath_execute_access(tmpfile):
    """ Check that executable files are valid when x-access is required. """
    filepath = settings.FilePath(doc="Test", permission_execute=True)
    os.chmod(tmpfile, 0o100)  # execute-only access
    filepath.validate(tmpfile)
    assert True  # reached without exception


def test_filepath_execute_noaccess(tmpfile):
    """ Check that regular files are invalid when x-access is required. """
    filepath = settings.FilePath(doc="Test", permission_execute=True)
    os.chmod(tmpfile, 0o400)  # read-only access
    with pytest.raises(ValueError):
        filepath.validate(tmpfile)


def test_filepath_doc():
    """ Check that a default, empty value is valid. """
    filepath = settings.FilePath(doc="Test",
                                 permission_read=True,
                                 permission_write=True,
                                 permission_execute=True)
    assert filepath.doc_struct


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


def test_iterable_invalid_template():
    """ Check that iterable templates are restricted to Settings. """
    non_setting = object()
    with pytest.raises(TypeError):
        settings.Iterable(non_setting)


def test_iterable_empty_allowed(string):
    """ Check that a default, empty value is valid. """
    iterable = settings.Iterable(string, default=None)
    iterable.validate(None)
    assert True  # reached without exception


def test_iterable_doc_struct(string):
    """ Check that a default, empty value is valid. """
    iterable = settings.Iterable(string, min_items=1, max_items=3)
    doc_struct = iterable.doc_struct
    assert doc_struct
    assert all(n in doc_struct for n in ("template", "min items", "max items"))
    assert doc_struct['template'] == string.doc_struct
    assert doc_struct['min items'] == 1
    assert doc_struct['max items'] == 3


def test_iterable_serialize(iterable, string):
    value = ["foo", "bar"]
    assert iterable.serialize(value) == value
    assert iterable.serialize(value) is not value


def test_iterable_unserialize(iterable, string):
    value = ["foo", "bar"]
    assert iterable.unserialize(value) == value
    assert iterable.unserialize(value) is not value
