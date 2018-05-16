#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Copyright 2007-2018 University of Oslo, Norway
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

"""Generate ldif files to populate VirtHome's LDAP tree.

This script can generate both user- and group LDIF files.
"""

import getopt
import sys

from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (ldif_outfile,
                                        end_ldif_outfile,
                                        container_entry_string,
                                        entry_string)
from Cerebrum.modules.virthome.LDIFHelper import LDIFHelper

logger = Factory.get_logger("cronjob")


def generate_all(fname):
    """Write user + group LDIF to fname."""
    logger.debug("Generating ldif into %s", fname)

    out = ldif_outfile("ORG", fname)
    out.write(container_entry_string("ORG"))

    helper = LDIFHelper(logger)

    logger.debug("Generating user ldif...")
    out.write(container_entry_string("USER"))
    for user in helper.yield_users():
        dn = user["dn"][0]
        del user["dn"]
        out.write(entry_string(dn, user, False))
    end_ldif_outfile("USER", out, out)

    logger.debug("Generating group ldif...")
    out.write(container_entry_string("GROUP"))
    for group in helper.yield_groups():
        dn = group["dn"][0]
        del group["dn"]
        out.write(entry_string(dn, group, False))
    end_ldif_outfile("GROUP", out)
    logger.debug("Done with group ldif (all done)")


def main(argv):
    opts, junk = getopt.getopt(argv[1:],
                               "f:",
                               ("file=",))

    filename = None

    for option, value in opts:
        if option in ('-f', '--file',):
            filename = value

    if filename:
        generate_all(filename)


if __name__ == "__main__":
    main(sys.argv[:])
