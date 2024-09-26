# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.otp.otp_utils` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest
import six
from six.moves.urllib.parse import quote

from Cerebrum.modules.otp import otp_utils


#
# test generate_secret
#


CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def test_generate_secret():
    secret = otp_utils.generate_secret()
    assert len(secret) == 16
    assert all(c in CHARSET for c in secret)


def test_generate_secret_size():
    secret = otp_utils.generate_secret(15)
    assert len(secret) == 24
    assert all(c in CHARSET for c in secret)


#
# test validate_secret
#


def test_validate_secret():
    otp_utils.validate_secret("HPV3FP52AS3QUF2Q")
    assert True  # reached


def test_validate_secret_invalid_chars():
    with pytest.raises(ValueError) as exc_info:
        # a 10 byte (16 char) secret, but with invalid chars (8 and 1)
        otp_utils.validate_secret("QZNK7MFG3QEIZH81")

    error = six.text_type(exc_info.value)
    assert error.startswith("invalid base32-secret: ")


def test_validate_secret_invalid_size():
    with pytest.raises(ValueError) as exc_info:
        # a 15 byte (24 char) secret, expecting default of 10 bytes
        otp_utils.validate_secret("VVPDY23FTUG4LZV37K6NBM2A")

    error = six.text_type(exc_info.value)
    assert error.startswith("invalid base32-secret: ")


def test_validate_secret_size():
    otp_utils.validate_secret("VVPDY23FTUG4LZV37K6NBM2A", 15)
    assert True  # reached


#
# test format_otp_uri
#

def _check_uri_label_and_issuer(uri, label, issuer):
    # There are different, valid syntaxes for totp labels - both are valid, and
    # different versions of passlib uses different formats
    return (
        uri.startswith("otpauth://totp/" + quote(label))
        or
        uri.startswith("otpauth://totp/" + quote(issuer) + ":" + quote(label))
    ) and ("issuer=" + quote(issuer)) in uri


def test_format_otp_uri_default():
    secret = "HPV3FP52AS3QUF2Q"
    uri = otp_utils.format_otp_uri(secret)

    assert ("secret=" + secret) in uri
    assert _check_uri_label_and_issuer(uri, otp_utils.DEFAULT_LABEL,
                                       otp_utils.DEFAULT_ISSUER)


def test_format_otp_uri_custom():
    secret = "HPV3FP52AS3QUF2Q"
    issuer = "foo"
    label = "bar"
    uri = otp_utils.format_otp_uri(secret, label=label, issuer=issuer)

    assert ("secret=" + secret) in uri
    assert _check_uri_label_and_issuer(uri, label, issuer)
