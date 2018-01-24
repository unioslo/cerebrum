# -*- coding: utf-8 -*-
import pytest


@pytest.fixture
def error_cls():
    from Cerebrum.config.errors import ConfigurationError
    return ConfigurationError


@pytest.fixture
def empty_error(error_cls):
    err = error_cls()
    return err


@pytest.fixture
def error(error_cls):
    err = error_cls()
    err.set_error('test', Exception("Test"))
    return err


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


def test_add_error_from_error(error_cls, error):
    error2 = error_cls()
    error2.set_error('test', Exception("Test"))
    error.set_error('group', error2)
    assert 'test' in error.errors
    assert 'group.test' in error.errors
