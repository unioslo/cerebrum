#!/usr/bin/env python2.2
#
# $Id$

import unittest

from Cerebrum.tests.OUTestCase import OUTestCase
from Cerebrum.tests.PersonTestCase import PersonTestCase

def suite():
    """Returns a suite containing all the test cases in this module.
       It can be a good idea to put an identically named factory function
       like this in every test module. Such a naming convention allows
       automation of test discovery.
    """

    suite1 = OUTestCase.suite()
    suite2 = PersonTestCase.suite()

    return unittest.TestSuite((suite1,suite2))


if __name__ == '__main__':
    # When this module is executed from the command-line, run all its tests
    unittest.main(defaultTest='suite')
