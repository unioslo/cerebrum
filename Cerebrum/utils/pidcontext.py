#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2018 University of Oslo, Norway
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

"""This module contains a simple PID file locking tool.

>>> from pidcontext import Pid
...     with Pid():
...         do_something()

Runs do_something() only if a lockfile for the program is acquirable. A warning
stating '<filename> is locked' is logged and SystemExit is raised if the
lockfile is not acquirable.
"""

from Cerebrum.Utils import Factory

from cereconf import LOCKFILE_DIR

from pid import PidFile
from pid import PidFileAlreadyLockedError

LOGGER = Factory.get_logger()


class Pid(object):
    def __init__(self):
        self.pid = PidFile(piddir=LOCKFILE_DIR)

    def __enter__(self):
        try:
            self.pid.__enter__()
        except PidFileAlreadyLockedError:
            LOGGER.warn('%s is locked', self.pid.filename)
            raise SystemExit()
        return self

    def __exit__(self, exc_type=None, exc_value=None, exc_tb=None):
        self.pid.__exit__()
