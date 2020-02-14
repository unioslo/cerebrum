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


def test_gnupg_encrypt_decrypt(gpg_key, password_bytes, password_text):
    ciphertext_for_unicode = gpgme_encrypt(
        message=password_text,
        recipient_key_id=gpg_key)

    ciphertext_for_unicode2 = gpgme_encrypt(
        message=password_text,
        recipient_key_id=gpg_key)

    ciphertext_for_str = gpgme_encrypt(
        message=password_bytes,
        recipient_key_id=gpg_key)

    # test for decrypt of unicode text
    decode_text = gpgme_decrypt(ciphertext_for_unicode)
    assert password_text == decode_text.decode('utf-8')

    # test for decrypt of bytestring
    decode_bytes = gpgme_decrypt(ciphertext_for_str)
    assert password_bytes == decode_bytes

    # same text should not result in the same gpg message
    assert ciphertext_for_unicode != ciphertext_for_unicode2

    # ... but both messages should be decrypted to the same content
    decode_text2 = gpgme_decrypt(ciphertext_for_unicode2)
    assert decode_text == decode_text2
