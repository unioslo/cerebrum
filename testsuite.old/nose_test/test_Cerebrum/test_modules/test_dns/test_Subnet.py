#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""

Basic tests for Cerebrum/modules/dns/Subnet.py.


"""
from nose.tools import assert_raises

import cerebrum_path

from Cerebrum.modules.dns.Subnet import *

class test_Subnet_is_valid_subnet():
    """Tests for is_valid_subnet-function in class Subnet."""
    
    def test_valid_subnet_validation(self):
        """Fully qualified subnet: 123.123.123.0/14"""
        assert Subnet.is_valid_subnet("123.123.123.0/14")


    def test_partial_subnet_validation(self):
        """Partially qualified subnet: 123.123.123/14"""
        assert Subnet.is_valid_subnet("123.123.123/14")


    def test_ip_only(self):
        """IP only should fail"""
        assert_raises(SubnetError, Subnet.is_valid_subnet, "123.123.123.123")


    def test_element_out_of_range(self):
        """Non-valid IPs should fail"""
        assert_raises(SubnetError, Subnet.is_valid_subnet, "256.123.123.123/20")
        assert_raises(SubnetError, Subnet.is_valid_subnet, "123.256.123.123/20")
        assert_raises(SubnetError, Subnet.is_valid_subnet, "123.123.256.123/20")
        assert_raises(SubnetError, Subnet.is_valid_subnet, "123.123.123.256/20")


    def test_not_enough_elements(self):
        """Subnets with 1 or 2 elements (only) should fail"""
        assert_raises(SubnetError, Subnet.is_valid_subnet, "123.123/10")
        assert_raises(SubnetError, Subnet.is_valid_subnet, "123/4")



class test_Subnet_calculate_subnet_mask():
    """Tests for is_valid_subnet-function in class Subnet."""

    def test_22_net(self):
        """Calculate subnetmask for 22-net"""
        assert Subnet.calculate_subnet_mask(2180009984, 2180011007) == 22

    def test_23_net(self):
        """Calculate subnetmask for 23-net"""
        assert Subnet.calculate_subnet_mask(2179991552, 2179992063) == 23

    def test_24_net(self):
        """Calculate subnetmask for 24-net"""
        assert Subnet.calculate_subnet_mask(2179990272, 2179990527) == 24

    def test_25_net(self):
        """Calculate subnetmask for 25-net"""
        assert Subnet.calculate_subnet_mask(2179990144, 2179990271) == 25

    def test_26_net(self):
        """Calculate subnetmask for 26-net"""
        assert Subnet.calculate_subnet_mask(2179989504, 2179989567) == 26

    def test_27_net(self):
        """Calculate subnetmask for 27-net"""
        assert Subnet.calculate_subnet_mask(2179991232, 2179991263) == 27

    def test_28_net(self):
        """Calculate subnetmask for 28-net"""
        assert Subnet.calculate_subnet_mask(2179989568, 2179989583) == 28

    def test_29_net(self):
        """Calculate subnetmask for 29-net"""
        assert Subnet.calculate_subnet_mask(2179989584, 2179989591) == 29

    def test_30_net(self):
        """Calculate subnetmask for 30-net"""
        assert Subnet.calculate_subnet_mask(2179995940, 2179995943) == 30

    def test_31_net(self):
        """Calculate subnetmask for 31-net"""
        assert Subnet.calculate_subnet_mask(2179995942, 2179995943) == 31

    def test_32_net(self):
        """Calculate subnetmask for 32-net"""
        assert Subnet.calculate_subnet_mask(2179996133, 2179996133) == 32


