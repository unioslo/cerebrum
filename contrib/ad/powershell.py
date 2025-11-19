#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2025 University of Oslo, Norway
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
Run powershell commands on a Windows host.

The script auto-runs some helpers (unless --clean is given) to interact with
Active Directory as well:
::

    $cred = New-Object System.Management.Automation.PSCredential(...)
    Import-Module ActiveDirectory

The ``$cred`` value contains the credentials for the domain admin account, and
can be used in AD cmdlets:
::

    # See all attributes for an account as registered in AD:
    Get-ADuser -Credential '$cred' -Properties '*' USERNAME

    # Get information about the AD forest we're in:
    Get-ADForest -Credential '$cred' -Current LocalComputer

    # Get information about the AD domain we're in:
    Get-ADDomain -Credential '$cred' -Current LocalComputer

    # Get information about the Directory Server:
    Get-ADRootDSE -Credential '$cred'

    # Get the password policy of the domain:
    Get-ADDefaultDomainPasswordPolicy -Credential '$cred' \\
        -Current LocalComputer

    # To unlock an account that has tried to authenticate too many times:
    Unlock-ADAccount -Credential '$cred' USERNAME

Due to some limitations in the winrm client, the code have to finish execution
before you can see the result.  You'll not be able to e.g. start a new session
through Enter-PSSession and add more commands to that session - everything has
to be executed in one go.

Don't forget to escape special characters (e.g. '$').
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import contextlib
import logging

import adconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.ad2.ADUtils import ADclient
from Cerebrum.modules.ad2 import cli
from Cerebrum.utils import argutils


logger = logging.getLogger(__name__)


def run_cmdlet(client, argv):
    code = " ".join(argv)
    logger.info("Running code: %s", code)
    return client.run(code)


def print_output(out_dict):
    for outtype in ('stderr', 'stdout'):
        data = out_dict.get(outtype)
        if data:
            print('%s:' % outtype.upper())
            print(data)
            print()


def main(argv=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__.lstrip(),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Skip setup code (clean shell)",
    )
    parser.add_argument(
        "command",
        type=argutils.UnicodeType(),
        nargs="+",
        help="Powershell cmdlet and args",
    )
    get_client = cli.add_ad_subparser(parser)
    Cerebrum.logutils.options.install_subparser(
        parser,
        defaults={
            # Interactive script - disable sentry by default
            Cerebrum.logutils.options.OPTION_SENTRY: False,
        },
    )

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("console", args)

    if args.clean:
        # Drain the client for pre-code:
        # A bit ugly, as we globally change the ADclient class...
        ADclient._pre_execution_code = ""

    client = get_client(adconf.SYNCS, args, dryrun=False)
    with contextlib.closing(client):
        print_output(run_cmdlet(client, args.command))

    logger.debug("Done")


if __name__ == '__main__':
    main()
