#!/usr/bin/env python
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

"""Run all ceresync tests"""

import unittest

def suite():
    tests = "config sync".split()
    try:
        import ldap
        tests.append("directory")
    except ImportError: 
        print "Module 'ldap' not installed, ignoring test 'directory'"
    return unittest.defaultTestLoader.loadTestsFromNames(tests)

if __name__ == "__main__":
    unittest.main(defaultTest='suite')

# arch-tag: 151921e5-3c85-4f10-8764-6c7e2c3337a2
