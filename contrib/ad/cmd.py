#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
Run commands (in cmd.exe through winrm) on a Windows machine.

This script is for running generic commands against Windows and AD.

If you want to run powershell commands, you could either run::

    cmd.py powershell.exe ...

or you could just use L{powershell.py}, which sets up a bit more for you, e.g.
credentials for the AD environment.

Examples:
::

    # Get the WinRM configuration:
    winrm get winrm/config

Note that, due to limitations in the communication with WinRM, the code have to
finish execution before you could see the result. You will therefore not be
able to run a cmd shell, or any other shell, interactively. This might change
if we get more time working with the WinRM protocol.

Don't forget to escape the dollar and other Windows related characters in your
shell!
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import adconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.ad2 import cli


logger = logging.getLogger(__name__)
description = __doc__.strip().splitlines()[0]
epilog = "\n".join(__doc__.strip().splitlines()[1:]).strip()


def main(argv=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=description,
        epilog=epilog,
    )
    parser.add_argument(
        "command",
        nargs="+",
    )

    get_client = cli.add_winrm_subparser(parser)
    Cerebrum.logutils.options.install_subparser(
        parser,
        defaults={
            # Interactive script - disable sentry by default
            Cerebrum.logutils.options.OPTION_SENTRY: False,
        },
    )

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("console", args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    client = get_client(adconf.SYNCS, args)
    client._winrs_skip_cmd_shell = False
    client.connect()

    command = " ".join(args.command)
    logger.info("Running command: %s", command)
    try:
        out = client.run(command)
    finally:
        client.close()

    for outtype in ('stderr', 'stdout'):
        data = out.get(outtype)
        if data:
            print('%s:' % outtype.upper())
            print(data)
            print()
    logger.info("Done")


if __name__ == '__main__':
    main()
