# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.apikeys.bofhd_apikey_cmds` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import timeit
import six

from Cerebrum.modules.bofhd import bofhd_debug_cmds
from Cerebrum.Errors import CerebrumError as GenericCerebrumError
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.database.errors import IntegrityError

@pytest.fixture
def commands(database, logger):
    return bofhd_debug_cmds.BofhdExtension(database, logger)


def test_bofhd_debug_raise_cerebrum_error(commands, superuser_session):
    with pytest.raises(GenericCerebrumError) as exception:
        commands.debug_raise_cerebrum_error(superuser_session, "Test Error")

    assert "Test Error" in six.text_type(exception.value)


def test_bofhd_debug_raise_bofhd_cerebrum_error(commands, superuser_session):
    with pytest.raises(CerebrumError) as exception:
        commands.debug_raise_bofhd_cerebrum_error(
            superuser_session, "Test Error")

    assert "Test Error" in six.text_type(exception.value)


def test_bofhd_debug_raise_exception_multiple_args(commands, superuser_session):
    with pytest.raises(bofhd_debug_cmds.ExceptionMultipleArgs) as exception:
        commands.debug_raise_exception_multiple_args(
            superuser_session, "Test Error", 10)

    assert "Test Error" in six.text_type(exception.value) and \
        "10" in six.text_type(exception.value)


def test_bofhd_debug_cause_integrity_error(commands, superuser_session):
    with pytest.raises(IntegrityError):
        commands.debug_cause_integrity_error(superuser_session)


def test_debug_wait(commands, superuser_session):
    start_time = timeit.default_timer()
    commands.debug_wait(superuser_session, sleep_seconds=1)
    elapsed = timeit.default_timer() - start_time
    assert elapsed >= 1 and elapsed < 2


testbytes = [
    b"abc123",
    u"abc123",
    u"abc123æøå",
]
@pytest.mark.parametrize("bytes", testbytes)
def test_debug_bytes(commands, superuser_session, bytes):
    result = commands.debug_bytes(superuser_session, bytes)

    assert result["type"] == repr(type(bytes))
    assert result["bytestring"] == bytes
    assert result["repr"] == repr(bytes)
    assert result["bytes"] == bytearray(u'abcæøå'.encode("utf-8"))

