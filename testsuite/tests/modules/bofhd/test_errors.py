# encoding: utf-8
"""
Unit tests for `Cerebrum.modules.bofhd.errors`.

This test module is pretty minimal, and tests the most common use cases for
these exceptions (i.e. how we serialize them for the client).
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six

from Cerebrum.modules.bofhd import errors as bofhd_errors

TEXT = "blåbærsaft"
BYTES = TEXT.encode("utf-8")
NATIVE = BYTES if str is bytes else TEXT


@pytest.mark.parametrize(
    "cls",
    (
        bofhd_errors.CerebrumError,
        bofhd_errors.PermissionDenied,
        bofhd_errors.ServerRestartedError,
        bofhd_errors.SessionExpiredError,
     ),
)
def test_error_to_text(cls):
    exc = cls(TEXT)
    assert six.text_type(exc) == TEXT


def test_unknown_to_text():
    err = NotImplementedError(TEXT)
    msg = "an unknown error has been logged"
    exc = bofhd_errors.UnknownError(
        type(err),
        six.text_type(err),
        msg,
    )
    assert six.text_type(exc) == ("Unknown error (NotImplementedError): "
                                  + msg)
