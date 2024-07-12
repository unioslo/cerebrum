# -*- coding: utf-8 -*-
#
# Copyright 2017-2023 University of Oslo, Norway
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
Options/cli arguments for logutils.

This module contains utilities to parse command line arguments, and use them to
change logging behaviour in Cerebrum. These options typically sets log levels
(--logger-level) or selects a non-default logging preset (--logger-name).

There are two ways to fetch logger settings from the command line:

- Use an ArgumentParser, and add logger arguments with `install_subparser`.
- Extract arguments directly from `sys.argv`

Both should result in an object that contains attributes with the command line
settings.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import sys
import threading

# Namespace-attributes
OPTION_CAPTURE_EXC = 'logger_capture_exc'
OPTION_CAPTURE_WARN = 'logger_capture_warn'
OPTION_LOGGER_LEVEL = 'logger_level'
OPTION_LOGGER_NAME = 'logger_name'
OPTION_SENTRY = 'sentry_enable'


def install_subparser(parser):
    """ Add a logging subparser to an existing ArgumentParser. """
    subparser = parser.add_argument_group('Logging',
                                          'Override default log configuration')

    # TODO: Should we have both an enable and a disable here?

    # Enable or disable logger exception hook
    exc_mutex = subparser.add_mutually_exclusive_group()
    exc_mutex.add_argument(
        '--logger-exc',
        dest=OPTION_CAPTURE_EXC,
        default=None,
        action='store_true',
        help="Enable exception capture",
    )
    exc_mutex.add_argument(
        '--logger-no-exc',
        dest=OPTION_CAPTURE_EXC,
        default=None,
        action='store_false',
        help="Disable exception capture",
    )

    # Enable or disable logger warnings "hook"
    warn_mutex = subparser.add_mutually_exclusive_group()
    warn_mutex.add_argument(
        '--logger-warn',
        dest=OPTION_CAPTURE_WARN,
        default=None,
        action='store_true',
        help="Enable warnings capture",
    )
    warn_mutex.add_argument(
        '--logger-no-warn',
        dest=OPTION_CAPTURE_WARN,
        default=None,
        action='store_false',
        help="Disable warnings capture",
    )

    # Select a logger preset
    # TODO: This should be renamed to `--logger-preset`,
    #       as the term *logger name* refers to something else
    subparser.add_argument(
        '--logger-name',
        metavar='NAME',
        dest=OPTION_LOGGER_NAME,
        help="Override logger configuration",
    )

    # Select a logger level
    subparser.add_argument(
        '--logger-level',
        metavar='LEVEL',
        dest=OPTION_LOGGER_LEVEL,
        help="Override logger level",
    )

    sentry_mutex = subparser.add_mutually_exclusive_group()
    sentry_mutex.add_argument(
        '--logger-sentry',
        dest=OPTION_SENTRY,
        default=None,
        action='store_true',
        help="Enable sentry",
    )
    sentry_mutex.add_argument(
        '--logger-no-sentry',
        dest=OPTION_SENTRY,
        default=None,
        action='store_false',
        help="Disable sentry",
    )

    return subparser


# Threading lock to prevent simultaneous changes to `sys.argv` by
# `process_arguments`
process_arguments_lock = threading.Lock()


def process_arguments(**kwargs):
    """
    Legacy argument parsing.

    This function is used to extract logger options directly from sys.argv.

    .. note::
       This function has side effects: It directly modifies `sys.argv` by
       removing valid logutils options.

    :returns argparse.Namespace:
        A namespace with all the logutils options.
    """
    parser = argparse.ArgumentParser(add_help=False)
    install_subparser(parser)

    # Note: This lock does not really help all that much if something outside
    # this module is accessing sys.argv

    # Note that this may also cause problems if your script also has other
    # options that starts with '--logger-<something>'. Look up 'argparse prefix
    # matching' for more details.
    with process_arguments_lock:
        namespace, rest = parser.parse_known_args(sys.argv)
        sys.argv[:] = rest[:]
        return namespace


# python -m Cerebrum.logutils.options


def main(inargs=None):
    parser = argparse.ArgumentParser()
    install_subparser(parser)
    args = parser.parse_args(inargs)
    print(repr(args))


if __name__ == '__main__':
    main()
