#! /usr/bin/env python

import glob, os
import unittest

if __name__ == '__main__':
    os.chdir(os.path.dirname(__file__))
    suite = None
    for file in glob.glob('*Test.py'):
        if file == 'Test.py': continue
        module, _ = os.path.splitext(file)
        module = __import__(module)
        s = unittest.defaultTestLoader.loadTestsFromModule(module)
        if not suite:
            suite = s
        else:
            suite = unittest.TestSuite([suite, s])
    unittest.TextTestRunner().run(suite)
