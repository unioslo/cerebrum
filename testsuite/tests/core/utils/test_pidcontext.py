# -*- coding: utf-8 -*-
"""
Unit tests for mod:`Cerebrum.utils.pidcontext`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import logging
import os
import shutil
import tempfile

import pytest

from Cerebrum.utils import pidcontext


@pytest.fixture
def lockfile_dir(write_dir):
    dirname = tempfile.mkdtemp(dir=write_dir)
    yield dirname
    shutil.rmtree(dirname)


@pytest.fixture
def piddir(write_dir):
    dirname = tempfile.mkdtemp(dir=write_dir)
    yield dirname
    shutil.rmtree(dirname)


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf, lockfile_dir):
    # Ensure no multiplier is set
    cereconf.LOCKFILE_DIR = lockfile_dir


def test_pid_init(lockfile_dir):
    pid = pidcontext.Pid()
    assert pid.piddir == lockfile_dir


def test_pid_init_piddir(piddir):
    pid = pidcontext.Pid(piddir=piddir)
    assert pid.piddir == piddir


@pytest.fixture
def pid(piddir):
    return pidcontext.Pid(piddir=piddir)


def test_pid_content(pid):
    with pid:
        assert os.path.exists(pid.filename)
        with io.open(pid.filename, mode="r", encoding="ascii") as f:
            content = f.read()

    file_pid = int(content.strip())
    assert file_pid == os.getpid()


def test_pid_cleanup(pid):
    with pid:
        assert os.path.exists(pid.filename)
    assert not os.path.exists(pid.filename)


def test_pid_exception_cleanup(pid):
    try:
        with pid:
            raise RuntimeError()
    except RuntimeError:
        pass
    assert not os.path.exists(pid.filename)


def test_pid_lock_twice_exit(piddir):
    pid_1 = pidcontext.Pid(piddir=piddir)
    pid_2 = pidcontext.Pid(piddir=piddir)
    with pid_1:
        with pytest.raises(SystemExit):
            with pid_2:
                pass

    assert pid_1.filename == pid_2.filename


def test_pid_lock_twice_cleanup(piddir):
    with pidcontext.Pid(piddir=piddir) as pid:
        with pytest.raises(SystemExit):
            with pidcontext.Pid(piddir=piddir):
                pass

    assert not os.path.exists(pid.filename)


def test_pid_lock_twice_warning(caplog, piddir):
    with pidcontext.Pid(piddir=piddir):
        with pytest.raises(SystemExit):
            with pidcontext.Pid(piddir=piddir):
                pass

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) > 0
