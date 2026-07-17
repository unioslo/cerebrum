# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.otp.jwe_utils` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.otp import jwe_utils


# keys_file_secret from conftest


def test_get_jwk(keys_file_secret):
    jwk = jwe_utils.get_jwk(keys_file_secret)
    assert jwk
    assert jwk.has_public
    assert jwk.has_private


@pytest.fixture
def jwk(keys_file_secret):
    return jwe_utils.get_jwk(keys_file_secret)


def test_jwe_encrypt(jwk):
    secret_data = {
        'aud': "example",
        'msg': "hello, world!",
    }
    token = jwe_utils.jwe_encrypt(secret_data, jwk)
    assert token

    # header.key.iv.ciphertext.auth_tag
    parts = token.split(".")
    assert len(token.split(".")) == 5

    # RSA-OAEP includes all parts
    assert all(p for p in parts)


def test_jwe_decrypt(jwk):
    """ test encrypt/decrypt cycle. """
    secret_data = {
        'aud': "example",
        'msg': "hello, world!",
    }
    token = jwe_utils.jwe_encrypt(secret_data, jwk)
    result = jwe_utils.jwe_decrypt(token, jwk)
    assert result == secret_data
