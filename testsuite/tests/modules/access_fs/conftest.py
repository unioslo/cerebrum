# encoding: utf-8
"""
Test fixtures for :mod:`Cerebrum.modules.no.access_FS` tests
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pytest

from Cerebrum.testutils import file_utils


@pytest.fixture(scope='module')
def write_dir():
    with file_utils.tempdir_ctx(prefix="test-access-fs-") as path:
        yield path


@pytest.fixture
def write_xml_file(write_dir):
    """ a writer that creates a temporary .xml file with the given content. """
    with file_utils.tempfile_ctx(write_dir, suffix=".xml") as filename:
        def writer(text):
            file_utils.write_text(filename, text)
            return filename

        yield writer
