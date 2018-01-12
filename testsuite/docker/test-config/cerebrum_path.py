# -*- coding: utf-8 -*-
#
# Template file for cerebrum_path.py
#
""" Cerebrum path setup. """
import os
import sys

sys.path.append(os.getenv('TEST_CONFIG_DIR'))
sys.path.append(os.path.join(os.getenv('TEST_CONFIG_DIR'), os.getenv('INST')))
sys.path.append("/src/testsuite/testtools")
sys.path.append("/src/testsuite/tests")
