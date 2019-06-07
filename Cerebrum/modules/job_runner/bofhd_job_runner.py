# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
"""This module contains job_runner related commands in bofhd."""
from __future__ import unicode_literals

import logging
import socket

from contextlib import closing

import cereconf

from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import (Command,
                                              FormatSuggestion,
                                              SimpleString,
                                              YesNo)
from Cerebrum.modules.bofhd.errors import PermissionDenied, CerebrumError
from Cerebrum.modules.job_runner.socket_ipc import (SocketConnection,
                                                    SocketProtocol)


logger = logging.getLogger(__name__)


class BofhdJobRunnerAuth(BofhdAuth):
    """Auth for job_runner commands."""

    def can_show_job_runner_status(self, operator, query_run_any=False):
        """Check if an operator is allowed to see job_runner status.

        :param int operator: entity_id of the authenticated user
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to see job runner status")

    def can_show_job_runner_job(self, operator, query_run_any=False):
        """Check if an operator is allowed to see info on a job_runner job.

        :param int operator: entity_id of the authenticated user
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to see job runner info")

    def can_run_job_runner_job(self, operator, query_run_any=False):
        """Check if an operator is allowed to start a job_runner run.

        :param int operator: entity_id of the authenticated user
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to run job runner jobs")


CMD_GROUP = {
    'job_runner': 'Interact with the cerebrum scheduler',
}

CMD_HELP = {
    'job_runner': {
        'job_runner_status':
            'Show job runner status',
        'job_runner_info':
            'Show info for a job runner job',
        'job_runner_run':
            'Start a job runner job',
    },
}

CMD_ARGS = {
    'job_runner_name': ['name', 'Enter job name',
                        'The name of the job_runner job'],
    'yes_no_with_deps': ['with_deps', 'Honor dependencies'],
}


class BofhdJobRunnerCommands(BofhdCommandBase):
    """Bofh commands for job_runner."""

    all_commands = {}
    authz = BofhdJobRunnerAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return CMD_GROUP, CMD_HELP, CMD_ARGS

    def _run_job_runner_command(self, command, args=None):
        """Run a job_runner command via the job_runner socket."""
        with closing(socket.socket(socket.AF_UNIX)) as sock:
            sock.connect(cereconf.JOB_RUNNER_SOCKET)
            sock.settimeout(0.2)
            try:
                return SocketProtocol.call(SocketConnection(sock),
                                           command,
                                           args)
            except socket.timeout:
                raise CerebrumError('Error talking to job_runner. Socket '
                                    'timeout')

    #
    # job_runner status
    #
    all_commands['job_runner_status'] = Command(
        ("job_runner", "status"),
        fs=FormatSuggestion(
            "%s", 'simpleString',
            hdr="%s" % 'Output:'
        ),
        perm_filter='can_show_job_runner_status')

    def job_runner_status(self, operator):
        """Show job runner status."""
        # Access control
        self.ba.can_show_job_runner_status(operator.get_entity_id())
        return self._run_job_runner_command('STATUS')

    # job_runner info
    #
    all_commands['job_runner_info'] = Command(
        ("job_runner", "info"),
        SimpleString(help_ref='job_runner_name', repeat=False),
        fs=FormatSuggestion(
            "%s", 'simpleString',
            hdr="%s" % 'Output:'
        ),
        perm_filter='can_show_job_runner_job')

    def job_runner_info(self, operator, job_name):
        """Show job runner status."""
        # Access control
        self.ba.can_show_job_runner_job(operator.get_entity_id())
        return self._run_job_runner_command('SHOWJOB', [job_name, ])

    #
    # job_runner run
    #
    all_commands['job_runner_run'] = Command(
        ("job_runner", "run"),
        SimpleString(help_ref='job_runner_name', repeat=False),
        YesNo(help_ref='yes_no_with_deps', optional=True, default="No"),
        fs=FormatSuggestion(
            "%s", 'simpleString',
            hdr="%s" % 'Output:'
        ),
        perm_filter='can_run_job_runner_job')

    def job_runner_run(self, operator, job_name, with_deps=False):
        """Run a job runner job."""
        # Access control
        self.ba.can_run_job_runner_job(operator.get_entity_id())
        with_deps = self._get_boolean(with_deps)
        return self._run_job_runner_command('RUNJOB', [job_name, with_deps])
