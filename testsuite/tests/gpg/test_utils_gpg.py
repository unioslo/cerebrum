# -*- coding: utf-8 -*-
"""
Tests for :mod:`Cerebrum.utils.gpg`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import random
import string

import pytest
import six

import Cerebrum.utils.gpg


gpgme_encrypt = Cerebrum.utils.gpg.gpgme_encrypt
gpgme_decrypt = Cerebrum.utils.gpg.gpgme_decrypt


# See the `conftest` module for some test setup and fixtures that makes these
# tests work.
#
# TODO: Would it be better to move the gpg fixtures up a level, and move this
# test module back to test_core/test_utils/?


@pytest.fixture
def random_prefix():
    uni_chars = six.text_type(string.ascii_letters + string.digits)
    return ''.join(random.choice(uni_chars) for _ in range(32))


@pytest.fixture
def password_text(random_prefix):
    return random_prefix + 'æøå'


@pytest.fixture
def password_bytes(password_text):
    return password_text.encode('utf-8')


@pytest.fixture
def invalid_key(gpg_key):
    """ Swap first character in the *gpg_key* key-id to make it invalid. """
    # Swap the first hex-char of the key-id for the "next char".  The key-id
    # itself could be *valid*, but it just doesn't match an actual key we know,
    # or have in our gpghome dir.
    next_char = format((int(gpg_key[0], 16) + 1) % 16, "x")
    return next_char + gpg_key[1:]


def test_gnupg_encrypt(gpg_key, password_text):
    gpg_message = gpgme_encrypt(message=password_text,
                                recipient_key_id=gpg_key)
    assert '-BEGIN PGP MESSAGE-' in gpg_message
    assert '-END PGP MESSAGE-' in gpg_message


def test_gnupg_encrypt_invalid_key(caplog, invalid_key, password_text):
    with pytest.raises(RuntimeError):
        # gpgme.GpgmeError
        gpgme_encrypt(message=password_text,
                      recipient_key_id=invalid_key)

    assert len(caplog.records) == 1
    log_msg = caplog.records[0].message
    assert log_msg.startswith("Unable to get key=")


def test_gnupg_encrypt_diff(gpg_key, password_text):
    a = gpgme_encrypt(message=password_text,
                      recipient_key_id=gpg_key)
    b = gpgme_encrypt(message=password_text,
                      recipient_key_id=gpg_key)
    assert a != b


def test_gnupg_encrypt_decrypt_bytes(gpg_key, password_bytes):
    message = gpgme_encrypt(message=password_bytes,
                            recipient_key_id=gpg_key)
    raw_message = gpgme_decrypt(message)
    assert raw_message == password_bytes


def test_gnupg_encrypt_decrypt_text(gpg_key, password_text, password_bytes):
    message = gpgme_encrypt(message=password_text,
                            recipient_key_id=gpg_key)
    raw_message = gpgme_decrypt(message)
    assert raw_message == password_bytes


#
# Legacy tests
#
# These tests are a bit ugly/hacky, and we test for multiple things in each
# test.
#

legacy_gpg_encrypt = Cerebrum.utils.gpg.legacy_gpg_encrypt
legacy_gpg_decrypt = Cerebrum.utils.gpg.legacy_gpg_decrypt


def test_legacy_gnupg_encrypt(gpg_key, password_text):
    with pytest.deprecated_call():
        gpg_message = legacy_gpg_encrypt(password_text, gpg_key)
    assert '-BEGIN PGP MESSAGE-' in gpg_message
    assert '-END PGP MESSAGE-' in gpg_message


def test_legacy_gnupg_encrypt_invalid_key(caplog, invalid_key, password_text):
    with pytest.raises(IOError):
        # gpgme.GpgmeError
        with pytest.deprecated_call():
            legacy_gpg_encrypt(password_text, invalid_key)

    assert len(caplog.records) == 1
    log_msg = caplog.records[0].message
    assert log_msg.startswith("gpg stderr: ")


def test_legacy_gnupg_encrypt_diff(gpg_key, password_text):
    with pytest.deprecated_call():
        a = legacy_gpg_encrypt(password_text, gpg_key)
        b = legacy_gpg_encrypt(password_text, gpg_key)
    assert a != b


def test_legacy_gnupg_encrypt_decrypt_bytes(gpg_key, password_bytes):
    message = gpgme_encrypt(password_bytes,
                            gpg_key)
    with pytest.deprecated_call():
        plaintext = legacy_gpg_decrypt(message, gpg_key)
    assert plaintext == password_bytes


def test_legacy_gnupg_encrypt_decrypt_text(gpg_key, password_text):
    expect = password_text.encode('utf-8')
    message = gpgme_encrypt(message=password_text,
                            recipient_key_id=gpg_key)
    with pytest.deprecated_call():
        plaintext = legacy_gpg_decrypt(message, gpg_key)
    assert plaintext == expect
