# -*- coding: iso-8859-1 -*-
#
#   Get time in platform-dependent way
#

import os
from sys import platform, exit, stderr

if platform == 'mac':
  import MacOS
  def time():
    return MacOS.GetTicks() / 60.0
  timekind = "real"
elif hasattr(os, 'times'):
  def time():
    t = os.times()
    return t[0] + t[1]
  timekind = "cpu"
else:
  stderr.write(
    "Don't know how to get time on platform %s\n" % repr(platform))
  exit(1)

# arch-tag: 4ea742b1-d908-41a2-9222-5dbcbdb9849c
