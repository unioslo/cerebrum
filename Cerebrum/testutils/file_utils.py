# -*- coding: utf-8 -*-
#
# Copyright 2024 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Re-usable utilities for dealing with files in unit tests.

Most of the functions and contexts in this module are small and simple, but can
reduce overhead and duplicated code when writing tests.

The file and dir contexts are particularly useful in fixtures, e.g.:
::

    @pytest.fixture(scope="module")
    def write_dir():
        with tempdir_ctx(prefix="my-test-") as path:
            yield path


    @pytest.fixture
    def config_file(write_dir):
        data = {"foo": "bar"}
        with tempfile_ctx(suffix=".json") as filename:
            write_json(filename, data)
            yield filename

... while some functions are useful in tests, e.g.:
::

    def test_file_content(filename):
        assert read_text(filename) == "expected text"


"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import contextlib
import json
import os
import shutil
import tempfile

from Cerebrum.utils import file_stream


#
# Create and delete directories
#


def create_dir(prefix="tests-", **kwargs):
    """ create a temporary directory """
    return tempfile.mkdtemp(prefix=prefix, **kwargs)


def delete_dir(path):
    """ delete a directory tree. """
    shutil.rmtree(path)


@contextlib.contextmanager
def tempdir_ctx(**kwargs):
    """
    A temporary directory context.

    The directory should exist within the context, but the entire directory
    tree is removed on context exit.
    """
    path = create_dir(**kwargs)
    yield path
    delete_dir(path)


#
# Create and delete files
#


def create_file(dirname, **kwargs):
    """ Create a new, empty temporary file in a given directory.  """
    fd, filename = tempfile.mkstemp(dir=dirname, **kwargs)
    os.close(fd)
    return filename


def reserve_file(dirname, **kwargs):
    """ Create a unique, non-existing filename that *doesn't* exist.  """
    fd, filename = tempfile.mkstemp(dir=dirname, **kwargs)
    os.close(fd)
    delete_file(filename)
    return filename


def delete_file(filename):
    """ Remove a filename if it exists.  """
    if os.path.exists(filename):
        os.unlink(filename)


@contextlib.contextmanager
def tempfile_ctx(dirname, name_only=False, **kwargs):
    """
    A temporary file context.

    The filename should be available within the context, and be removed on exit
    if created.
    """
    if name_only:
        filename = reserve_file(dirname, **kwargs)
    else:
        filename = create_file(dirname, **kwargs)
    yield filename
    delete_file(filename)


#
# Read and write file content
#


def write_text(filename, text, encoding="utf-8"):
    with file_stream.get_output_context(filename, encoding=encoding) as f:
        f.write(text)


def write_bytes(filename, bytestring):
    with file_stream.get_output_context(filename, encoding=None) as f:
        f.write(bytestring)


def read_text(filename, text, encoding="utf-8"):
    with file_stream.get_input_context(filename, encoding=encoding) as f:
        return f.read()


def read_bytes(filename, text):
    with file_stream.get_input_context(filename, encoding=None) as f:
        return f.read()


def write_json(filename, data, indent=2, sort_keys=True, **kwargs):
    encoding = None if str is bytes else "utf-8"
    with file_stream.get_output_context(filename, encoding=encoding) as f:
        json.dump(data, f, indent=2, sort_keys=True)


def read_json(filename, data):
    encoding = None if str is bytes else "utf-8"
    with file_stream.get_input_context(filename, encoding=encoding) as f:
        return json.load(f)
