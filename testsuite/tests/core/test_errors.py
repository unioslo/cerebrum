# -*- coding: utf-8 -*-
""" Unit tests for `Cerebrum.Errors`. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals
)

import pytest
import six

from Cerebrum import Errors
from Cerebrum.utils import text_compat

DOCSTRING = "doc \N{REPLACEMENT CHARACTER} 1"
MESSAGE = "msg f94a"
DOCSTRING_AND_MESSAGE = "%s: %s" % (DOCSTRING, MESSAGE)


#
# DocstringException messages should include the exception class docstring
#

@pytest.fixture
def doc_error_cls():
    """ A DocstringException with a docstring. """
    # Create exception using `type` to dynamically set __doc__ to DOCSTRING
    return type(
        text_compat.to_str("DocError"),
        (Errors.DocstringException,),
        {'__doc__': DOCSTRING},
    )


# TODO: This fails on Python 2 - we don't handle unicode well with
# str(CerebrumError(six.tex_type)):
#
# def test_doc_error_nomsg_str(doc_error_cls):
#     """ str(exception) should only include our docstring. """
#     exc = doc_error_cls()
#     assert str(exc) == text_compat.to_str(DOCSTRING)


@pytest.mark.skipif(six.PY3,
                    reason="covered by test_doc_error_nomsg_str on PY3")
def test_doc_error_nomsg_text(doc_error_cls):
    """ unicode(exception) should only include our docstring. """
    exc = doc_error_cls()
    assert six.text_type(exc) == DOCSTRING


def test_raise_doc_error_nomsg(doc_error_cls):
    """ the traceback should include our class name and docstring. """
    with pytest.raises(doc_error_cls) as exc_info:
        raise doc_error_cls()
    # Get the last line of the pretty-printed traceback:
    msg = text_compat.to_text(exc_info.exconly())

    # PY3 prefixes the class name with its module, so we use endswith rather
    # than __eq__
    assert msg.endswith("DocError: " + DOCSTRING)


# TODO: This fails on Python 2 - we don't handle unicode well with
# str(CerebrumError(six.tex_type)):
#
# def test_doc_error_msg_str(doc_error_cls):
#     """ str(exception) should include our docstring and message. """
#     exc = doc_error_cls(MESSAGE)
#     assert str(exc) == text_compat.to_str(DOCSTRING_AND_MESSAGE)


@pytest.mark.skipif(six.PY3,
                    reason="covered by test_doc_error_msg_text on PY3")
def test_doc_error_msg_text(doc_error_cls):
    """ unicode(exception) should include our docstring and message. """
    exc = doc_error_cls(MESSAGE)
    assert six.text_type(exc) == DOCSTRING_AND_MESSAGE


def test_raise_doc_error_msg(doc_error_cls):
    """ the traceback should include our class name, docstring and message. """
    with pytest.raises(doc_error_cls) as exc_info:
        raise doc_error_cls(MESSAGE)
    msg = text_compat.to_text(exc_info.exconly())
    assert msg.endswith("DocError: " + DOCSTRING_AND_MESSAGE)


#
# DocstringException messages should be formatted like regular exceptions if no
# docstring is provided
#


@pytest.fixture
def nodoc_error_cls():
    """ A DocstringException without an actual docstring. """
    class NodocError(Errors.DocstringException):
        pass

    return NodocError


def test_nodoc_error_nomsg_str(nodoc_error_cls):
    """ str(exception) should not include a docstring or message. """
    exc = nodoc_error_cls()
    assert str(exc) == text_compat.to_str("")


@pytest.mark.skipif(six.PY3,
                    reason="covered by test_nodoc_error_nomsg_str on PY3")
def test_nodoc_error_nomsg_text(nodoc_error_cls):
    """ unicode(exception) should not include a docstring or message. """
    exc = nodoc_error_cls()
    assert six.text_type(exc) == ""


def test_raise_nodoc_error_nomsg(nodoc_error_cls):
    """ the traceback should only include the class name. """
    with pytest.raises(nodoc_error_cls) as exc_info:
        raise nodoc_error_cls()
    msg = text_compat.to_text(exc_info.exconly())
    assert msg.endswith("NodocError")


def test_nodoc_error_msg_str(nodoc_error_cls):
    """ str(exception) should only include our message. """
    exc = nodoc_error_cls(MESSAGE)
    assert str(exc) == text_compat.to_str(MESSAGE)


@pytest.mark.skipif(six.PY3,
                    reason="covered by test_nodoc_error_msg_str on PY3")
def test_nodoc_error_msg_text(nodoc_error_cls):
    """ unicode(exception) should only include our message. """
    exc = nodoc_error_cls(MESSAGE)
    assert six.text_type(exc) == MESSAGE


def test_raise_nodoc_error_msg(nodoc_error_cls):
    """ the traceback should only include our class name and message. """
    with pytest.raises(nodoc_error_cls) as exc_info:
        raise nodoc_error_cls(MESSAGE)
    msg = text_compat.to_text(exc_info.exconly())
    assert msg.endswith("NodocError: " + MESSAGE)


#
# Inheriting from a DocstringException should *not* include the docstring
# itself.
#


@pytest.fixture
def sub_error_cls():
    """ A DocstringException subclass without a docstring. """

    class _DocError(Errors.DocstringException):
        """this docstring should not occur in subclasses"""

    class SubError(_DocError):
        # note - parent has docstring, we don't
        pass

    return SubError


def test_sub_error_nomsg_str(sub_error_cls):
    """ str(exception) should not include a docstring or message. """
    exc = sub_error_cls()
    assert str(exc) == text_compat.to_str("")


def test_raise_sub_error_nomsg_str(sub_error_cls):
    """ the traceback should only include the class name. """
    with pytest.raises(sub_error_cls) as exc_info:
        raise sub_error_cls()
    msg = text_compat.to_text(exc_info.exconly())
    assert msg.endswith("SubError")


def test_sub_error_msg_str(sub_error_cls):
    """ str(exception) should only include our message. """
    exc = sub_error_cls(MESSAGE)
    assert str(exc) == text_compat.to_str(MESSAGE)


def test_raise_sub_error_msg_str(sub_error_cls):
    """ the traceback should only include our class name and message. """
    with pytest.raises(sub_error_cls) as exc_info:
        raise sub_error_cls(MESSAGE)
    msg = text_compat.to_text(exc_info.exconly())
    assert msg.endswith("SubError: " + MESSAGE)


#
# Test our common DocstringException implementations
#

_common_docstring_exceptions = [
    (Errors.CerebrumError, "Generic Cerebrum error"),
    (Errors.RealityError, "This should never happen"),
    (Errors.UnreachableCodeError, "Unreachable code"),
    (Errors.DatabaseException, "Database error"),
    (Errors.NotFoundError, "Could not find"),
    (Errors.TooManyRowsError, "Too many rows"),
]


@pytest.mark.parametrize(
    "cls, doc",
    _common_docstring_exceptions,
    ids=[c[0].__name__ for c in _common_docstring_exceptions],
)
def test_error_msg(cls, doc):
    exc = cls(MESSAGE)
    expect = "%s: %s" % (doc, MESSAGE)
    assert six.text_type(exc) == expect
