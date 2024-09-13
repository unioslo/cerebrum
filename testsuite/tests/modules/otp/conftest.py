# encoding: utf-8
"""
Test fixtures for :mod:`Cerebrum.modules.otp` tests
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

import pytest

from Cerebrum.testutils import file_utils


# RSA keys in PEM format for the default key-alg
KEYS = textwrap.dedent(
    """
    -----BEGIN PRIVATE KEY-----
    MIICeQIBADANBgkqhkiG9w0BAQEFAASCAmMwggJfAgEAAoGBALM+kl8IDsysMnOS
    BmaFf3tAWzxKjz+wxv4swrZKk1y2hreRsl/qbfcMPbJmIzWxsGQs+mwyhS9zgGHT
    RF8pybt5TcshnnIWK7siqFlRJiAco72lQTc5Jp/c/62CeSve/H3j+q/AxyEJIVh/
    dWShh9ijcRPmQ2RGMyJEW4Apcxb7AgMBAAECgYEArDRaRYilR0fMdLH/CjIJhu0O
    ej8bntIEbB+utZmyN+l4RhZo67N7EFUnVSTBgQ2EbMm1kYt731m1JsblMhQgpSsV
    6A58n7pQKyQQomL8Kfg1B1O1vEgy8RRGqSGzYSir2RWLg1ItXhCTjQie2xeAI9Xj
    ZEmkA/hXeeSf6khoyyECQQDjL1nWdulddLJy5fyVfAGslrc2xpEhRFPCcZlF63UJ
    EmfOJhdqf4ZH2XKdb39fayVWtQfXDgDsqRZsZlPGQctxAkEAyfqZ6xIjdxJfQJQi
    qmxG7JnaU3He36K796eP9KqvJZXVh5qBomkXEcuDGPti68OaeCQWk+SrdOm6SBhv
    6IEbKwJBAIvolULmaEENpPfteuf0PnOzPZGWJ7p9Abg1jVbp8mFr3FGwU6taba/B
    0jvydlak/ZGwWuutzBPy7cREIENwMYECQQCt2BySz9HmstF5bAdKWFfTXbklCWWj
    ZxYSWw70r9SArS5UwQ/DEmDg2CHGZtkFxB44OheUw8Uvo9zKIP5xSG5xAkEAmj2t
    OqXUCbKOVRrYFuElxmFOr1C/23hkfa6NiOur0mGrj4iNxvE25VeBF6SfdXgANnrT
    NSq3uMqmK//COAH/UA==
    -----END PRIVATE KEY-----
    -----BEGIN PUBLIC KEY-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3U5x3dMg18Q203lj1AXu
    /Bdt5lnauRSZ/p4t9rOLAu1AttEk/Tid83qbRjl0jwtunf7hjeQitXDm/17devuK
    rZt2xUOwC01x1Rl8IkbkRBkktITkdKoXn5dsr2TP1U3korazbN5yFVTj6EM95KLO
    PhKwLYu6Ulv0j8PoMsR9MB7kIGEobN0j1SWteVLs/t54uW3b9gG4Vr0nuyamfqKi
    VNphDC0aQPy1HvNPmkitAA+TdI1cIUneDjM69M+M2j0n4FQBrnoL+bCTLt6UQcpQ
    4wOz+enC2B5w3qdgkGv3bY6C0Vzq5yH5MwIWTkp/Xb7H3J4HFvbTzPgZHZblw7WR
    1wIDAQAB
    -----END PUBLIC KEY-----
    """
).lstrip()


@pytest.fixture(scope='module')
def secrets_dir():
    with file_utils.tempdir_ctx(prefix="test-otp-") as path:
        yield path


@pytest.fixture(scope='module', autouse=True)
def keys_file_secret(secrets_dir):
    with file_utils.tempfile_ctx(secrets_dir, suffix=".pem") as filename:
        file_utils.write_text(filename, KEYS)
        yield "file:" + filename
