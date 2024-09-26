# encoding: utf-8
""" Tests for mod:`Cerebrum.modules.otp.otp_types` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.modules.otp import otp_types

SHARED_SECRET = "HPV3FP52AS3QUF2Q"


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf):
    cereconf.OTP_POLICY = (
        "Cerebrum.modules.otp.otp_types/OtpTypePlaintext",
    )


@pytest.fixture(scope='module')
def otp_type_plaintext():
    return otp_types.OtpTypePlaintext.new()


def test_otp_type_plaintext(otp_type_plaintext):
    plaintext = otp_type_plaintext(SHARED_SECRET)
    assert plaintext == SHARED_SECRET


@pytest.fixture(scope='module')
def otp_type_radius(keys_file_secret):
    return otp_types.OtpTypeRadiusJwe.new(keys_file_secret)


def test_otp_type_radius_jwe(otp_type_radius):
    token = otp_type_radius(SHARED_SECRET)
    assert len(token.split(".")) == 5


@pytest.fixture(scope='module')
def otp_type_feide(keys_file_secret):
    return otp_types.OtpTypeFeideJwe.new(keys_file_secret)


def test_otp_type_feide_jwe(otp_type_feide):
    token = otp_type_feide(SHARED_SECRET)
    assert len(token.split(".")) == 5


@pytest.fixture(scope='module')
def otp_policy(otp_type_plaintext, otp_type_radius, otp_type_feide):
    return otp_types.OtpPolicy({
        'test-plain': otp_type_plaintext,
        'test-radius': otp_type_radius,
        'test-feide': otp_type_feide,
    })


def test_otp_policy_types(otp_policy):
    expect = set(('test-plain', 'test-radius', 'test-feide'))
    assert set(otp_policy.otp_types) == expect


def test_otp_policy_call(otp_policy):
    secrets = dict(otp_policy(SHARED_SECRET))
    assert secrets['test-plain'] == SHARED_SECRET
    assert secrets['test-radius']
    assert secrets['test-feide']


def test_get_policy():
    policy = otp_types.get_policy()
    assert policy.otp_types == (otp_types.OtpTypePlaintext.otp_type,)
