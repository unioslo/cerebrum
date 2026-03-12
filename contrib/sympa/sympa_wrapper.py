#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2008 University of Oslo, Norway
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


"""This script passes on sympa list commands to the sympa servers.

This is the final step on Cerebrum's side of sympa list administration. The
script passes these commands:

  - list creation
  - list deletion

to the specified sympa server.
"""

import os
import re
import sys

import cereconf
from Cerebrum import Utils

Factory = Utils.Factory
logger = Factory.get_logger("cronjob")


def validate_address(addr, mode="any"):
    """Make sure e-mail addresses are valid."""
    # For more extensive info on e-mail-addresses:
    #    http://en.wikipedia.org/wiki/Email_address
    logger.info("Checking address '%s'; mode: %s" % (addr, mode))
    if (re.match(r"""^                   # Start of string
                     [                   # Allow the following characters...
                     \w                  # - alphanumerics
                     !#-\'*+./=?^`{-~-   # - these special characters
                     ]+                  # ... to occur in any order, at least 1 char
                     (@|$)               # Must be followed by "@" or end-of-string
                     """, addr, re.VERBOSE) and (mode == 'rmlist' or
         (addr.count('@') == 1 and
          re.search(r"""@            # Adding a list must always provide a domain
                        ([\w-]+\.)+  # At least two parts, parts separated by '.'
                        ([\w-]+)     # Each part consists of alphanumerics and/or '-'
                        $            # And nothing more than that.
                        """, addr, re.VERBOSE)))):
        return True
    logger.error("Illegal address: '%s'" % addr)
    raise ValueError("Illegal address: '%s'" % addr)


def main():
    host, command, listname = sys.argv[1:4]
    admin = profile = description = None
    remote_user = "cerebrum"
    validate_address(listname, mode=command)
    
    if command == "newlist":
        admin, profile, description = sys.argv[4:]
        admin = admin.split(",")
        for a in admin:
            validate_address(a)

        args = ["/usr/bin/sudo",
                "PKG=%s" % host,
                "/site/bin/createlist",
                "--listname", listname,
                "--type", '"' + profile + '"',
                "--subject", '"' + description + '"',]
        for a in admin:
            args.extend(("--owner", a))
            
    elif command == "rmlist":
        args = ["/usr/bin/sudo", "PKG=%s" % host, "/site/bin/closelist", listname]
    else:
        raise ValueError("Unknown command <%s> for sympa list" % command)

    to_exec = " ".join(args)
    logger.info("Complete command to be run on remote host: '%s'" % to_exec)
    args = ["/usr/bin/ssh", "%s@%s" % (remote_user, host),
            "" + to_exec + " > /dev/null 2>&1" + ""]
    logger.info("Executing command: '%s'" % " ".join(args))
    os.execv(args[0], args)


if __name__ == "__main__":
    main()
