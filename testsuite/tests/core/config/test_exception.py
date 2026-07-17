# -*- coding: utf-8 -*-
""" Unit tests for :mod:`Cerebrum.config.errors`. """
import pytest
import six

from Cerebrum.config.errors import ConfigurationError


def test_error_init_empty():
    err = ConfigurationError()
    assert not err.errors


def test_error_init():
    error_map = {
        'foo': ValueError("invalid foo"),
        'bar': TypeError("invalid bar"),
    }
    err = ConfigurationError(error_map)
    assert len(err.errors) == 2
    assert err.errors['foo'] == error_map['foo']
    assert err.errors['bar'] == error_map['bar']


@pytest.fixture
def empty_error():
    err = ConfigurationError()
    return err


@pytest.fixture
def error():
    return ConfigurationError({'test': Exception("Test")})


def test_set_error(empty_error):
    empty_error.set_error('test', Exception("test"))
    assert 'test' in empty_error.errors


def test_get_error(error):
    assert 'test' in error.errors
    assert isinstance(error.errors['test'], Exception)


def test_len_config_error(empty_error, error):
    assert len(empty_error) == 0
    assert len(error) == 1


def test_bool_config_error(empty_error, error):
    assert not empty_error
    assert error


def test_add_error_from_error(error):
    error2 = ConfigurationError({'test': Exception("Test")})
    error.set_error('group', error2)
    assert 'test' in error.errors
    assert 'group.test' in error.errors


def test_str_config_error(error):
    strval = six.text_type(error)
    assert strval.startswith("Errors in ")


def test_repr_config_error(error):
    strval = repr(error)
    assert strval.startswith("ConfigurationError(")
