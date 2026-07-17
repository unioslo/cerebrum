# -*- coding: utf-8 -*-
#
# Copyright 2019-2024 University of Oslo, Norway
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
This module contains job_runner related commands in bofhd.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import socket
import textwrap

from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.errors import PermissionDenied, CerebrumError
from Cerebrum.modules.job_runner import socket_ipc


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
        'job_runner_status': 'Show job runner status',
        'job_runner_info': 'Show info for a job runner job',
        'job_runner_run': 'Start a job runner job',
    },
}

CMD_ARGS = {
    'jr-job': [
        "jr-job",
        "Enter job name",
        textwrap.dedent(
            """
            The name of a job-runner job

            Use `job_runner status` to list all jobs.
            """
        ).lstrip(),
    ],
    'jr-with-deps': [
        "jr-with-deps",
        "Honor dependencies (yes/no)",
        textwrap.dedent(
            """
            Honor dependencies and constraints for this job.

            If `yes`, job runner will try to queue pre-jobs and post-jobs for
            this job.  Note that other constraints, such as max-freq, will also
            be honored - the result may be that this job won't be queued.
            """
        ).lstrip(),
    ],
}


class BofhdJobRunnerCommands(BofhdCommandBase):
    """Bofh commands for job_runner."""

    all_commands = {}
    authz = BofhdJobRunnerAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return (CMD_GROUP, CMD_HELP, CMD_ARGS)

    def _run_job_runner_command(self, command, args=None):
        """Run a job_runner command via the job_runner socket."""
        with socket_ipc.jr_connection(timeout=0.2) as conn:
            try:
                resp_text = socket_ipc.SocketProtocol.call(conn, command, args)
                return {'response': resp_text}
            except socket.timeout:
                raise CerebrumError(
                    "Connection timeout when talking to job-runner.")

    _job_runner_fs = cmd_param.FormatSuggestion(
        "%s", ('response',),
        hdr="Output:",
    )

    #
    # job_runner status
    #
    all_commands['job_runner_status'] = cmd_param.Command(
        ("job_runner", "status"),
        fs=_job_runner_fs,
        perm_filter='can_show_job_runner_status',
    )

    def job_runner_status(self, operator):
        """Show job runner status."""
        # Access control
        self.ba.can_show_job_runner_status(operator.get_entity_id())
        return self._run_job_runner_command('STATUS')

    #
    # job_runner info <jr-job>
    #
    all_commands['job_runner_info'] = cmd_param.Command(
        ("job_runner", "info"),
        cmd_param.SimpleString(help_ref='jr-job', repeat=False),
        fs=_job_runner_fs,
        perm_filter='can_show_job_runner_job',
    )

    def job_runner_info(self, operator, job_name):
        """Show job runner status."""
        # Access control
        self.ba.can_show_job_runner_job(operator.get_entity_id())
        return self._run_job_runner_command('SHOWJOB', [job_name, ])

    #
    # job_runner run <jr-job> [jr-with-deps]
    #
    all_commands['job_runner_run'] = cmd_param.Command(
        ("job_runner", "run"),
        cmd_param.SimpleString(help_ref='jr-job', repeat=False),
        cmd_param.YesNo(help_ref='jr-with-deps', optional=True, default="No"),
        fs=_job_runner_fs,
        perm_filter='can_run_job_runner_job',
    )

    def job_runner_run(self, operator, job_name, with_deps=False):
        """Run a job runner job."""
        # Access control
        self.ba.can_run_job_runner_job(operator.get_entity_id())
        with_deps = self._get_boolean(with_deps)
        return self._run_job_runner_command('RUNJOB', [job_name, with_deps])
