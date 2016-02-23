#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
u""" Tests for dns module IPv6 utils (Cerebrum.modules.dns.IPv6Utils) """

import pytest
from Cerebrum.modules.dns.IPv6Utils import IPv6Utils


valid_ipv6_addrs = [
    '4534:2342:4543::202',
    '4534:2342:4543::',
    '2342:3252:2352:2352:2352:2535:6436:1',
    '2342::154',
]

invalid_ipv6_addrs = [
    # Only 0-FFFF should be accepted values
    '4534:2342:4546::/64',
    'ffxe::1',
    # Max 8 segments
    '2342:3252:2352:2352:2352:2535:6436:1:1',
]


@pytest.mark.parametrize('addr', valid_ipv6_addrs)
def test_is_valid_ipv6(addr):
    assert IPv6Utils.is_valid_ipv6(addr)


@pytest.mark.parametrize('addr', invalid_ipv6_addrs)
def test_not_is_valid_ipv6(addr):
    assert not IPv6Utils.is_valid_ipv6(addr)
