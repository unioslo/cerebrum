#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
Command line socket interface to servers/job_runner/job_runner.py

job_runner is a scheduler that runs specific commands at certain times.

This script is a command line interface that is able to fetch the job_runner
status and queue jobs using the job_runner socket server.
"""
import argparse
import logging
import os

try:
    import cereconf
except ImportError:
    cereconf = object()

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.job_runner.job_config import get_job_config, dump_jobs
from Cerebrum.modules.job_runner.socket_ipc import SocketServer, SocketTimeout

default_dump_config = 'scheduled_jobs'
default_dump_depth = 1
default_socket = getattr(cereconf, 'JOB_RUNNER_SOCKET', None)
default_timeout = 2

logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(
    description="Send commands to a job_runner daemon",
)
parser.add_argument(
    '-s', '--socket',
    dest='socket',
    required=not default_socket,
    default=default_socket,
    help='Connect to job_runner on a given socket',
)
parser.add_argument(
    '-t', '--timeout',
    dest='timeout',
    default=default_timeout,
    type=int,
    help="timeout for running commands")

commands = parser.add_subparsers(
    title='Commands',
    description='Commands to send',
    metavar='<command>',
)


def add_command(cmd, jr_cmd, desc):
    subparser = commands.add_parser(cmd, description=desc, help=desc)
    subparser.set_defaults(command=jr_cmd)
    return subparser


# <prog> reload
#
cmd_reload = add_command(
    'reload', 'RELOAD',
    'Reload the current job-runner configuration',
)

# <prog> quit
#
cmd_quit = add_command(
    'quit', 'QUIT',
    'Exit gracefully (allow current jobs to complete)',
)

# <prog> kill
#
cmd_kill = add_command(
    'kill', 'KILL',
    'Exit, but kill jobs not finished after 5 seconds',
)

# <prog> status
#
cmd_status = add_command(
    'status', 'STATUS',
    'Show status for a running job-runner',
)

# <prog> pause
#
cmd_pause = add_command(
    'pause', 'PAUSE',
    'Pause queue processing (don\'t start any new jobs)',
)

# <prog> resume
#
cmd_resume = add_command(
    'resume', 'RESUME',
    'Resume queue processing (from paused state)',
)

# <prog> run <name> [--with-deps]
#
cmd_run = add_command(
    'run', 'RUNJOB',
    'Add a job to the front of the run queue',
)
cmd_run.add_argument(
    'name',
    help='Run the job named %(metavar)s',
    metavar='<name>',
)
cmd_run.add_argument(
    '--with-deps',
    dest='run_with_deps',
    action='store_true',
    default=False,
    help='make --run honor dependencies',
)

# <prog> show <name>
#
cmd_show = add_command(
    'show', 'SHOWJOB',
    'Show information about a job',
)
cmd_show.add_argument(
    'name',
    help='Show info about the job named %(metavar)s',
    metavar='<name>',
)

# <prog> dump [--config <config>] [--depth <n>]
#
# TODO/TBD: Should probably be its own script, as it has nothing to do with a
# running job_runner daemon/socket server.
#
cmd_dump = add_command(
    'dump', 'MOCK_DUMP',
    'Show job hierarchy of a configuration file',
)
cmd_dump.add_argument(
    '--config',
    dest='config',
    default=default_dump_config,
    help='use alternative config (filename or module name)',
    metavar='<config>',
)
cmd_dump.add_argument(
    '-d', '--depth',
    type=int,
    dest='dump_depth',
    default=default_dump_depth,
    help='Limit hierarchy depth to %(metavar)s levels',
    metavar='<n>',
)

Cerebrum.logutils.options.install_subparser(parser)
parser.set_defaults(**{
    Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'WARNING',
})


def run_command(socket, command, args, timeout):
    try:
        return SocketServer.send_cmd(command, args=args, timeout=timeout,
                                     jr_socket=socket)
    except SocketTimeout:
        raise RuntimeError("Timout contacting server, is it running?")


def main(inargs=None):
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))
    logger.debug("job runner socket=%s exists=%r",
                 repr(args.socket), os.path.exists(args.socket))

    command = args.command
    c_args = []

    if command == 'RUNJOB':
        c_args = [args.name, args.run_with_deps]
    if command == 'SHOWJOB':
        c_args = [args.name]

    if command == 'MOCK_DUMP':
        scheduled_jobs = get_job_config(args.config)
        print("Showing jobs in {0!r}".format(scheduled_jobs))
        dump_jobs(scheduled_jobs, args.dump_depth)
    else:
        logger.info("Running command=%r, args=%r, timeout=%r",
                    command, c_args, args.timeout)
        print(run_command(args.socket, command, c_args, args.timeout))


if __name__ == '__main__':
    main()
