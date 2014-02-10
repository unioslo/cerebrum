#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2009 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

# $Id$


""" 
Unittests for Cerebrum/modules/dns/IPNumber.py.

"""

__version__ = "$Revision$"
# $URL$
# $Source$

from nose.tools import assert_raises, unittest

import cerebrum_path

from Cerebrum.Utils import Factory
from Cerebrum.modules.dns.IPNumber import *


def setup_module():
    global database, constants
    database = Factory.get("Database")()


class test_IPNumber_verify_mac_format(unittest.TestCase):
    """Tests for the '_verify_mac_format'-method in IPNumber."""

    def setUp(self):
        self.ipnumber = IPNumber(database)


    def test_valid_mac_adr_standard_format(self):
        """Valid MAC-address on standard format"""
        assert self.ipnumber._verify_mac_format("01:23:45:67:89:ab") == "01:23:45:67:89:ab"


    def test_valid_mac_adr_with_nonstandard_seperators(self):
        """Various valid MAC-addresses with non-standard seperators"""
        assert self.ipnumber._verify_mac_format("01-23-45-67-89-ab") == "01:23:45:67:89:ab"
        assert self.ipnumber._verify_mac_format("01.23.45.67.89.ab") == "01:23:45:67:89:ab"
        assert self.ipnumber._verify_mac_format("01 23 45 67 89 ab") == "01:23:45:67:89:ab"


    def test_valid_mac_adr_using_cisco_format(self):
        """Valid MAC-addresses using Cisco format"""
        assert self.ipnumber._verify_mac_format("0123:4567:89ab") == "01:23:45:67:89:ab"
        assert self.ipnumber._verify_mac_format("0123-4567-89ab") == "01:23:45:67:89:ab"
        assert self.ipnumber._verify_mac_format("0123.4567.89ab") == "01:23:45:67:89:ab"
        assert self.ipnumber._verify_mac_format("0123 4567 89ab") == "01:23:45:67:89:ab"


    def test_valid_mac_adr_with_no_seperators(self):
        assert self.ipnumber._verify_mac_format("0123456789ab") == "01:23:45:67:89:ab"


    def test_valid_mac_adr_with_uppercase(self):
        """Valid MAC-address with uppercase characters"""
        assert self.ipnumber._verify_mac_format("AB:CD:EF:AB:CD:EF") == "ab:cd:ef:ab:cd:ef"
        

    def test_invalid_mac_adr_with_illegal_chars(self):
        """Raise exception when invalid characters are used"""
        assert_raises(DNSError, self.ipnumber._verify_mac_format, "bl:ip:pi:bl:up:pa")


    def test_invalid_mac_adr_with_incorrect_length(self):
        """Raise exception when MAC-adr has incorrect length"""
        assert_raises(DNSError, self.ipnumber._verify_mac_format, "01:23:45:67:89:ab:cd")
        assert_raises(DNSError, self.ipnumber._verify_mac_format, "01:23:45:67:89")


    def test_invalid_mac_adr_with_invalid_seperators(self):
        """Raise exception when MAC-adr has invalid seperator characters"""
        assert_raises(DNSError, self.ipnumber._verify_mac_format, "01/23/45/67/89/ab")
        assert_raises(DNSError, self.ipnumber._verify_mac_format, "010230450670890ab")



