# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.modules.pwcheck.dictionary`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import functools
import io
import os
import shutil
import tempfile
import textwrap

import pytest

from Cerebrum.modules.pwcheck import dictionary


# Encoding for file contents
ENCODING = "utf-8"


@pytest.fixture(scope='module')
def tmpdir():
    """ Creates a temp dir for use by a test module. """
    dirname = tempfile.mkdtemp(prefix="test-mod-pwcheck-dict-")
    yield dirname
    # `rm -r` the directory after after all tests have completed
    shutil.rmtree(dirname)


def _create_text_file(folder, content):
    content = textwrap.dedent(content).lstrip()
    fno, filename = tempfile.mkstemp(dir=folder)
    os.close(fno)
    with io.open(filename, mode="w", encoding=ENCODING) as f:
        f.write(content)
    return filename


def _cleanup_files(filenames):
    for filename in filenames:
        if os.path.exists(filename):
            os.unlink(filename)


#
# look tests
#


@pytest.fixture
def dict_fd(tmpdir):
    filename = _create_text_file(
        tmpdir,
        """
        123456
        Example
        Hunter2
        foo bar baz
        host 127.0.0.1 localhost
        odd separators here
        odd:separators:here
        odds
        password1
        some other words
        """,
    )
    with io.open(filename, mode="r", encoding=ENCODING) as fd:
        yield fd
    _cleanup_files([filename])


def test_look_find_pos(dict_fd):
    """ look() should return the found position in the open file. """
    pos = dictionary.look(dict_fd, "Example", False, False)
    assert pos == 7  # after 123456


def test_look_seek(dict_fd):
    """ look() should seek to the found position. """
    pos = dictionary.look(dict_fd, "Example", False, False)
    assert pos == dict_fd.tell()


def test_look_hit(dict_fd):
    """ look() should seek to the found position in the open file. """
    dictionary.look(dict_fd, "Example", False, False)
    assert dict_fd.readline().startswith("Example")


def test_look_partial(dict_fd):
    """ look() should seek to positions that starts with the given key. """
    dictionary.look(dict_fd, "passw", False, False)
    assert dict_fd.readline().startswith("password1")


def test_look_miss(dict_fd):
    """ If we miss - we should end up where the word *should* be. """
    dictionary.look(dict_fd, "gone missing", False, False)
    assert dict_fd.readline().startswith("host 127.0.0.1")


def test_look_eof(dict_fd):
    """ We may reach the end of the file if our word would be last. """
    dictionary.look(dict_fd, "z is the last ascii-letter", False, False)
    assert not dict_fd.readline().strip()


def test_look_case_fold(dict_fd):
    """ look() should search case insensitively. """
    dictionary.look(dict_fd, "example", False, True)
    assert dict_fd.readline().startswith("Example")


def test_look_no_case_fold(dict_fd):
    """ look() should search case sensitively. """
    # This test is the inverse of test_look_case_fold - i.e. to check that we
    # don't get the same result
    dictionary.look(dict_fd, "example", False, False)
    assert dict_fd.readline().startswith("foo bar")


def test_look_words_only(dict_fd):
    """ look(dictn=True) should ignore (strip) non-word chars. """
    dictionary.look(dict_fd, "odds", True, False)
    assert dict_fd.readline().startswith("odd:separators")


def test_look_all_chars(dict_fd):
    """ look(dictn=False) should consider all characters on a line. """
    # this is the inverse of test_look_words_only - i.e. to check that we
    # don't get the same result
    dictionary.look(dict_fd, "odds", False, False)
    assert dict_fd.readline().rstrip() == "odds"


#
# is_word_in_dicts tests
#


is_word_in_dicts = functools.partial(dictionary.is_word_in_dicts,
                                     file_encoding=ENCODING)


@pytest.fixture
def dicts(tmpdir):
    fn_1 = _create_text_file(
        tmpdir,
        """
        123456
        Hunter2
        password1
        """,
    )
    fn_2 = _create_text_file(
        tmpdir,
        """
        Example
        foo bar baz
        host 127.0.0.1 localhost
        odd separators here
        odd:separators:here
        odds
        """,
    )
    dictionaries = (fn_1, fn_2)
    yield dictionaries
    _cleanup_files(dictionaries)


@pytest.mark.parametrize("word", ("Hunter2", "foo bar baz"))
def test_is_word_in_dicts_hit(dicts, word):
    words = [word]
    assert is_word_in_dicts(dicts, words)


@pytest.mark.parametrize("word", ("banana", "xylophone"))
def test_is_word_in_dicts_miss(dicts, word):
    words = [word]
    assert not is_word_in_dicts(dicts, words)


def test_is_word_in_dicts_empty(dicts):
    assert not is_word_in_dicts(dicts, [])


def test_is_word_in_dicts_any(dicts):
    words = ["Hunter2", "foo bar baz"]
    assert is_word_in_dicts(dicts, words)


#
# check_dict tests
#


check_dict = functools.partial(dictionary.check_dict, file_encoding=ENCODING)


@pytest.fixture
def dict_to_check(tmpdir):
    filename = _create_text_file(
        tmpdir,
        """
        bolder
        jumps
        password
        """,
    )
    yield (filename,)
    _cleanup_files([filename])


@pytest.mark.parametrize(
    "word",
    ("password1", "p4$$w0rd", "123password", "jumping", "boldly"),
)
def test_check_dict_hit(dict_to_check, word):
    assert check_dict(dict_to_check, word)


def test_check_dict_miss(dict_to_check):
    assert not check_dict(dict_to_check, "banana")


#
# check_two_word_combinations tests
#

check_two_word_combinations = functools.partial(
    dictionary.check_two_word_combinations,
    file_encoding=ENCODING,
)


@pytest.fixture
def dict_combos(tmpdir):
    filename = _create_text_file(
        tmpdir,
        """
        bolder
        came
        camel
        example
        flea
        jumps
        late
        password
        """,
    )
    yield (filename,)
    _cleanup_files([filename])


@pytest.mark.parametrize(
    "word, matches",
    (
        ("CamelFle", ("camel", "flea")),
        ("CameLate", ("came", "late")),
        ("ExamplePassword", ("example", "password")),
    ),
)
def test_check_two_word_combinations_hit(dict_combos, word, matches):
    err = check_two_word_combinations(dict_combos, word)
    assert err == matches


@pytest.mark.parametrize("word", ("banana", "CameLAte", "ExamplepassworD"))
def test_check_two_word_combinations_miss(dict_combos, word):
    err = check_two_word_combinations(dict_combos, word)
    assert err is None
