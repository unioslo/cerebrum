# coding: utf-8
#
# Copyright 2016 University of Oslo, Norway
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
# Copyright 2002-2015 University of Oslo, Norway
""" This module contains helpers and utilities for argparse. """
import argparse


def build_callback_action(callback, args=[], kwargs={}, exit=True):
    """ Builds an action that will run a callback.

    Example:

        def do_something():
            print("something")

        parser.add_argument(--do-something,
                            action=call_and_exit_action(do_something),
                            help="Do something and exit")

    :param callable callback:
        The callback to run.
    :param list args:
        Positional arguments for the callback.
    :param dict kwargs:
        Keyword arguments for the callback.
    :param bool exit:
        True if the script should exit after performing this action. This is
        the default.

    :return argparse.Action:
        An action that will run the callback.
    """
    class _CallAndExitAction(argparse.Action):
        """ An action that calls 'callback' and exits.  """

        def __init__(self, option_strings, dest, help=None):
            super(_CallAndExitAction, self).__init__(
                option_strings=option_strings,
                dest=argparse.SUPPRESS,
                default=argparse.SUPPRESS,
                nargs=0,
                help=help)

        def __call__(self, parser, ns, opt_value, option_string=None):
            callback(*args, **kwargs)
            if exit:
                parser.exit()
    return _CallAndExitAction
