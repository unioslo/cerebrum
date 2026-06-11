#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2026 University of Oslo, Norway
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
"""
Sympa command wrapper.

This script passes on sympa list commands to the sympa servers.  This script
formats the actual commands for our sympa server, and translates the following
commands to actual sympa commands:

``sympa_wrapper.py <host> newlist <listname> <admins> <profile> <description>``
    Creates a new list, <listname>, using sympa host <host>.

    - <listname> must be the full list address
    - <admins> is a comma-separated list of e-mail addresses

``sympa_wrapper.py <host> rmlist <listname>``
    Removes an existing list, <listname>, using sympa host <host>.

    - <listname> may be just the localpart of the email list address.


TODO
----
These commands should probably just be moved into the
``Cerebrum.modules.sympa.commands`` module, rather than using this wrapper
script.

The email address validation should be moved to the sympa request processing
and/or the bofhd-commands that creates sympa requests?.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import re
import sys

import Cerebrum.logutils
# import Cerebrum.logutils.options
from Cerebrum.utils import subproc
from Cerebrum.utils import text_compat

logger = logging.getLogger(__name__)


REGEX_LOCALPART = re.compile(
    r"""
    ^                   # Start of string
    [                   # Allow the following characters...
    \w                  # - alphanumerics
    !#-\'*+./=?^`{-~-   # - these special characters
    ]+                  # ... to occur in any order, at least 1 char
    (@|$)               # Must be followed by "@" or end-of-string
    """,
    re.VERBOSE,
)

REGEX_DOMAIN = re.compile(
    r"""
    @            # Adding a list must always provide a domain
    ([\w-]+\.)+  # At least two parts, parts separated by '.'
    ([\w-]+)     # Each part consists of alphanumerics and/or '-'
    $            # And nothing more than that.
    """,
    re.VERBOSE,
)


def validate_address(addr, mode="any"):
    """Make sure e-mail addresses are valid."""
    # For more extensive info on e-mail-addresses:
    #    http://en.wikipedia.org/wiki/Email_address
    logger.debug("Checking address=%s, mode=%s", repr(addr), repr(mode))

    localpart_ok = REGEX_LOCALPART.match(addr)
    domain_ok = addr.count('@') == 1 and REGEX_DOMAIN.search(addr)

    if (localpart_ok) and (mode == 'rmlist' or domain_ok):
        return True
    logger.error("Illegal address: %s", repr(addr))
    raise ValueError("Illegal address: " + repr(addr))


def main():
    # For now - legacy mode
    Cerebrum.logutils.autoconf("cronjob", None)
    argv = [text_compat.to_text(a) for a in sys.argv]

    host, command, listname = argv[1:4]
    admin = profile = description = None
    remote_user = "cerebrum"
    validate_address(listname, mode=command)

    if command == "newlist":
        admin, profile, description = argv[4:]
        admin = admin.split(",")
        for a in admin:
            validate_address(a)

        sympa_cmd = [
            "/usr/bin/sudo",
            "PKG=%s" % (host,),
            "/site/bin/createlist",
            "--listname", listname,
            "--type", profile,
            "--subject", description,
        ]
        for a in admin:
            sympa_cmd.extend(("--owner", a))

    elif command == "rmlist":
        sympa_cmd = [
            "/usr/bin/sudo",
            "PKG=%s" % (host,),
            "/site/bin/closelist",
            listname,
        ]

    else:
        raise ValueError("Unknown command <%s> for sympa list" % (command,))

    remote_cmd = [
        "/usr/bin/ssh",
        "%s@%s" % (remote_user, host),
        subproc.format_command(sympa_cmd),
    ]
    ret = subproc.run(remote_cmd, retval=(subproc.RETURN_RC,))
    rc = ret[0]
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
