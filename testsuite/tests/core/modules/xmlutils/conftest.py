# encoding: utf-8
"""
Fixtures for :mod:`Cerebrum.modules.xmlutils` unit tests
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import pytest

from Cerebrum.testutils import file_utils
from Cerebrum.testutils.log_utils import StrictNullHandler


@pytest.fixture(scope='module')
def write_dir():
    """ temporary directory for files. """
    with file_utils.tempdir_ctx(prefix="test-xmlutils-") as path:
        yield path


@pytest.fixture
def write_xml_file(write_dir):
    """ a writer that creates a temporary .xml file with the given content. """
    with file_utils.tempfile_ctx(write_dir, suffix=".xml") as filename:
        def writer(text):
            file_utils.write_text(filename, text)
            return filename

        yield writer


@pytest.fixture(scope="module", autouse=True)
def logger():
    """ a logger for use in tests. """
    logger = logging.getLogger(__name__)

    # ensure logger checks log record formatting:
    logger.addHandler(StrictNullHandler())
    logger.setLevel(-100)
    return logger
