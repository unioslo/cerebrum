#!/usr/bin/python2.2

import cerebrum_path
import cereconf

import os
import sys

# ssh server /bin/sub server user
os.execv(cereconf.SSH, [cereconf.SSH, sys.argv[1],
                        cereconf.SUBSCRIBE_SCRIPT_REMOTE,
                        sys.argv[1:]])
