# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.utils.filelock`

TODO: Figure out how to test error handling.  There probably needs to be some
PY3 refactoring here, as IOError is OSError on Python 3.  Probably easier to
trigger an OSError though (just try to write to a non-existing directory).

TODO: Figure out to test the timeout without actually introducing delays/sleeps
in the tests?
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os

import pytest

from Cerebrum.utils import filelock


# inherited conftest fixtures:
#
# - `write_dir` - a directory to write temporary files into (scope=module)
# - `new_file` - a non-existing filename in `write_dir`


def test_init_lock_without_type(new_file):
    with pytest.raises(filelock.LockError):
        with filelock.SimpleFlock(new_file, lock_type=None, timeout=0):
            # this should fail
            pass


def test_acquire_read_lock(new_file):
    # sanity check
    assert not os.path.exists(new_file)

    with filelock.ReadLock(new_file, timeout=0):
        assert os.path.exists(new_file)

    # lcok should be released
    assert not os.path.exists(new_file)


def test_read_lock_allows_read(new_file):
    with filelock.ReadLock(new_file, timeout=0):
        with filelock.ReadLock(new_file, timeout=0):
            # this should succeed
            pass
    assert True  # reached without error


def test_read_lock_denies_write(new_file):
    with filelock.ReadLock(new_file, timeout=0):
        with pytest.raises(filelock.LockError):
            with filelock.WriteLock(new_file, timeout=0):
                # this should fail
                pass


def test_acquire_write_lock(new_file):
    # sanity check
    assert not os.path.exists(new_file)

    with filelock.WriteLock(new_file):
        assert os.path.exists(new_file)

    # lcok should be released
    assert not os.path.exists(new_file)


def test_write_lock_denies_read(new_file):
    with filelock.WriteLock(new_file, timeout=0):
        with pytest.raises(filelock.LockError):
            with filelock.ReadLock(new_file, timeout=0):
                # this should fail
                pass


def test_write_lock_denies_write(new_file):
    with filelock.WriteLock(new_file, timeout=0):
        with pytest.raises(filelock.LockError):
            with filelock.WriteLock(new_file, timeout=0):
                # this should fail
                pass
