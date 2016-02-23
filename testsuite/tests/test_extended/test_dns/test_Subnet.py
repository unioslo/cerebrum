#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
u""" Tests for dns module IPv4 subnet (Cerebrum.modules.dns.Subnet) """

import pytest

valid_ipv4_subnets = [
    '10.0.0/0',
    '10.0.0.0/0',
    '10.0.0/16',
    '10.0.0/23',
    '10.0.255/31',
    '10.0.255/32',
    '10.0.0.0/23',
    '10.0.0.0/23',
    '10.0.0.0/23',
]

invalid_ipv4_subnets = [
    # Segment values must be in range 0-255
    '256.0.0/26',
    '10.0.256.0/31',
    # Subnet must have 3 or 4 IP-segments
    '10/16',
    '10.0/16',
    '10.0.255.1.1/16',
    # Mask must be between 0 and 32
    '10.0.0.0/-1',
    '10.0.0.0/33',
    '10.0.0.0/64',
    # Must include valid subnet mask
    '10.0.0.1',
    '10.0.0.1/',
    # IPv6 addresses
    '4534:2342:4543::',
    '4534:2342:4543::/10',
]


@pytest.fixture
def subnet_module():
    from Cerebrum.modules.dns import Subnet as module
    return module


@pytest.fixture
def Subnet(subnet_module):
    return getattr(subnet_module, 'Subnet')


@pytest.fixture
def subnet(database, Subnet):
    return Subnet(database)


@pytest.mark.parametrize('cidr', valid_ipv4_subnets)
def test_is_valid_subnet(Subnet, cidr):
    assert Subnet.is_valid_subnet(cidr)


@pytest.mark.parametrize('cidr', invalid_ipv4_subnets)
def test_not_is_valid_subnet(Subnet, cidr):
    assert not Subnet.is_valid_subnet(cidr)


@pytest.mark.parametrize('cidr', valid_ipv4_subnets)
def test_validate_subnet(Subnet, cidr):
    assert Subnet.validate_subnet(cidr)


@pytest.mark.parametrize('cidr', invalid_ipv4_subnets)
def test_validate_subnet_error(Subnet, cidr):
    from Cerebrum.modules.dns.Errors import SubnetError
    with pytest.raises(SubnetError):
        Subnet.validate_subnet(cidr)
