# encoding: utf-8
"""
Test fixtures for :mod:`Cerebrum.modules.password_generator` tests
"""
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
    dirname = tempfile.mkdtemp(prefix="test-pwgen-")
    yield dirname
    # `rm -r` the directory after after all tests have completed
    shutil.rmtree(dirname)


def _create_file(dirname, **kwargs):
    fd, filename = tempfile.mkstemp(dir=dirname, **kwargs)
    os.close(fd)
    return filename


def _remove_file(filename):
    if os.path.exists(filename):
        os.unlink(filename)


@pytest.fixture
def new_file(write_dir):
    """ Gets a `filename` that is guaranteed to not exist. """
    filename = _create_file(write_dir)
    os.unlink(filename)
    yield filename
    _remove_file(filename)


@pytest.fixture
def empty_file(write_dir):
    """
    Create an empty `filename`.

    Typically for use as a valid passphrase word dictionary in tests and other
    fixtures.
    """
    filename = _create_file(write_dir)
    yield filename
    _remove_file(filename)


@pytest.fixture
def empty_json_file(write_dir):
    """
    Create an empty `filename.json`.

    Typically for use as a config file in tests and other fixtures that needs a
    .json suffix for config parsers to identify the content.
    """
    filename = _create_file(write_dir, suffix=".json")
    yield filename
    _remove_file(filename)
