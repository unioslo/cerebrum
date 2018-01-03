# -*- coding: utf-8 -*-
#
# Template file for cerebrum_path.py
#
""" Cerebrum path setup. """
import os
import sys

sys.path.append(os.getenv('CONFIG_DIR'))
#sys.path.append("/etc/cerebrum")
#sys.path.append("/usr/local/etc/cerebrum")
sys.path.append("/src/testsuite/testtools")
sys.path.append("/src/testsuite/tests")
