#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
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

# IVR 2008-08-08 FIXME: code duplication (contrib/no/uio/mailman.py)
def validate_address(addr, mode="any"):
    """Make sure e-mail addresses are valid.
    """
    if (re.match(r'[a-z0-9][a-z0-9._-]*[a-z0-9](@|$)', addr) and
        (mode == 'rmlist' or
         (addr.count('@') == 1 and
          re.search(r'@[a-z0-9-]+(\.[a-z0-9]+)+$', addr)))):
        return True
    raise ValueError("illegal address: '%s'" % addr)
# end validate_address


def main():
    host, command, listname = sys.argv[1:4]
    admin = profile = description = None
    validate_address(listname, mode=command)
    
    if command == "newlist":
        admin, profile, description = sys.argv[4:]
        admin = admin.split(",")
        for a in admin:
            validate_address(a)

        args = ["/site/bin/createlist",
                "--listname", listname,
                "--type", '"' + profile + '"',
                "--subject", '"' + description + '"',]
        for a in admin:
            args.extend(("--owner", a))
            
    elif command == "rmlist":
        args = ["/site/bin/closelist", listname]
    else:
        raise ValueError("Unknown command <%s> for sympa list" % command)

    args.insert(0, "PKG=" + host)
    to_exec = " ".join(args)
    args = ["/local/bin/ssh", host, "su", "-", "sympa", "-c",
            "'" + to_exec + ">/dev/null" + "'"]
    os.execv(args[0], args)
# end main


if __name__ == "__main__":
    main()
