#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for Cerebrum.utils.gpg """
from __future__ import print_function, unicode_literals

import random
import string

import pytest
import six

import Cerebrum.utils.gpg


gpgme_encrypt = Cerebrum.utils.gpg.gpgme_encrypt
gpgme_decrypt = Cerebrum.utils.gpg.gpgme_decrypt


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


def test_gnupg_encrypt(gpg_key, password_text):
    gpg_message = gpgme_encrypt(message=password_text,
                                recipient_key_id=gpg_key)
    assert '-BEGIN PGP MESSAGE-' in gpg_message
    assert '-END PGP MESSAGE-' in gpg_message


def test_gnupg_encrypt_diff(gpg_key, password_text):
    a = gpgme_encrypt(message=password_text,
                      recipient_key_id=gpg_key)
    b = gpgme_encrypt(message=password_text,
                      recipient_key_id=gpg_key)
    assert a != b


def test_gnupg_encrypt_decrypt_bytes(gpg_key, password_bytes):
    message = gpgme_encrypt(message=password_bytes,
                            recipient_key_id=gpg_key)
    plaintext = gpgme_decrypt(message)
    assert plaintext == password_bytes


def test_gnupg_encrypt_decrypt_text(gpg_key, password_text):
    expect = password_text.encode('utf-8')
    message = gpgme_encrypt(message=password_text,
                            recipient_key_id=gpg_key)
    plaintext = gpgme_decrypt(message)
    assert plaintext == expect
