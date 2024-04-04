# coding: utf-8
""" Unit tests for AtomicFileWriter and related file writers. """
from __future__ import print_function, unicode_literals

import pytest

import math
import os
import random
import shutil
import string
import tempfile


class _MockFailure(Exception):
    """ A unique exception to catch """
    pass


# Filter rule to ignore atomic file warnings:
_ignore_rule = 'ignore::Cerebrum.utils.atomicfile.FileWriterWarning'


@pytest.fixture(scope='module')
def write_dir():
    """ Creates a temp dir for use by this test module. """
    tempdir = tempfile.mkdtemp()
    yield tempdir
    # `rm -r` the temp-dir after after all tests have completed, to clear out
    # any residue temp-files from uncompleted AtomicFileWriter write/close
    # cycles.
    shutil.rmtree(tempdir)


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    # Ensure no multiplier is set
    cereconf.SIMILARSIZE_LIMIT_MULTIPLIER = 1.0


@pytest.fixture
def file_module(cereconf):
    from Cerebrum.utils import atomicfile
    return atomicfile


@pytest.fixture(
    params=[
        'AtomicFileWriter',
        'MinimumSizeWriter',
        'SimilarLineCountWriter',
        'SimilarSizeWriter',
    ],
)
def test_cls(file_module, request):
    cls = getattr(file_module, request.param)

    def init(*args, **kwargs):
        writer = cls(*args, **kwargs)
        writer.validate = False
        return writer
    return init


def generate_text(num_chars):
    choice = string.ascii_letters + " \n"
    return u''.join(
        [random.choice(choice) for i in range(num_chars)])


@pytest.fixture(params=[70], ids=lambda p: 'text({})'.format(p))
def text(request):
    """ Creates a string of `param` printable characters. """
    return generate_text(request.param)


@pytest.fixture(params=[120], ids=lambda p: 'more_text({})'.format(p))
def more_text(request):
    """ Creates a string of `param` printable characters. """
    return generate_text(request.param)


@pytest.yield_fixture
def new_file(write_dir):
    """ Gets a `filename` that doesn't exist, and removes it if created. """
    fd, name = tempfile.mkstemp(dir=write_dir)
    os.close(fd)
    os.unlink(name)
    # `name` is now the path to a non-existing tmp-file
    yield name
    # Remove the file, if created by test
    if os.path.exists(name):
        os.unlink(name)


@pytest.yield_fixture
def text_file(write_dir, text):
    """ Creates a new file with `text` as contents. """
    fd, name = tempfile.mkstemp(dir=write_dir)
    os.write(fd, text.encode("utf-8"))
    os.close(fd)
    yield name
    os.unlink(name)


def match_contents(filename, expected):
    """ Checks that the contents of `filename` is `contents`. """
    current = ""
    with open(filename, 'r') as f:
        current = f.read()

    print('match: {!r} == {!r}'.format(current, expected))
    return current == expected


def test_writer_warns_if_validation_disabled(test_cls, new_file):
    from Cerebrum.utils.atomicfile import FileWriterWarning
    with pytest.warns(FileWriterWarning):
        af = test_cls(new_file)
    assert af.validate is False


@pytest.mark.filterwarnings(_ignore_rule)
def test_writer_prop_name(test_cls, new_file):
    af = test_cls(new_file)
    assert af.name == new_file


@pytest.mark.filterwarnings(_ignore_rule)
def test_writer_prop_closed(test_cls, new_file):
    af = test_cls(new_file)
    assert not af.closed
    af.close()
    assert af.closed


@pytest.mark.filterwarnings(_ignore_rule)
def test_writer_prop_tmpname(test_cls, new_file):
    af = test_cls(new_file)
    assert os.path.exists(af.tmpname)
    assert not os.path.exists(new_file)
    af.close()
    assert not os.path.exists(af.tmpname)
    assert os.path.exists(new_file)


@pytest.mark.filterwarnings(_ignore_rule)
def test_writer_prop_discarded(test_cls, text_file, text):
    af = test_cls(text_file)
    assert not af.discarded
    af.write(text)
    assert not af.discarded
    af.close()
    assert af.discarded


@pytest.mark.filterwarnings(_ignore_rule)
def test_writer_prop_replace(test_cls, text_file, text, more_text):
    """ Check that content is only written to a tmpfile if replace=False. """
    af = test_cls(text_file, replace_equal=True)
    af.replace = False
    af.write(more_text)
    af.close()
    assert os.path.exists(af.tmpname)
    assert match_contents(af.name, text)
    assert match_contents(af.tmpname, more_text)


@pytest.mark.filterwarnings(_ignore_rule)
def test_writer_prop_replaced(test_cls, new_file, text):
    af = test_cls(new_file)
    assert not af.replaced
    af.write(text)
    assert not af.replaced
    af.close()
    assert af.replaced


def test_new_file_write(test_cls, new_file, text):
    # Write 'text' to a new file (non-existing filename)
    af = test_cls(new_file)
    af.write(text)
    af.flush()

    # Assert that 'new_file' does *not* exist after write
    assert not os.path.exists(new_file)
    assert os.path.exists(af.tmpname)
    assert match_contents(af.tmpname, text)


@pytest.mark.filterwarnings(_ignore_rule)
def test_new_file_close(test_cls, new_file, text):
    # Write 'text' to a new file (non-existing filename)
    af = test_cls(new_file)
    af.write(text)
    af.close()

    # Read the file, assert that the contents is as expected after close
    assert af.name == new_file
    assert os.path.exists(af.name)
    assert match_contents(new_file, text)


def test_replace_write(test_cls, text, text_file, more_text):
    # Write 'replace' to a file with contents 'text', without closing
    af = test_cls(text_file)
    af.write(more_text)

    # Read contents from file, assert that it hasn't been replaced
    assert match_contents(text_file, text)


@pytest.mark.filterwarnings(_ignore_rule)
def test_replace_close(test_cls, text, text_file, more_text):
    # Write 'replace' to a file with contents 'text', and close the file
    af = test_cls(text_file)
    af.write(more_text)
    af.close()

    # Read the file, assert that the contents matches 'replace'
    assert match_contents(text_file, more_text)


@pytest.mark.filterwarnings(_ignore_rule)
def test_context_pass(test_cls, text, text_file, more_text):
    with test_cls(text_file) as af:
        af.write(more_text)
    assert match_contents(text_file, more_text)


def test_context_fail(test_cls, text, text_file, more_text):
    try:
        with test_cls(text_file) as af:
            af.write(more_text)
            raise _MockFailure()
    except _MockFailure:
        pass
    assert match_contents(text_file, text)


def test_append_write(test_cls, text, text_file, more_text):
    af = test_cls(text_file, mode='a')
    af.write(more_text)

    # Read contents from file, assert that it hasn't been replaced
    assert match_contents(text_file, text)


@pytest.mark.filterwarnings(_ignore_rule)
def test_append_close(test_cls, text, text_file, more_text):
    af = test_cls(text_file, mode='a')
    af.write(more_text)
    af.close()

    print('Contents: {!r}'.format(text))
    print('Append: {!r}'.format(more_text))

    assert match_contents(text_file, text + more_text)


@pytest.fixture
def min_size_cls(file_module):
    return getattr(file_module, 'MinimumSizeWriter')


def test_minimum_size_pass(min_size_cls, text, new_file):

    af = min_size_cls(new_file)
    af.min_size = len(text) - 1

    af.write(text)
    af.close()

    assert match_contents(new_file, text)


def test_minimum_size_fail(min_size_cls, file_module, new_file, text):

    af = min_size_cls(new_file)
    af.min_size = len(text) + 1

    af.write(text)

    with pytest.raises(file_module.FileTooSmallError):
        af.close()

    assert not os.path.exists(new_file)


@pytest.fixture
def similar_size_cls(file_module):
    return getattr(file_module, 'SimilarSizeWriter')


def test_similar_size_pass(similar_size_cls, text, text_file, more_text):
    change = 100 * abs(float(len(more_text)) / float(len(text)) - 1.0)
    limit = int(math.ceil(change)) + 1

    print('Actual change: {:.1f}%'.format(change))
    print('Limit: {:d}%'.format(limit))

    af = similar_size_cls(text_file)
    af.max_pct_change = limit
    af.write(more_text)
    af.close()

    assert match_contents(text_file, more_text)


def test_similar_size_fail(
        similar_size_cls, file_module, text, text_file, more_text):
    change = 100 * abs(float(len(more_text)) / float(len(text)) - 1.0)
    limit = int(math.floor(change)) - 1

    print('Actual change: {:.1f}%'.format(change))
    print('Limit: {:d}%'.format(limit))

    af = similar_size_cls(text_file)
    af.max_pct_change = limit
    af.write(more_text)

    with pytest.raises(file_module.FileChangeTooBigError):
        af.close()

    assert match_contents(text_file, text)


def test_similar_size_new(similar_size_cls, text, new_file):

    af = similar_size_cls(new_file)
    af.max_pct_change = 0
    af.write(text)
    af.close()

    assert os.path.exists(new_file)
    assert match_contents(new_file, text)


@pytest.fixture
def similar_line_cls(file_module):
    return getattr(file_module, 'SimilarLineCountWriter')


def test_line_count_fail(similar_line_cls, file_module, text, text_file):
    af = similar_line_cls(text_file)
    af.max_line_change = 1

    lines = text.split("\n")
    lines.append('another line')
    lines.append('another line')
    too_many_lines = "\n".join(lines)

    af.write(too_many_lines)

    with pytest.raises(file_module.FileChangeTooBigError):
        af.close()

    assert match_contents(text_file, text)


def test_line_count_pass(similar_line_cls, text, text_file):
    af = similar_line_cls(text_file)
    af.max_line_change = 1

    lines = text.split("\n")
    lines.append('another line')
    new_content = "\n".join(lines)

    af.write(new_content)
    af.close()

    assert match_contents(text_file, new_content)


@pytest.fixture
def mixed_cls(file_module):
    ssize = getattr(file_module, 'SimilarLineCountWriter')
    minsize = getattr(file_module, 'MinimumSizeWriter')

    class MixedSizeWriter(ssize, minsize):
        pass
    return MixedSizeWriter


def test_mixed_writer_pass(mixed_cls, text_file, text):
    af = mixed_cls(text_file, mode='a')
    af.max_line_change = 1
    af.min_size = 1
    line = "\nanother line"
    af.write(line)
    af.close()

    assert match_contents(text_file, text + line)


def test_mixed_writer_fail_size(mixed_cls, file_module, text_file, text):
    af = mixed_cls(text_file, mode='a')
    af.max_line_change = 1
    line = "\nanother line"
    af.min_size = len(text) + len(line) + 10
    af.write(line)

    with pytest.raises(file_module.FileTooSmallError):
        af.close()

    assert match_contents(text_file, text)


def test_mixed_writer_fail_change(mixed_cls, file_module, text_file, text):
    af = mixed_cls(text_file, mode='a')
    line = "\nanother line"
    af.max_line_change = 0
    af.min_size = 1
    af.write(line)

    with pytest.raises(file_module.FileChangeTooBigError):
        af.close()

    assert match_contents(text_file, text)
