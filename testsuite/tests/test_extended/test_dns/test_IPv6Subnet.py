#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
u""" Tests for dns module IPv4 subnet (Cerebrum.modules.dns.Subnet) """

import pytest

valid_ipv6_subnets = [
    '4534:2342:4543::202/0',
    '4534:2342:4543::202/128',
    '4534:2342:4543::/63',
    '2342:3252:2352:2352:2352:2535:6436:1/0',
    '2342:3252:2352:2352:2352:2535:6436:1/1',
    '2342:3252:2352:2352:2352:2535:6436:1/127',
    '2342:3252:2352:2352:2352:2535:6436:1/128',
    '2342::154/64',
]

invalid_ipv6_subnets = [
    # Segment values must be in range 0-FFFF
    '45g4:2342:4543::202/64',
    # Mask must be between 0 and 32
    '4534:2342:4546::/-1',
    '4534:2342:4546::/129',
    '4534:2342:4546::/255',
    # Must include valid subnet mask
    '4534:2342:4543::',
    '4534:2342:4543::/',
    # IPv4 addresses
    '10.0.0.1',
    '10.0.0/23',
    '10.0.255/31',
]


@pytest.fixture
def subnet_module():
    from Cerebrum.modules.dns import IPv6Subnet as module
    return module


@pytest.fixture
def Subnet(subnet_module):
    return getattr(subnet_module, 'IPv6Subnet')


@pytest.fixture
def subnet(database, Subnet):
    return Subnet(database)


@pytest.mark.parametrize('cidr', valid_ipv6_subnets)
def test_is_valid_subnet(Subnet, cidr):
    assert Subnet.is_valid_subnet(cidr)


@pytest.mark.parametrize('cidr', invalid_ipv6_subnets)
def test_not_is_valid_subnet(Subnet, cidr):
    assert not Subnet.is_valid_subnet(cidr)


@pytest.mark.parametrize('cidr', valid_ipv6_subnets)
def test_validate_subnet(Subnet, cidr):
    assert Subnet.validate_subnet(cidr)


@pytest.mark.parametrize('cidr', invalid_ipv6_subnets)
def test_validate_subnet_error(Subnet, cidr):
    from Cerebrum.modules.dns.Errors import SubnetError
    with pytest.raises(SubnetError):
        Subnet.validate_subnet(cidr)
