# encoding: utf-8
""" Test fixtures for mod:`Cerebrum.modules.job_runner.socket_ipc` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import os
import shutil
import tempfile

import pytest


@pytest.fixture(scope='module')
def write_dir():
    """ Creates a temp dir for use by a test module. """
    dirname = tempfile.mkdtemp(prefix="test-core-utils-")
    yield dirname
    # `rm -r` the directory after after all tests have completed
    shutil.rmtree(dirname)


@pytest.fixture
def new_file(write_dir):
    """ Gets a `filename` that doesn't exist, and removes it if created. """
    fd, filename = tempfile.mkstemp(dir=write_dir)
    os.close(fd)
    os.unlink(filename)
    # `filename` is now the path to a non-existing tmp-file
    yield filename
    # Remove the file if the test created it (and didn't remove it)
    if os.path.exists(filename):
        os.unlink(filename)


@pytest.fixture
def config_file(write_dir):
    """ Gets a `filename.py` that doesn't exist, and removes it if created. """
    fd, filename = tempfile.mkstemp(dir=write_dir, suffix=".py")
    os.close(fd)
    os.unlink(filename)
    # `filename` is now the path to a non-existing tmp-file
    yield filename
    # Remove the file if the test created it (and didn't remove it)
    if os.path.exists(filename):
        os.unlink(filename)
