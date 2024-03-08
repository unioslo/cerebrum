#!/usr/bin/env python
# encoding: utf-8
""" Common fixtures for py.test tests. """
import pytest
import tempfile
import os


@pytest.yield_fixture
def tmpfile(request):
    """ Make a temporary file, and clean up afterwards. """
    fd, name = tempfile.mkstemp()
    os.close(fd)
    yield name
    os.unlink(name)


@pytest.fixture
def config_dir():
    return os.path.join(os.path.dirname(__file__), 'testdata', 'configs')
