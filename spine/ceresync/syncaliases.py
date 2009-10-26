#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005, 2006 University of Oslo, Norway
#
# This filebackend is part of Cerebrum.
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

import sys

from ceresync import syncws as sync
from ceresync import config

log = config.logger

def main():
    sync_options = {}
    config.parse_args(config.make_testing_options())
    config.set_testing_options(sync_options)

    try:
        s = sync.Sync()
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        sys.exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        sys.exit(1)

    if config.getboolean('args', 'use_test_backend'):
        import ceresync.backend.test as filebackend
    else:
        import ceresync.backend.file as filebackend

    aliases = filebackend.Alias()
    
    log.debug("Syncronizing aliases")
    aliases.begin(unicode=True)

    try:
        for alias in s.get_aliases(**sync_options):
            log.debug("Processing account '%s@%s'", alias.local_part, alias.domain)
            aliases.add(alias)
    except IOError,e:
        log.error("Exception %s occured, aborting",e)
        aliases.abort()
    else:
        aliases.close()

if __name__ == "__main__":
    main()
