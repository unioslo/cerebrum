# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

"""Cerebrum-tailored wrapper around the 'logging' module.

The 'logging' module, which is bundled with Python 2.3 and onwards,
needs a little bit of configuration before being usable by Cerebrum.
Rather than have each and every Cerebrum script copy-and-paste the
code doing this configuration, we provide this module for doing it.

With this module, any Cerebrum component that wants to log stuff, can
get away with as little setup code as this (which still retains the
configurable flexibility provided by the 'logging' module):

  from Cerebrum import Logging
  logger = Logging.getLogger(NAME_OF_WANTED_LOGGER)

"""

import sys
if sys.version_info >= (2, 3):
    # The 'logging' module is bundled with Python 2.3 and newer.
    import logging
else:
    # Even though the 'logging' module might have been installed with
    # this older-than-2.3 Python, we'd rather not deal with troubles
    # from using too old versions of the module; use the version
    # bundled with Cerebrum.
    from Cerebrum.extlib import logging

# Now, any Cerebrum module that does the equivalent of
#   from Cerebrum import Logging
# should be able to access the real 'logging' module through
# Logging.logging.  For increased ease of use, however, we mirror some
# of the most commonly used constants/functions into this module.

for attr in ('getLogger', 'disable', 'shutdown',
             'ALL', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL', 'CRITICAL'):
    globals().setdefault(attr, getattr(logging, attr))
del attr

# Configure for Cerebrum logging.
import cereconf
logging.fileConfig(cereconf.LOGGING_CONFIGFILE)

# arch-tag: 96c6a522-fdd5-41f5-975d-a25bb69fa8d1
