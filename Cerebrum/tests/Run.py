#!/usr/bin/env python2.2
#
# $Id$

import unittest

from Cerebrum.tests.OUTestCase import OUTestCase
from Cerebrum.tests.PersonTestCase import PersonTestCase
from Cerebrum.tests.AccountTestCase import AccountTestCase
from Cerebrum.tests import GroupTestCase
from Cerebrum.tests.SQLDriverTestCase import SQLDriverTestCase

def suite():
    """Returns a suite containing all the test cases in this module.
       It can be a good idea to put an identically named factory function
       like this in every test module. Such a naming convention allows
       automation of test discovery.
    """

    suite1 = SQLDriverTestCase.suite()
    suite2 = OUTestCase.suite()
    suite3 = PersonTestCase.suite()
    suite4 = AccountTestCase.suite()
    suite5 = GroupTestCase.suite()
    return unittest.TestSuite((suite1, suite2, suite3, suite4, suite5))


if __name__ == '__main__':
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')
