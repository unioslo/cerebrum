# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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
#

from SpineLib.Builder import Builder, Attribute

import unittest
from sets import Set

class BuilderTest(unittest.TestCase):
    def setUp(self):
        class TestClass(Builder):
            primary = (
                Attribute('primary', str, write=True),
            )
            slots = (
                Attribute('str_ro', str),
                Attribute('str_rw', str, write=True),
            )
        self.cls = TestClass

    def test_build_methods__empty(self):
        """Make sure that Builder doesn't affect an empty class."""
        self.cls.primary = self.cls.slots = () # Empty the class

        orig = dir(self.cls)
        self.cls.build_methods()
        res = dir(self.cls)

        assert orig == res

    def test_build_methods(self):
        self.cls.build_methods()

        assertAttrs(self.cls)

    def test_build_methods__primary_ro(self):
        self.cls.primary = (
            Attribute('primary', str), # Set primary to ro
        )

        self.cls.build_methods()

        assertAttrs(self.cls)
        assert not hasattr(self.cls, 'set_primary')

    def test_build_methods__altered_method(self):
        """Test that signature, signature_name are overwritten for get methods,
        while signature, signature_name, signature_write and signature_args are
        overwritten for set methods.  Other signature attributes should not be 
        touched."""
        def set_primary(self, value):
            pass
        def get_primary(self):
            pass
        get_signatures = ['', '_name']
        set_signatures = ['', '_name', '_write', '_args']
        for i in get_signatures:
            setattr(get_primary, "signature%s" % i, 'fisk')
        for i in set_signatures:
            setattr(set_primary, "signature%s" % i, 'fisk')
        set_primary.signature_special = 'fisk'
        get_primary.signature_special = 'fisk'
        self.cls.set_primary = set_primary
        self.cls.get_primary = get_primary

        self.cls.build_methods()

        assert self.cls.get_primary.signature_special == 'fisk'
        assert self.cls.set_primary.signature_special == 'fisk'
        assertAttrs(self.cls)

    def test_build_methods__nowrite_with_setter(self):
        """Test that build_methods raises an assertion error if
        the class defines a setter for an attribute with write=False"""
        self.cls.set_str_ro = lambda: 'fisk'
        self.assertRaises(AssertionError, self.cls.build_methods)
    
    def test_build_methods__twice(self):
        """build_methods should be able to run more than once"""
        self.cls.build_methods()
        self.cls.build_methods()

        assertAttrs(self.cls)

def assertAttrs(cls):
    """Runs through the attributes in a Builder class and asserts their sanity."""
    for attr in cls.slots:
        name = 'get_%s' % attr.name
        getter = getattr(cls, name)
        assert getter.signature == attr.data_type
        assert getter.signature_name == name
        if attr.write:
            name = 'set_%s' % attr.name
            setter = getattr(cls, name)
            assert setter.signature == None
            assert setter.signature_name == name
            assert setter.signature_args == [attr.data_type]
            assert setter.signature_write == True

if __name__ == '__main__':
    unittest.main()
