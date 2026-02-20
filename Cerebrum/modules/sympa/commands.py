# -*- coding: utf-8 -*-
#
# Copyright 2026 University of Oslo, Norway
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
Wrapper module for running sympa commands

Sympa commands is simply a script we run to create and delete email lists in
Sympa.

More info: TODO

Configuration
=============
The following settings from :mod:`cereconf` applies to this modoule:

``SYMPA_SCRIPT``
    Location of the sympa script to run.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import six

import cereconf
from Cerebrum.utils import reprutils
from Cerebrum.utils import subproc

logger = logging.getLogger(__name__)


def _str_arg(value, allow_empty=False):
    """ normalize string command argument. """
    if not isinstance(value, six.string_types):
        raise ValueError("invalid argument: " + repr(value))
    value = value.strip()
    if not allow_empty and not value:
        raise ValueError("invalid argument: " + repr(value))
    return value


class SympaCommands(reprutils.ReprEvalMixin):
    """
    Handler for running sympa script commands.

    This class can create and delete email lists in Sympa.

    It has a dryrun mode that prevents running any actual commands.
    """
    repr_module = False
    repr_kwargs = ("dryrun",)

    def __init__(self, dryrun=True):
        """
        :param bool dryrun: if true, no sympa commands will actually run
        """
        self.dryrun = dryrun

    @property
    def sympa_script(self):
        """ the sympa management command/script. """
        return cereconf.SYMPA_SCRIPT

    def _run_command(self, cmd):
        if self.dryrun:
            logger.info("dryrun: %s", subproc.format_command(cmd))
            return True
        result_t = subproc.run(cmd, retval=(subproc.RETURN_RC,))
        return not result_t[0]

    def _newlist_args(self, runhost, listname, admins, profile, description):
        return [
            self.sympa_script, _str_arg(runhost),
            "newlist", _str_arg(listname),
            _str_arg(admins), _str_arg(profile), _str_arg(description),
        ]

    def newlist(self, runhost, listname, admins, profile, description):
        """
        Create a new sympa email list.

        :param str runhost: the sympa host where this list should be created
        :param str listname: the email list name
        :param admins:
        :param profile:
        :param str description: email list description
        """
        logger.debug("%s.newlist(%s, %s, %s, %s, %s)",
                     repr(self), repr(runhost), repr(listname),
                     repr(admins), repr(profile), repr(description))
        return self._run_command(
            self._newlist_args(runhost, listname, admins, profile, description)
        )

    def _rmlist_args(self, runhost, listname):
        return [
            self.sympa_script, _str_arg(runhost),
            "rmlist", _str_arg(listname),
        ]

    def rmlist(self, runhost, listname):
        """
        Remove an existing sympa email list.

        :param str runhost: the sympa host where this list exists
        :param str listname: the email list name
        """
        logger.debug("%s.rmlist(%s, %s)",
                     repr(self), repr(runhost), repr(listname))
        return self._run_command(
            self._rmlist_args(runhost, listname)
        )
