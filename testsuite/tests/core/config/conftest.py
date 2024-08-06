# encoding: utf-8
""" Common fixtures for config tests. """
import pytest
import tempfile
import os
import shutil


@pytest.fixture(scope='module')
def tmpdir():
    """ Creates a temp dir for use by this test module. """
    tempdir = tempfile.mkdtemp()
    yield tempdir
    # `rm -r` the temp-dir after after all tests have completed, to clear out
    # any residue temp-files from uncompleted AtomicFileWriter write/close
    # cycles.
    shutil.rmtree(tempdir)


@pytest.fixture
def tmpfile(tmpdir):
    fd, name = tempfile.mkstemp(dir=tmpdir)
    os.close(fd)
    yield name
    # Remove the file, unless already deleted by test
    if os.path.exists(name):
        os.unlink(name)


@pytest.fixture
def config_dir():
    return os.path.join(os.path.dirname(__file__), 'testdata/configs')
