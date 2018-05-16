#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 University of Oslo, Norway
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
u""" Printer module.

This module should be used in all print operations from Cerebrum.

Configuration
-------------
Print command substitution
    The following values will be substituted in print commands:

    - username ($username)
    - hostname ($hostname)
    - destination ($destination, $dest, $printer)
    - filenames ($filename, $filenames)

    Note that the substitution strings should be quoted, except for the
    filenames. Filenames are automatically quoted.


The following `cereconf' values alters how printing is performed:

PRINT_LPR_MAP
    A dict that contains destination->command mappings. Whenever the
    LinePrinter object from this module is used to print, and a print job is
    issued to a destination given in `PRINT_LPR_MAP', the assiciated command
    will be used for printing.

    Example:

      PRINT_LPR_MAP = {
        'foo': 'lp -- $filenames',
        'bar': 'lpr -U "$username" -- $filenames', }

    If the value '*' is given in `PRINT_LPR_MAP', that value will be used if
    the destination is not given in the map.

PRINT_LPR_CMD
    The default print command. If the print destination does not exist in the
    `PRINT_LPR_MAP', or the `PRINT_LPR_MAP' does not exist, then this command
    will be used for printing.

    Example:

      PRINT_LPR_CMD = 'lp -- $filenames'

"""

import os
import string
import time
import tempfile

import cereconf

from Cerebrum.Utils import Factory


__print_log = None
u""" Shared log for subprocess output. """


def _get_print_log():
    u""" Lazy instantiation of __print_log. """
    global __print_log
    if __print_log is None or not os.path.isfile(__print_log):
        fd, __print_log = tempfile.mkstemp(
            prefix='cerebrum_print_{}'.format(time.time())
        )
    return __print_log


def _tail_print_log(num=1):
    u""" Fetch last `num' of lines from __print_log. """
    lines = []
    with open(_get_print_log(), 'r') as f:
        lines = f.readlines()
    try:
        return lines[-num:]
    except IndexError:
        return lines


class LinePrinter(object):

    u""" Printer object. """

    lp_cmd = 'lp -h "$hostname" -U "$username" -d "$destination" -- $filenames'
    u""" Default print command. """

    def __init__(self, dest, uname=None, host=None, job=None, logfile=None):
        u""" Set up printer object.

        :param str dest:
            The destination printer or queue name.
        :param str uname:
            Who to print as. Defaults to `default_username' if uname is None.
        :param str host:
            Use an alternative print server/port. Defaults to
            `default_hostname' if host is None.
        :param str job:
            A name for this job. Defaults to `default_jobname' if job is None.
        :param str logfile:
            Use an alternative log file for output from print command.

        """
        self.destination = dest
        self.username = uname or self.default_username
        self.hostname = host or self.default_hostname
        self.jobname = job or self.default_jobname
        self.logfile = logfile

    @property
    def default_username(self):
        u""" Get a default username for printing. """
        return 'unknown'

    @property
    def default_hostname(self):
        u""" Get a default hostname for printing. """
        return os.uname()[1]

    @property
    def default_jobname(self):
        return 'job.ps'

    def _build_cmd(self, **params):
        u""" Choose and build the print command.

        :param **dict params:
            Key-value arguments to substitute the print command with.

        """
        if self.destination in getattr(cereconf, 'PRINT_LPR_MAP', {}):
            cmd = string.Template(cereconf.PRINT_LPR_MAP[self.destination])
        elif '*' in getattr(cereconf, 'PRINT_LPR_MAP', {}):
            cmd = string.Template(cereconf.PRINT_LPR_MAP['*'])
        elif hasattr(cereconf, 'PRINT_LPR_CMD'):
            cmd = string.Template(cereconf.PRINT_LPR_CMD)
        else:
            cmd = string.Template(self.lp_cmd)
        return cmd.substitute(params)

    def spool(self, *filenames):
        u""" Spool file for printing. """
        logger = Factory.get_logger('cronjob')
        if not filenames:
            logger.debug("No files given, nothing to spool")
            return

        filenames = ' '.join(['"%s"' % f for f in filenames])
        lpr_params = {
            # File to print
            'filename': filenames,
            'filenames': filenames,

            # Who to print as
            'uname': self.username,
            'username': self.username,

            # Where to print from
            'hostname': self.hostname,

            # Job name
            'jobname': self.jobname,

            # Destination queue
            'destination': self.destination,
            'printer': self.destination, }

        logfile = self.logfile or _get_print_log()
        cmd = self._build_cmd(**lpr_params)
        logger.debug("Spooling files %r with command %r", filenames, cmd)
        rc = os.system("%s >> %s 2>&1" % (cmd, logfile))
        logger.debug("Spooled files %r (rc=%d, logfile=%s)",
                     filenames, rc, logfile)

        if rc != 0:
            raise IOError("Error spooling job, see %r for details (tail: %s)" %
                          (logfile, "".join(_tail_print_log(num=1)).rstrip()))
