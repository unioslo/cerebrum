#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

#
# This example shows how one can perform profiling in python
#

import profile
import pstats
import import_SATS

pr = profile.Profile()
pr.calibrate(1000)

pdta = pr.run('import_SATS.main()')

pdta.dump_stats('profile')

s = pstats.Stats('profile')
s.strip_dirs()
s.sort_stats('time').print_stats(20)
