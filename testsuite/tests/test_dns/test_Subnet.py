#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
Tests for Subnet in dns module - Cerebrum/modules/dns/Subnet.py.
"""

import unittest

import cerebrum_path

from Cerebrum.modules.dns.Subnet import Subnet
from Cerebrum.modules.dns.Errors import SubnetError

class SubnetTest(unittest.TestCase):
    """
    Tests the atomic methods for validating subnets.
    """

    def test_is_valid_subnet(self):

        # Valid subnet-entries that should pass

        self.assertTrue(Subnet.is_valid_subnet('10.0.0/0'))
        self.assertTrue(Subnet.is_valid_subnet('10.0.0/16'))
        self.assertTrue(Subnet.is_valid_subnet('10.0.0.0/23'))
        self.assertTrue(Subnet.is_valid_subnet('10.0.255/32'))

        # Invalid subnet-entries that should not pass

        # Only 0-255 should be accepted values
        self.assertFalse(Subnet.is_valid_subnet('256.0.0/26'))
        self.assertFalse(Subnet.is_valid_subnet('10.0.256.0/31'))

        # Subnet must have 3 or 4 IP-segments
        self.assertFalse(Subnet.is_valid_subnet('10/16'))
        self.assertFalse(Subnet.is_valid_subnet('10.0/16'))
        self.assertFalse(Subnet.is_valid_subnet('10.0.255.1.1/16'))

        # Mask must be between 0 and 32
        self.assertFalse(Subnet.is_valid_subnet('10.0.0.0/-1'))
        self.assertFalse(Subnet.is_valid_subnet('10.0.0.0/33'))
        self.assertFalse(Subnet.is_valid_subnet('10.0.0.0/64'))

    def test_validate_subnet(self):

        # Subnet-mask must be specified
        self.assertTrue(Subnet.is_valid_subnet('10.0.255/31'))
        self.assertRaises(SubnetError, Subnet.validate_subnet, '10.0.0.0')

        # Subnet-mask must be between 0 and 32
        self.assertTrue(Subnet.validate_subnet('10.0.0.0/0'))
        self.assertTrue(Subnet.validate_subnet('10.0.0.0/23'))
        self.assertTrue(Subnet.validate_subnet('10.0.255/31'))
        self.assertRaises(SubnetError, Subnet.validate_subnet, '10.0.0.0/-1')
        self.assertRaises(SubnetError, Subnet.validate_subnet, '10.0.0.0/33')

        # Subnet must have 3 or 4 segments
        self.assertTrue(Subnet.validate_subnet('10.0.0.0/23'))
        self.assertTrue(Subnet.validate_subnet('10.0.0/23'))
        self.assertRaises(SubnetError, Subnet.validate_subnet, '10.0/23')
        self.assertRaises(SubnetError, Subnet.validate_subnet, '10/23')
        self.assertRaises(SubnetError, Subnet.validate_subnet, '10.0.0.0.0/23')
