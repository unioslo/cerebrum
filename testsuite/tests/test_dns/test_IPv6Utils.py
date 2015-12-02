#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
Tests for IPv6Utils in dns module - Cerebrum/modules/dns/IPv6Utils.py.
"""

import unittest

import cerebrum_path

from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.dns.IPv6Utils import IPv6Utils

class IPUtilsTest(unittest.TestCase):
    """
    Tests the atomic methods for validating IPv6-addresses.
    """

    def test_verify(self):

        # Valid IPv6-entries that should pass

        self.assertTrue(IPv6Utils.is_valid_ipv6('4534:2342:4543::202'))
        self.assertTrue(IPv6Utils.is_valid_ipv6('4534:2342:4543::'))
        self.assertTrue(IPv6Utils.is_valid_ipv6('2342:3252:2352:2352:2352:2535:6436:1'))
        self.assertTrue(IPv6Utils.is_valid_ipv6('2342::154'))

        # Invalid IPv6-entries that should not pass

        # Only 0-FFFF should be accepted values
        self.assertFalse(IPv6Utils.is_valid_ipv6('4534:2342:4546::/64'))
        self.assertFalse(IPv6Utils.is_valid_ipv6('ffxe::1'))

        # Max 8 segments
        self.assertFalse(IPv6Utils.is_valid_ipv6('2342:3252:2352:2352:2352:2535:6436:1:1'))
