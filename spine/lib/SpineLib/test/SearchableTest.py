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

from SpineLib.Date import Date
from SpineLib.Builder import Builder, Attribute
from SpineLib.Searchable import Searchable
from SpineLib.DatabaseClass import DatabaseAttr

import unittest
from sets import Set

class SearchableTest(unittest.TestCase):
    def setUp(self):
        class TestClass(Builder, Searchable):
            table = 'testing'
            primary = (
                DatabaseAttr('primary', table, str, write=True),
            )
            slots = (
                DatabaseAttr('str_ro', table, str),
                DatabaseAttr('str_rw', table, str, write=True),
                DatabaseAttr('int_ro', table, int),
                DatabaseAttr('int_opt', table, int, optional=True),
                DatabaseAttr('date_rw', table, Date, write=True),
            )
        self.cls = TestClass

    def test_build_search_class(self):
        self.cls.build_search_class()

        assert hasattr(self.cls, 'search_class')
        self.assertAttrs(self.cls)

    def test_build_search_class__primary_not_searchable(self):
        self.cls.build_search_class()
        sc = self.cls.search_class

        assert not hasattr(sc, 'get_primary')
        assert not hasattr(sc, 'set_primary')

    def test_build_search_class__non_dbattr(self):
        self.cls.slots = (Attribute('str_ro', str),)
        self.cls.build_search_class()

        assert hasattr(self.cls, 'search_class')
        sc = self.cls.search_class
        assert not hasattr(sc, 'set_str_ro')
        assert not hasattr(sc, 'get_str_ro')

    def assertAttrs(self, cls):
        """Runs through the attributes in a Builder class and asserts their sanity."""
        sc = cls.search_class
        assert hasattr(sc, 'search')
        assert sc.search.signature == [cls]

        for attr in cls.slots:
            assert hasattr(sc, 'get_%s' % attr.name)
            assert hasattr(sc, 'set_%s' % attr.name)
            if attr.data_type == str:
                assert hasattr(sc, 'get_%s_like' % attr.name)
                assert hasattr(sc, 'set_%s_like' % attr.name)
            elif attr.data_type == Date or \
                    attr.data_type == int:
                for name in 'less_than', 'more_than':
                    assert hasattr(sc, 'get_%s_%s' % (attr.name, name))
                    assert hasattr(sc, 'set_%s_%s' % (attr.name, name))

            if attr.optional:
                assert hasattr(sc, 'get_%s_exists' % attr.name)
                assert hasattr(sc, 'set_%s_exists' % attr.name)
            else:
                assert not hasattr(sc, 'get_%s_exists' % attr.name)
                assert not hasattr(sc, 'set_%s_exists' % attr.name)

