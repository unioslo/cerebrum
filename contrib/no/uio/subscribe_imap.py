#!/usr/bin/python2.2

import cerebrum_path
import cereconf

import os
import sys

# Run: ssh server /bin/sub action server user
os.execv(cereconf.SSH, [cereconf.SSH, sys.argv[2],
                        cereconf.SUBSCRIBE_SCRIPT_REMOTE] + sys.argv[1:])
