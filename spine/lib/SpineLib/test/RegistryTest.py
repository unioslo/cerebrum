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

from SpineLib import Registry
from SpineLib.Builder import Builder, Attribute
from SpineLib.Searchable import Searchable
from SpineLib.Dumpable import Dumpable

import unittest

class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = Registry.Registry()

    def tearDown(self):
        del self.registry

    def test_register_empty_class(self):
        """Test that registering a class works, and gives us
        the same class when we retrieve it.
        """
        class TestClass(Builder):
            pass

        self.registry.register_class(TestClass)
        cls = self.registry.TestClass

        assert cls == TestClass

    def test_register_class(self):
        """Test that a class gets built properly when it gets registered."""
        class TestClass(Builder):
            primary = (
                Attribute('primary', str),
            )
            slots = (
                Attribute('slots', str, write=True),
            )

        self.registry.register_class(TestClass)
        cls = self.registry.TestClass

        assert hasattr(cls, "get_primary")
        assert not hasattr(cls, "set_primary")
        assert hasattr(cls, "get_slots")
        assert hasattr(cls, "set_slots")
        assert cls == TestClass

    def test_register_search_class(self):
        class TestClass(Builder, Searchable):
            pass

        self.registry.register_class(TestClass)
        cls = self.registry.TestClass

        assert hasattr(cls, "search_class")
        assert hasattr(cls.search_class, "search")
        assert not hasattr(cls, "dumper_class")

    def test_register_dump_class(self):
        class TestClass(Builder, Dumpable):
            pass

        self.registry.register_class(TestClass)
        cls = self.registry.TestClass

        assert hasattr(cls, "dumper_class")
        assert hasattr(cls.dumper_class, "dump")
        assert not hasattr(cls, "search_class")

    def test_register_search_and_dump_class(self):
        class TestClass(Builder, Searchable, Dumpable):
            pass

        self.registry.register_class(TestClass)
        cls = self.registry.TestClass

        assert hasattr(cls, "dumper_class")
        assert hasattr(cls.dumper_class, "dump")
        assert hasattr(cls, "search_class")
        assert hasattr(cls.search_class, "search")
        assert hasattr(cls.search_class, "get_dumpers")
        assert hasattr(cls.search_class, "dump")

    def test_extend_class(self):
        class TestClass(Builder):
            pass

        self.registry.register_class(TestClass)
        cls = self.registry.TestClass

        TestClass.register_attribute(Attribute('slots', str, write=True))

        self.registry.register_class(TestClass)

if __name__ == '__main__':
    unittest.main()
