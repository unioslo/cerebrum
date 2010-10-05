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

import sys, os

from ceresync import syncws as sync
from ceresync import config

log = config.logger


def get_altformat(config):
    altformat = config.getboolean('alias', 'altformat', default=False)
    return altformat

def get_emailserver(config):
    emailserver = config.get('alias', 'emailserver', default=os.uname()[1])
    emailserver = config.get('args', 'emailserver', default=emailserver)
    if emailserver == "" or emailserver=="*":
        emailserver = None
    return emailserver

def make_alias_options(config):
    return [
        config.make_option(
            "--emailserver",
            action="store",
            default=None,
            dest="emailserver",
            help="Fetch data for specified emailserver"),
        ]

def main():
    sync_options = {}
    options = config.make_testing_options() + make_alias_options(config)
    config.parse_args(options)
    config.set_testing_options(sync_options)
    sync_options['emailserver'] = get_emailserver(config)

    using_test_backend = config.getboolean('args', 'use_test_backend')
    altformat = get_altformat(config)

    try:
        s = sync.Sync(locking=not using_test_backend)
    except sync.AlreadyRunningWarning, e:
        log.error(str(e))
        sys.exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        sys.exit(1)

    if using_test_backend:
        import ceresync.backend.test as filebackend
    else:
        import ceresync.backend.file as filebackend

    aliases = filebackend.Alias(altformat=altformat)
    
    log.info("Syncronizing aliases")
    aliases.begin(unicode=True)

    try:
        for alias in sorted(s.get_aliases(**sync_options),
                            cmp=lambda x,y:cmp(x.account_name,y.account_name)):
            log.debug("Processing alias '%s@%s'", alias.local_part, 
                      alias.domain)
            aliases.add(alias)
    except Exception, e:
        log.exception("Exception %s occured, aborting",e)
        aliases.abort()
    else:
        aliases.close()

if __name__ == "__main__":
    main()
