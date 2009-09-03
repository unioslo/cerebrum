#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""

Basic tests for Cerebrum/modules/dns/IntegrityHelper.py.


"""
from nose.tools import assert_raises, unittest

import cerebrum_path

from Cerebrum.Utils import Factory
import Cerebrum.modules.dns
from Cerebrum.modules.dns.IntegrityHelper import *

def setup_module():
    global database, constants
    database = Factory.get("Database")()


class test_Validator_legal_dns_owner_name(unittest.TestCase):
    """Tests the 'legal_dns_owner_name'-method in class Validator."""

    def setUp(self):
        self.validator = Validator(database, dns.ZONE)


    def test_valid_hostnames(self):
        """Accepts valid hostnames"""
        ldon = self.validator.legal_dns_owner_name
        ldon("blubb.uio.no.", dns.DNS_OWNER)
        ldon("42blubb.uio.no.", dns.DNS_OWNER)
        ldon("blubb42.uio.no.", dns.DNS_OWNER)
        ldon("blu-bb.uio.no.", dns.DNS_OWNER)
        ldon("blubb-42.uio.no.", dns.DNS_OWNER)
        ldon("42-blubb.uio.no.", dns.DNS_OWNER)
        ldon("42.uio.no.", dns.DNS_OWNER)


    def test_invalid_hostnames(self):
        """Does not accept invalid hostnames"""
        ldon = self.validator.legal_dns_owner_name
        assert_raises(DNSError, ldon, "-blubb-.uio.no.", dns.DNS_OWNER)
        assert_raises(DNSError, ldon, "-blubb.uio.no.", dns.DNS_OWNER)
        assert_raises(DNSError, ldon, "blubb-.uio.no.", dns.DNS_OWNER)
        assert_raises(DNSError, ldon, "blibb#blubb.uio.no.", dns.DNS_OWNER)
        assert_raises(DNSError, ldon, "-.uio.no.", dns.DNS_OWNER)
        assert_raises(DNSError, ldon, "blibb--blubb.uio.no.", dns.DNS_OWNER)


    def test_valid_srv_hostnames(self):
        """Accepts valid service-hostnames"""
        ldon = self.validator.legal_dns_owner_name
        # Should allow the same as for regular dns-owners, hence
        # identical tests.
        ldon("blubb.uio.no.", dns.SRV_OWNER)
        ldon("42blubb.uio.no.", dns.SRV_OWNER)
        ldon("blubb42.uio.no.", dns.SRV_OWNER)
        ldon("blu-bb.uio.no.", dns.SRV_OWNER)
        ldon("blubb-42.uio.no.", dns.SRV_OWNER)
        ldon("42-blubb.uio.no.", dns.SRV_OWNER)
        ldon("42.uio.no.", dns.SRV_OWNER)
        # But also allow use of '_' in various places
        ldon("_blubb.uio.no.", dns.SRV_OWNER)
        ldon("42_blubb.uio.no.", dns.SRV_OWNER)
        ldon("blubb42_.uio.no.", dns.SRV_OWNER)
        ldon("_blu-bb.uio.no.", dns.SRV_OWNER)
        ldon("_sip._udp.nortel-gw.voip.",dns.SRV_OWNER )


    def test_invalid_srv_hostnames(self):
        """Does not accept invalid service-hostnames"""
        # Should invalidate the same as for regular dns-owners, hence
        # identical tests.
        ldon = self.validator.legal_dns_owner_name
        assert_raises(DNSError, ldon, "-blubb-.uio.no.", dns.SRV_OWNER)
        assert_raises(DNSError, ldon, "-blubb.uio.no.", dns.SRV_OWNER)
        assert_raises(DNSError, ldon, "blubb-.uio.no.", dns.SRV_OWNER)
        assert_raises(DNSError, ldon, "blibb#blubb.uio.no.", dns.SRV_OWNER)
        assert_raises(DNSError, ldon, "-.uio.no.", dns.SRV_OWNER)
        assert_raises(DNSError, ldon, "blibb--blubb.uio.no.", dns.SRV_OWNER)
        # But also make sure that double underscores aren't allowed
        assert_raises(DNSError, ldon, "blibb__blubb.uio.no.", dns.SRV_OWNER)


