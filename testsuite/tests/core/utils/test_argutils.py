# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.utils.argutils`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import codecs

import pytest
import six

from Cerebrum.utils import argutils


#
# UnicodeType tests
#

ENCODING = "utf-8"
TEXT = "blåbærsaft"
BYTES = TEXT.encode(ENCODING)
NATIVE = BYTES if str is bytes else TEXT


@pytest.fixture
def unicode_type():
    return argutils.UnicodeType(encoding=ENCODING)


def test_unicode_type_init(unicode_type):
    assert unicode_type


def test_unicode_type_repr(unicode_type):
    assert repr(unicode_type).startswith("UnicodeType(")


def test_unicode_type_default():
    unicode_type = argutils.UnicodeType(encoding=ENCODING)
    assert unicode_type.encoding


def test_unicode_type_convert_bytes(unicode_type):
    assert unicode_type(BYTES) == TEXT


def test_unicode_type_convert_text(unicode_type):
    assert unicode_type(TEXT) == TEXT


#
# IntegerType tests
#

def test_int_type_defaults():
    int_type = argutils.IntegerType()
    assert int_type
    assert int_type.minval is None
    assert int_type.maxval is None


@pytest.fixture
def int_type():
    return argutils.IntegerType(minval=0, maxval=10)


def test_int_type_init(int_type):
    assert int_type.minval == 0
    assert int_type.maxval == 10


def test_int_type_repr(int_type):
    assert repr(int_type).startswith("IntegerType(")


@pytest.mark.parametrize("value", ["-1", "11", "text", ""])
def test_int_type_invalid(int_type, value):
    with pytest.raises(ValueError):
        int_type(value)


@pytest.mark.parametrize("value", ["0", "10", "5"])
def test_int_type_valid(int_type, value):
    expected = int(value)
    assert int_type(value) == expected


#
# attr_type tests
#

@pytest.fixture
def attr_target():
    """ an object with attribtues 'foo' and 'bar'. """
    return type(str("attr_target"), (object,), {'foo': 1, 'bar': "text"})


def test_attr_type_get(attr_target):
    get = argutils.attr_type(attr_target)
    assert get("foo") == 1


def test_attr_type_get_missing(attr_target):
    get = argutils.attr_type(attr_target)
    with pytest.raises(argparse.ArgumentTypeError):
        assert get("baz")


def test_attr_type_attr_func(attr_target):
    get = argutils.attr_type(attr_target, attr_func=six.text_type.lower)
    assert get("FOO") == 1


def test_attr_type_type_func(attr_target):
    get = argutils.attr_type(attr_target, type_func=six.text_type)
    assert get("foo") == "1"


#
# codec_type tests
#

def test_codec_type_ascii():
    assert argutils.codec_type("ascii")


def test_codec_type_utf8():
    assert argutils.codec_type("UTF-8")


def test_codec_type_invalid():
    with pytest.raises(ValueError):
        argutils.codec_type("not-a-codec")


#
# ParserContext tests
#

def test_parser_context_init():
    parser = argparse.ArgumentParser()
    ctx = argutils.ParserContext(parser)
    assert ctx.parser is parser
    assert ctx.argument is None


PROG = "my-prog"
ERROR = "something went wrong"


def test_parser_context_error(capsys):
    expected_err = "%s: error: %s" % (PROG, ERROR)
    parser = argparse.ArgumentParser(prog=PROG)
    with pytest.raises(SystemExit) as exc_info:
        with argutils.ParserContext(parser):
            raise ValueError(ERROR)

    _, stderr = capsys.readouterr()
    lines = stderr.splitlines()
    assert expected_err == lines[-1]
    assert exc_info.type == SystemExit
    assert exc_info.value.code == 2


def test_parser_context_arg_error(capsys):
    expected_err = "%s: error: argument --foo: %s" % (PROG, ERROR)
    parser = argparse.ArgumentParser(prog=PROG)
    arg = parser.add_argument("--foo", help="foo")
    with pytest.raises(SystemExit) as exc_info:
        with argutils.ParserContext(parser, arg):
            raise ValueError(ERROR)

    _, stderr = capsys.readouterr()
    lines = stderr.splitlines()
    assert expected_err == lines[-1]
    assert exc_info.type == SystemExit
    assert exc_info.value.code == 2


#
# ExtendAction tests
#

def test_extend():
    parser = argparse.ArgumentParser(prog=PROG)
    parser.add_argument(
        "--foo",
        dest="foo",
        type=lambda arg: arg.split(','),
        action=argutils.ExtendAction,
    )
    args = parser.parse_args(["--foo", "bar,baz", "--foo", "bat"])
    assert args.foo
    assert args.foo == ["bar", "baz", "bat"]


#
# ExtendConstAction tests
#

def test_extend_const():
    parser = argparse.ArgumentParser(prog=PROG)
    parser.add_argument(
        "--foo",
        dest="foo",
        const=("bar", "baz"),
        action=argutils.ExtendConstAction,
    )
    args = parser.parse_args(["--foo"])
    assert args.foo
    assert args.foo == ["bar", "baz"]


#
# add_commit_args tests
#

def test_add_commit_args_default_false():
    parser = argparse.ArgumentParser(prog=PROG)
    argutils.add_commit_args(parser, default=False)
    args = parser.parse_args([])
    assert not args.commit


def test_add_commit_args_default_true():
    parser = argparse.ArgumentParser(prog=PROG)
    argutils.add_commit_args(parser, default=True)
    args = parser.parse_args([])
    assert args.commit


def test_add_commit_args_commit():
    parser = argparse.ArgumentParser(prog=PROG)
    argutils.add_commit_args(parser)
    args = parser.parse_args(["--commit"])
    assert args.commit


def test_add_commit_args_dryrun():
    parser = argparse.ArgumentParser(prog=PROG)
    argutils.add_commit_args(parser)
    args = parser.parse_args(["--dryrun"])
    assert not args.commit


def test_add_commit_args_mutex():
    parser = argparse.ArgumentParser(prog=PROG)
    argutils.add_commit_args(parser)
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--dryrun", "--commit"])

    assert exc_info.type == SystemExit
    assert exc_info.value.code == 2
