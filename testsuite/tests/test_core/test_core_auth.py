#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for Cerebrum.auth """
from __future__ import unicode_literals

import pytest

import Cerebrum.auth
import Cerebrum.modules.no.uio.voip.voipAuthAccountMixin

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
def voipAuthAccount():
    return Cerebrum.modules.no.uio.voip.voipAuthAccountMixin


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


def test_ssha_encrypt():
    method = Cerebrum.auth.AuthTypeSSHA()
    _hash = method.encrypt("hesterbest", salt="ABCDEFGI")
    assert _hash == "qBVr/e8BtH7dw2h09V8WL0jxEaxBQkNERUZHSQ=="


def test_sha256_encrypt():
    method = Cerebrum.auth.AuthTypeSHA256()
    _hash = method.encrypt("hesterbest", salt="$5$ABCDEFGI")
    assert _hash == "$5$ABCDEFGI$wRL35zTjgAhecyc9CWv5Id.qsz5RZqXvDD3EXmlkUJ4"


def test_sha512_encrypt():
    method = Cerebrum.auth.AuthTypeSHA512()
    _hash = method.encrypt("hesterbest", salt="$6$ABCDEFGI")
    expect = ("$6$ABCDEFGI$s5rS3hTF2FJrqxToloyKaOcmUwFMVvEft"
              "Yen3WjaetYz726AFZQkI572G0o/bO9BWC86Sae1QjMUe7TZYBeYg1")
    assert _hash == expect


def test_md5crypt_encrypt():
    method = Cerebrum.auth.AuthTypeMD5()
    _hash = method.encrypt("hesterbest", salt="$1$ABCDEFGI")
    assert _hash == "$1$ABCDEFGI$iO4CKjwcmvejNZ7j1MEW./"


def test_md4nt_encrypt():
    method = Cerebrum.auth.AuthTypeMD4NT()
    _hash = method.encrypt("hesterbest", salt="ABC")
    assert _hash == "5DDE3A6B19D3DEB6B63E304A5574A193"


def test_plaintext_encrypt():
    method = Cerebrum.auth.AuthTypePlaintext()
    _hash = method.encrypt("hesterbest", salt="dont-care")
    assert _hash == "hesterbest"


def test_md5unsalt_encrypt():
    method = Cerebrum.auth.AuthTypeMD5Unsalt()
    _hash = method.encrypt("hesterbest", salt="dont-care")
    assert _hash == "2b403476f80bc3c1b295fe0459a36f26"


def test_ha1md5_encrypt(voipAuthAccount):
    name = 'olanordmann'
    realm = 'myorg'
    passwd = 'hesterbest'

    _hash = voipAuthAccount.encrypt_ha1_md5(name, realm, passwd)
    assert _hash == "05f96542dbba4d8c53dc83635985df97"


def test_ha1md5_verify(voipAuthAccount):
    name = 'olanordmann'
    realm = 'myorg'
    right_passwd = 'hesterbest'
    wrong_passwd = 'hesterverst'
    _hash = voipAuthAccount.encrypt_ha1_md5(name, realm, right_passwd)

    assert voipAuthAccount.verify_ha1_md5(name, realm, right_passwd, _hash)
    assert not voipAuthAccount.verify_ha1_md5(name, realm, wrong_passwd, _hash)
