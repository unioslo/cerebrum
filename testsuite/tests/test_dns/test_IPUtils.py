#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
Tests for IPUtils in dns module - Cerebrum/modules/dns/IPUtils.py.
"""

import unittest

import cerebrum_path

from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.dns.IPUtils import IPUtils

class IPUtilsTest(unittest.TestCase):
    """
    Tests the atomic methods for validating/parsing IPv4-addresses.
    """

    def test_is_valid_ipv4(self):

        # Valid IPv4-entries that should pass

        self.assertTrue(IPUtils.is_valid_ipv4('10.0'))
        self.assertTrue(IPUtils.is_valid_ipv4('10.0.255'))
        self.assertTrue(IPUtils.is_valid_ipv4('10.0.255.1'))

        # Invalid IPv4-entries that should not pass

        # Only 0-255 should be accepted values
        self.assertFalse(IPUtils.is_valid_ipv4('10.0.256.1'))
        self.assertFalse(IPUtils.is_valid_ipv4('10.0.foo.1'))

        # Max 4 segments
        self.assertFalse(IPUtils.is_valid_ipv4('10.0.255.1.1'))

    def test_parse_ipv4(self):

        # Technically valid IPv4-addresses that contain leading
        # zeroes should raise an error
        self.assertRaises(CerebrumError, IPUtils.parse_ipv4, '010.0.0.10')
        self.assertRaises(CerebrumError, IPUtils.parse_ipv4, '010.0.0.10')
        self.assertRaises(CerebrumError, IPUtils.parse_ipv4, '10.00.0.1')
        self.assertRaises(CerebrumError, IPUtils.parse_ipv4, '10.0.00.1')
        self.assertRaises(CerebrumError, IPUtils.parse_ipv4, '10.0.00.01')

