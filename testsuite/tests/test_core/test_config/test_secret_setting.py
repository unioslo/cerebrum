# encoding: utf-8
""" Unit tests for settings type Secret. """
import re

import pytest

from Cerebrum.config import secrets


default_value = "plaintext:foo"
new_value = "plaintext:bar"


@pytest.fixture
def setting():
    return secrets.Secret(doc="Test", default=default_value)


def test_invalid_type(setting):
    """ Check that a TypeError is raised if set to a non-string. """
    with pytest.raises(TypeError):
        setting.set_value(32)


def test_invalid_format(setting):
    """ Check that a ValueError is raised if incorrect format is given. """
    with pytest.raises(ValueError):
        setting.set_value("foo")


def test_invalid_source(setting):
    """ Check that a ValueError is raised if set to an invalid source. """
    with pytest.raises(ValueError):
        setting.set_value("foo:bar")


def test_setting_default(setting):
    """ Check that the setting has a default value """
    assert setting.get_value() == default_value


def test_setting_set(setting):
    """ Check that a new value can be set. """
    setting.set_value(new_value)
    assert setting.get_value() == new_value


def test_setting_del(setting):
    """ Check that a new value can be reverted to the default. """
    setting.set_value(new_value)
    assert setting.get_value() == new_value
    setting.reset_value()
    assert setting.get_value() == default_value


def test_setting_doc(setting):
    """ Check that a the documentation includes our custom description. """
    assert setting.doc.startswith(str(type(setting)))
    assert re.search("description: Test", setting.doc, flags=re.M)


values = [
    "plaintext:hunter2",
    "file:/tmp/foo.txt",
    "auth-file:foo.txt",
    "legacy-file:user@foo",
]
sources = [v.split(':')[0] for v in values]


@pytest.mark.parametrize('value', values, ids=sources)
def test_valid_source(setting, value):
    """ Check that valid sources can be set. """
    setting.set_value(value)
    assert setting.get_value() == value
