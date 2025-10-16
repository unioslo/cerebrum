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
Get WinRM data and start a Shell

This script is mostly useful for testing the WinRM configuration, or to clean
up unclosed shells started by WinRM.
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
import textwrap

from lxml import etree

import adconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.ad2 import cli

logger = logging.getLogger(__name__)


def create_shell(client):
    logger.info("Creating Shell...")
    shell_id = client.wsman_create()
    logger.info("Created shell id=%s", repr(shell_id))
    return shell_id


def delete_shell(client, shell_id):
    logger.info("Deleting shell with id=%s", repr(shell_id))
    client.wsman_delete(shell_id)
    logger.info("Delete shell with id=%s", repr(shell_id))


@contextlib.contextmanager
def debug_context(context):
    logger.debug("getting %s ...", context)
    try:
        yield
    except Exception:
        logger.debug("unable to get %s", context, exc_info=True)


def print_result(item, xml_result):
    print(item)
    print("-" * len(item))
    if xml_result:
        print(etree.tostring(xml_result, pretty_print=True))
    else:
        print("Unable to get " + item)
    print()


def get_info(client):
    # wsman info
    result = None
    with debug_context("server identity"):
        result = client.wsman_identify()
    print_result("server identity", result)

    # services
    resource = 'config/listener'
    result = None
    with debug_context("listeners"):
        request_id = client.wsman_enumerate(resource)
        logger.debug("got request_id-id: %s", request_id)
        result = client.wsman_pull(resource, request_id)
    print_result("listeners", result)

    # list shells
    resource = 'windows/shell'
    result = None
    with debug_context("shell list"):
        request_id = client.wsman_enumerate(resource)
        logger.debug("got request_id-id: %s", request_id)
        result = client.wsman_pull(resource, request_id)
    print_result("shell list", result)

    # Don't think the following has ever worked?
    #
    # I think the idea is to get the actual commands running in each shell.
    # The documentation says the get command must be sent to a specific shell?
    # Probably needs a Shell-Id selector (which we *could* get from the shell
    # listing?).
    resource = 'windows/shell/cmd'
    result = None
    with debug_context("running commands"):
        request_id = client.wsman_get(resource)
        logger.debug("got request-id: %s", request_id)
        result = client.wsman_pull(resource, request_id)
    print_result("running commands", result)


def main(argv=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """
            Get info from a WinRM server and start a shell.

            This script is mainly used to test the WinRM parts of an adconf
            preset.
            """
        ).strip(),
    )
    parser.add_argument(
        "--get-info",
        action="store_true",
        help="Enumerate info from the ad server",
    )

    # alternative actions
    parser.add_argument(
        "--delete-shell",
        help="Send a signal to delete the given ShellId and exit",
        metavar="<shell-id>"
    )
    get_client = cli.add_winrm_subparser(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("console", args)
    logger.info("Start %s", parser.prog)

    client = get_client(adconf.SYNCS, args)
    client._winrs_skip_cmd_shell = False

    if args.get_info:
        get_info(client)

    if args.delete_shell:
        delete_shell(client, args.delete_shell)
    else:
        create_shell(client)

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
