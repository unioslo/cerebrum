#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
#
# Author: Petter Reinholdtsen <pere@hungry.com>
# Date:   2002-11-06
#
# Test the fødselsnummer class

# Copyright 2002, 2003 University of Oslo, Norway
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

import unittest

from Cerebrum.modules.no import fodselsnr

class fodselsnrTestCase(unittest.TestCase):
    def setUp(self):
        self.invalidnumbers = [
            "01013338728",
            "19055433813",
            ]

        self.validnumbers = [
            # (number, sex, birth date)
            ("01013638728", 0, (1936, 01, 01)),
            ("71057107345", 0, (1971, 05, 31)),
            ("20067647972", 0, (1976, 06, 20)),
            ("30535890168", 0, (1958, 03, 30)),
            ("01015449256", 1, (1954, 01, 01)),
            ("20035322052", 1, (1953, 03, 20)),
            ("19055430813", 1, (1954, 05, 19))
            ]

        self.invalidinfo = [
            ("01013638728", 1, (1867, 01, 01)),
            ("19055430813", 0, (1954, 05, 12))
            ]

    def testIsNumberOK(self):
        "Check if able to separate valid fødelsnummers from invalid"
        for number in self.validnumbers:
            assert( fodselsnr.personnr_ok(number[0]) )
        for number in self.invalidnumbers:
            try:
                nr = fodselsnr.personnr_ok(number)
                raise "Invalid fødelsnr accepted"
            except:
                pass

    def testDate(self):
        "Check if the Date is correctly extracted from fødelsnummers"
        for number in self.validnumbers:
            year, month, day = fodselsnr.fodt_dato(number[0])
            assert( (year, month, day) == number[2] )

        for number in self.invalidinfo:
            year, month, day = fodselsnr.fodt_dato(number[0])
            assert( (year, month, day) != number[2] )

    def testSex(self):
        "Check if the sex is correctly extracted from fødelsnummers"
        for number in self.validnumbers:
            assert( fodselsnr.er_kvinne(number[0]) == number[1] )

        for number in self.invalidinfo:
            assert( fodselsnr.er_kvinne(number[0]) != number[1] )

    def suite():
        suite = unittest.TestSuite()
        suite.addTest(fodselsnrTestCase("testIsNumberOK"))
        suite.addTest(fodselsnrTestCase("testDate"))
        suite.addTest(fodselsnrTestCase("testSex"))
        return suite
    suite=staticmethod(suite)

def suite():
    return fodselsnrTestCase.suite()

if __name__ == "__main__":
    unittest.main()
