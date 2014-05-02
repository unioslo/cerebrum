#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2012 University of Oslo, Norway
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

""" This is a bofhd module for debug commands.

It is used to implement behaviour that is useful for testing, but never
desireable in a production environment.

WARNING: These commands should never be put in an actual config.dat file
outside dev environments. To use, add the following line to your config.dat
file:
    Cerebrum.modules.bofhd.bofhd_debug_cmds/BofhdExtension

"""
import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.auth import BofhdAuth

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import Command, FormatSuggestion, \
    SimpleString, Integer


class ExceptionMultipleArgs(Exception):

    """ A generic exception that takes multiple args. """

    def __init__(self, strval, intval):
        self.strval = strval
        self.intval = intval

    def __str__(self):
        return "ExceptionMultipleArgs(strval='%s', intval=%d)" % (self.strval,
                                                                  self.intval)


class BofhdExtension(BofhdCommandBase):

    """ Debug commands. """

    all_commands = {}

    def __init__(self, server):
        super(BofhdExtension, self).__init__(server)
        self.ba = BofhdAuth(self.db)

    def get_help_strings(self):
        group_help = {'debug': "Debug commands.", }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'debug': {
                'debug_raise_cerebrum_error':
                    'Raise a Cerebrum.Errors.CerebrumError exception',
                'debug_raise_bofhd_cerebrum_error':
                    'Raise a bofhd.errors.CerebrumError exception',
                'debug_raise_exception_multiple_args':
                    'Raise an exception with multiple args',
            }
        }

        arg_help = {
            'exc_strval': ['string', 'Enter a string',
                           'Enter a string value for the exception'],
            'exc_intval': ['integer', 'Enter an integer',
                           'Enter an integer value for the exception'],
        }
        return (group_help, command_help, arg_help)

    #
    # debug raise_cerebrum_error
    #
    all_commands['debug_raise_cerebrum_error'] = Command(
        ("debug", "raise_cerebrum_error"),
        SimpleString(help_ref='exc_strval', optional=True), )

    def debug_raise_cerebrum_error(self, operator, strval="Foo Bar"):
        """ Raise an exception that takes multiple args. """
        raise Errors.CerebrumError(strval)

    #
    # debug raise_bofhd_cerebrum_error
    #
    all_commands['debug_raise_bofhd_cerebrum_error'] = Command(
        ("debug", "raise_bofhd_cerebrum_error"),
        SimpleString(help_ref='exc_strval', optional=True), )

    def debug_raise_bofhd_cerebrum_error(self, operator, strval="Foo Bar"):
        """ Raise an exception that takes multiple args. """
        raise CerebrumError(strval)

    #
    # debug raise_exception_multiple_args
    #
    all_commands['debug_raise_exception_multiple_args'] = Command(
        ("debug", "raise_exception_multiple_args"),
        SimpleString(help_ref='exc_strval', optional=True),
        Integer(help_ref='exc_intval', optional=True), )

    def debug_raise_exception_multiple_args(self, operator, strval="Foo Bar",
                                            intval=10):
        """ Raise an exception that takes multiple args. """
        raise ExceptionMultipleArgs(strval, intval)
