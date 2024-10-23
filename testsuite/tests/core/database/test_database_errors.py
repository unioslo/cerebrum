# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.database.errors`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap
import types

import pytest
import six

from Cerebrum.database import errors


class _MockModule(types.ModuleType):
    Warning = type(str("Warning"), (Exception,), {})
    Error = type(str("Error"), (Exception,), {})

    DataError = type(str("DataError"), (Error,), {})
    DatabaseError = type(str("DatabaseError"), (Error,), {})
    IntegrityError = type(str("IntegrityError"), (Error,), {})
    InterfaceError = type(str("InterfaceError"), (Error,), {})
    InternalError = type(str("InternalError"), (Error,), {})
    NotSupportedError = type(str("NotSupportedError"), (Error,), {})
    OperationalError = type(str("OperationalError"), (Error,), {})
    ProgrammingError = type(str("ProgrammingError"), (Error,), {})

    NonApiError = type(str("NonApiError"), (Exception,), {})


db_module = _MockModule(str("db_module"))


@pytest.fixture
def wrapper():
    def _helper(**extras):
        return errors.DatabaseErrorWrapper(errors, db_module, **extras)
    return _helper


def test_database_error_wrapper_init(wrapper):
    ctx = wrapper(foo=1, bar="bar")
    assert ctx.to_module is errors
    assert ctx.from_module is db_module
    assert ctx.extra_attrs == {'foo': repr(1), 'bar': repr("bar")}


@pytest.mark.parametrize(
    "name",
    (
        "NotSupportedError",
        "ProgrammingError",
        "InternalError",
        "IntegrityError",
        "OperationalError",
        "DataError",
        "DatabaseError",
        "InterfaceError",
        "Error",
        "Warning",
    )
)
def test_database_error_wrapper_reraise(wrapper, name):
    """ check that our wrapper processes all db-api exception names. """
    expected = getattr(errors, name)
    to_raise = getattr(db_module, name)

    with pytest.raises(expected) as exc_info:
        with wrapper():
            raise to_raise("message")

    assert exc_info.type is expected
    assert six.text_type(exc_info.value) == "message"


def test_database_error_wrapper_attrs(wrapper):
    """ check that our wrapper can apply extra attributes to exceptions. """
    expected = errors.Error
    to_raise = db_module.Error

    with pytest.raises(expected) as exc_info:
        with wrapper(foo=1, bar="bar"):
            raise to_raise("message")

    assert exc_info.type is expected
    exc = exc_info.value
    assert exc.foo == repr(1)
    assert exc.bar == repr("bar")


def test_database_error_wrapper_miss(wrapper):
    """ check that our wrapper only processes db-api exception names. """
    raise_type = db_module.NonApiError
    raise_value = raise_type("message")

    with pytest.raises(raise_type) as exc_info:
        with wrapper(foo=1, bar="bar"):
            raise raise_value

    exc = exc_info.value
    assert exc is raise_value
    assert not hasattr(exc, "foo")
    assert not hasattr(exc, "bar")


def test_database_error_wrapper_ok(wrapper):
    """ check that our wrapper works when nothing happens. """
    value = False
    with wrapper(foo=1, bar="bar"):
        value = True
    assert value


def test_database_error_wrapper_funcwrap(wrapper):
    """ check that our exception wrapper can be a function wrapper. """
    @wrapper()
    def my_func():
        raise db_module.Error

    with pytest.raises(errors.Error):
        my_func()


def test_database_error_msg():
    exc = errors.Error("hello")
    msg = six.text_type(exc)
    assert msg == "hello"


def test_database_error_msg_details():
    exc = errors.Error("hello")
    exc.operation = "cerebrum-operation"
    exc.parameters = "cerebrum-params"
    exc.sql = "sql-statement"
    exc.binds = "sql-binds"
    exc.unknown = "unknown-attribute"
    msg = six.text_type(exc)
    assert msg == textwrap.dedent(
        """
        hello
        operation=cerebrum-operation
        sql=sql-statement
        parameters=cerebrum-params
        binds=sql-binds
        """
    ).strip()
