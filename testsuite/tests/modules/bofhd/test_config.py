# -*- coding: utf-8 -*-
""" Tests for Cerebrum.modules.bofhd.config """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import os
import tempfile
import shutil

import pytest
import six

from Cerebrum.modules.bofhd import config as bofhd_config


EXAMPLE_CONFIG = """
# This is a comment...
#    ... which continues indented on the next line

example.module/MyClass

  another.module/AnotherClass
# another comment

foo.bar/Baz
""".lstrip()

# These are the modules and classes as they appear in in EXAMPLE_CONFIG
EXAMPLE_MODULES = (
    ("example.module", "MyClass"),
    ("another.module", "AnotherClass"),
    ("foo.bar", "Baz"),
)


@pytest.fixture(scope='session')
def config_dir():
    """ Creates a temp dir for use by this test module. """
    tempdir = tempfile.mkdtemp(suffix="crb-test-bofhd-config")
    yield tempdir
    # `rm -r` the temp-dir after after all tests have completed, to clear out
    # any residue temp-files from uncompleted AtomicFileWriter write/close
    # cycles.
    shutil.rmtree(tempdir)


@pytest.fixture
def config_file(config_dir):
    """ Gets a `filename` that doesn't exist, and removes it if created. """
    fd, name = tempfile.mkstemp(dir=config_dir)
    os.write(fd, EXAMPLE_CONFIG.encode("utf-8"))
    os.close(fd)
    yield name
    # Remove the file if it still exists
    if os.path.exists(name):
        os.unlink(name)


def test_bofhd_config(config_file):
    config = bofhd_config.BofhdConfig(config_file)
    classes = tuple(config.extensions())
    assert classes == EXAMPLE_MODULES


ERRONEOUS_CONFIG = """
# This is line 1
example.module/MyClass
# Line 3 - the next line contains an invalid entry (no class)
foo.bar
# Line 5
another.module/MyClass
""".lstrip()


@pytest.fixture
def config_with_error(config_dir):
    """ Gets a `filename` that doesn't exist, and removes it if created. """
    fd, name = tempfile.mkstemp(dir=config_dir)
    os.write(fd, ERRONEOUS_CONFIG.encode("utf-8"))
    os.close(fd)
    yield name
    # Remove the file if it still exists
    if os.path.exists(name):
        os.unlink(name)


def test_bofhd_config_error(config_with_error):
    config = bofhd_config.BofhdConfig()
    with pytest.raises(Exception) as e:
        # fails on line 4 (foo.bar) - no class given
        config.load_from_file(config_with_error)

    msg = six.text_type(e)

    # the error should include the filename
    assert config_with_error in msg

    # the error should include the line number
    assert "on line 4:" in msg

    # the error should include the line content
    assert "foo.bar" in msg
