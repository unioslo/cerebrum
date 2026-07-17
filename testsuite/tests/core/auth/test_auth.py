#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for Cerebrum.auth """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from collections import namedtuple

import pytest

import Cerebrum.auth
from Cerebrum.modules.no.uio.voip.voipAuthAccountMixin import (
    encrypt_ha1_md5,
    verify_ha1_md5,
)

ALL_METHODS = (
    ('MD4-NT', Cerebrum.auth.AuthTypeMD4NT),
    ('MD5-crypt', Cerebrum.auth.AuthTypeMD5),
    ('SHA-256-crypt', Cerebrum.auth.AuthTypeSHA256),
    ('SHA-512-crypt', Cerebrum.auth.AuthTypeSHA512),
    ('SSHA', Cerebrum.auth.AuthTypeSSHA),
    ('md5-unsalted', Cerebrum.auth.AuthTypeMD5Unsalt),
    ('plaintext', Cerebrum.auth.AuthTypePlaintext),
)
ALL_METHOD_NAMES = tuple(t[0] for t in ALL_METHODS)


@pytest.fixture
def auth_methods():
    """AuthMap with a known set of auth methods."""
    auth_methods = Cerebrum.auth.AuthMap(ALL_METHODS)
    return auth_methods


def test_map_get_crypt_subset(auth_methods):
    """test that AuthMap.get_crypt_subset() works as expected"""
    subset_t = ALL_METHODS[:2]
    subset_n = [t[0] for t in subset_t]

    subset = auth_methods.get_crypt_subset(subset_n)

    assert len(subset_t) == len(subset)
    assert all(name in subset for name in subset_n)


@pytest.mark.parametrize('method,cls', ALL_METHODS, ids=ALL_METHOD_NAMES)
def test_all_methods_exists(method, cls):
    """test that all the required methods exists in all_auth_methods"""
    assert Cerebrum.auth.all_auth_methods[method] is cls


def test_crypt_bytes():
    """ test the underlying crypt.crypt function wrapper. """
    password = b"hesterbest"
    salt = b"$1$ABCDEFGI"
    cryptstring = "$1$ABCDEFGI$iO4CKjwcmvejNZ7j1MEW./"
    assert Cerebrum.auth.crypt_bytes(password, salt) == cryptstring


def test_generate_empty_salt():
    assert Cerebrum.auth.generate_salt(0) == b""


def test_generate_salt_16():
    salt = Cerebrum.auth.generate_salt(16)
    assert len(salt) == 16


def test_generate_salt_prefix():
    prefix = "my-prefix-"
    salt = Cerebrum.auth.generate_salt(8, prefix=prefix)
    assert salt.startswith(prefix.encode("ascii"))
    assert len(salt) == 8 + len(prefix)


_TestCase = namedtuple(
    "_TestCase",
    ("name", "method", "password", "salt", "cryptstring"),
)


CORRECT_PASSWORD = "hesterbest"
INCORRECT_PASSWORD = "hesterverst"


TEST_CASES = [
    _TestCase(
        name="SSHA",
        method=Cerebrum.auth.AuthTypeSSHA,
        password=CORRECT_PASSWORD,
        salt="ABCDEFGI",
        cryptstring="qBVr/e8BtH7dw2h09V8WL0jxEaxBQkNERUZHSQ==",
    ),
    _TestCase(
        name="SHA-256-crypt",
        method=Cerebrum.auth.AuthTypeSHA256,
        password=CORRECT_PASSWORD,
        salt="$5$ABCDEFGI",
        cryptstring="$5$ABCDEFGI$wRL35zTjgAhecyc9CWv5Id.qsz5RZqXvDD3EXmlkUJ4",
    ),
    _TestCase(
        name="SHA-512-crypt",
        method=Cerebrum.auth.AuthTypeSHA512,
        password=CORRECT_PASSWORD,
        salt="$6$ABCDEFGI",
        cryptstring=(
            "$6$ABCDEFGI$s5rS3hTF2FJrqxToloyKaOcmUwFMVvEft"
            "Yen3WjaetYz726AFZQkI572G0o/bO9BWC86Sae1QjMUe7TZYBeYg1"
        ),
    ),
    _TestCase(
        name="MD5-crypt",
        method=Cerebrum.auth.AuthTypeMD5,
        password=CORRECT_PASSWORD,
        salt="$1$ABCDEFGI",
        cryptstring="$1$ABCDEFGI$iO4CKjwcmvejNZ7j1MEW./",
    ),
    _TestCase(
        name="MD4-NT",
        method=Cerebrum.auth.AuthTypeMD4NT,
        password=CORRECT_PASSWORD,
        salt="",  # unsalted cryptstring
        cryptstring="5DDE3A6B19D3DEB6B63E304A5574A193",
    ),
    _TestCase(
        name="plaintext",
        method=Cerebrum.auth.AuthTypePlaintext,
        password=CORRECT_PASSWORD,
        salt="",  # unsalted cryptstring
        cryptstring="hesterbest",
    ),
    _TestCase(
        name="md5-unsalted",
        method=Cerebrum.auth.AuthTypeMD5Unsalt,
        password=CORRECT_PASSWORD,
        salt="",  # unsalted cryptstring
        cryptstring="2b403476f80bc3c1b295fe0459a36f26",
    ),
]


@pytest.mark.parametrize(
    "cls, password",
    [(tc.method, tc.password) for tc in TEST_CASES],
    ids=[tc.name for tc in TEST_CASES],
)
def test_generate_cryptstring(cls, password):
    """ check that we can generate a new cryptstring from a password """
    method = cls()
    assert method.encrypt(password)


@pytest.mark.parametrize(
    "cls, password",
    [(tc.method, tc.password) for tc in TEST_CASES],
    ids=[tc.name for tc in TEST_CASES],
)
def test_ensure_text(cls, password):
    method = cls()
    bytestring = password.encode("utf-8")
    with pytest.raises(ValueError):
        method.encrypt(bytestring)


@pytest.mark.parametrize(
    "cls, salt, password, cryptstring",
    [(tc.method, tc.salt, tc.password, tc.cryptstring) for tc in TEST_CASES],
    ids=[tc.name for tc in TEST_CASES],
)
def test_recreate_cryptstring(cls, salt, password, cryptstring):
    """ check that we can recreate a cryptstring from a password + salt """
    method = cls()
    assert method.encrypt(password, salt=salt) == cryptstring


@pytest.mark.parametrize(
    "cls, salt, password, cryptstring",
    [(tc.method, tc.salt, tc.password, tc.cryptstring) for tc in TEST_CASES],
    ids=[tc.name for tc in TEST_CASES],
)
def test_recreate_cryptstring_from_bytes(cls, salt, password, cryptstring):
    method = cls()
    salt = salt.encode("utf-8")
    password = password.encode("utf-8")
    assert method.encrypt(password, salt=salt, binary=True) == cryptstring


@pytest.mark.parametrize(
    "cls, password, cryptstring",
    [(tc.method, tc.password, tc.cryptstring) for tc in TEST_CASES],
    ids=[tc.name for tc in TEST_CASES],
)
def test_verify_cryptstring(cls, password, cryptstring):
    """ check that we can verify a password against a given cryptstring """
    method = cls()
    assert method.verify(password, cryptstring)


@pytest.mark.parametrize(
    "cls, cryptstring",
    [(tc.method, tc.cryptstring) for tc in TEST_CASES],
    ids=[tc.name for tc in TEST_CASES],
)
def test_verify_invalid_password(cls, cryptstring):
    """ check that we can verify a password against a given cryptstring """
    method = cls()
    assert not method.verify(INCORRECT_PASSWORD, cryptstring)


# TODO: The following tests should be moved to a voip test module

def test_ha1md5_encrypt():
    """ check that we can create a http digest hash. """
    name = "olanordmann"
    realm = "myorg"
    passwd = CORRECT_PASSWORD
    cryptstring = "05f96542dbba4d8c53dc83635985df97"
    assert encrypt_ha1_md5(name, realm, passwd) == cryptstring


def test_ha1md5_verify():
    name = "olanordmann"
    realm = "myorg"
    password = CORRECT_PASSWORD
    cryptstring = "05f96542dbba4d8c53dc83635985df97"
    assert verify_ha1_md5(name, realm, password, cryptstring)


def test_ha1md5_invalid_password():
    name = "olanordmann"
    realm = "myorg"
    password = INCORRECT_PASSWORD
    cryptstring = "05f96542dbba4d8c53dc83635985df97"
    assert not verify_ha1_md5(name, realm, password, cryptstring)


def test_ha1md5_invalid_realm():
    name = "olanordmann"
    realm = "another-org"
    password = CORRECT_PASSWORD
    cryptstring = "05f96542dbba4d8c53dc83635985df97"
    assert not verify_ha1_md5(name, realm, password, cryptstring)
