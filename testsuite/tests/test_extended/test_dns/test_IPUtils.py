#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
u""" Tests for dns module IPv4 utils (Cerebrum.modules.dns.IPUtils) """

import pytest

from Cerebrum.modules.dns.IPUtils import IPUtils


def test_is_valid_ipv4():
    # Valid IPv4-entries that should pass
    assert IPUtils.is_valid_ipv4('10.0')
    assert IPUtils.is_valid_ipv4('10.0.255')
    assert IPUtils.is_valid_ipv4('10.0.255.1')


def test_not_is_valid_ipv4():
    # Only 0-255 should be accepted values
    assert not IPUtils.is_valid_ipv4('10.0.256.1')
    assert not IPUtils.is_valid_ipv4('10.0.foo.1')

    # Max 4 segments
    assert not IPUtils.is_valid_ipv4('10.0.255.1.1')


def test_ipv4_prefix_not_allowed():
    # TODO: Should this really raise a bofhd-error?
    from Cerebrum.modules.bofhd.errors import CerebrumError

    # Technically valid IPv4-addresses that contain leading
    # zeroes should raise an error
    for ipaddr in ('010.0.0.10',
                   '010.0.0.10',
                   '10.00.0.1',
                   '10.0.00.1',
                   '10.0.00.01'):
        with pytest.raises(CerebrumError):
            IPUtils.parse_ipv4(ipaddr)
