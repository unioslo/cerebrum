#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2025 University of Oslo, Norway
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
Clean up old job-runner work dirs.

This script goes through the job-runner base directory
(``cereconf.JOB_RUNNER_LOG_DIR``) and removes archived workdirs that are no
longer relevant, due to their age.

The default Job Runner action creates a temporary workdir for each job
(see :class:`Cerebrum.modules.job_runner.job_actions.System`).  If the job
fails or writes to stdout/stderr, the workdir will be kept for debugging.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import logging
import os
import re
import shutil

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils import argutils
from Cerebrum.utils import date as date_utils

logger = logging.getLogger(__name__)


# Archived work directories use the following naming scheme:
#
#     <job-name>.<timestamp>
#
# <job-name>
#     The job attribute name as given in scheduled_jobs.
#
# <timestamp>
#     When the work directory was archived - a unix timestamp with decimals.
#
WORKDIR_REGEX = re.compile(r"(?P<job>[^\.]+)\.(?P<ts>[0-9]+\.[0-9]+)")


def find_workdirs(path, cutoff):
    """
    Find job runner workdirs in *path* with matching criterias.

    :param path:
        path to a directory tree to find workdirs in

    :param float cutoff:
        Upper timestamp threshold for archived directories.
    """
    logger.info("Finding workdirs in %s, timestamp<%s", repr(path), cutoff)

    for relative in os.listdir(path):
        curr = os.path.join(path, relative)

        if not os.path.isdir(curr):
            # A file in the job-runner root directory.  May be a lock-file.
            # Should we exterd this script to clean up old lock files as well?
            # Job-runner will remove/replace these automatically if they are
            # old, but will never clean up lock files for jobs that have been
            # renamed or removed from config.
            continue

        match = WORKDIR_REGEX.match(relative)
        if not match:
            # Not a workdir, but should we consider doing some other clean-ups
            # here ase well?  This would probably be a workdir for:
            #
            #  - Manually triggered job definitions that hasn't been started in
            #    a while
            #  - Job-definitions that has been renamed or removed
            #
            continue

        job_name = match.group("job")
        timestamp = float(match.group("ts"))

        if timestamp > cutoff:
            logger.debug("ignoring new workdir: %s (job: %s, ts: %s)",
                         curr, job_name, timestamp)
            continue

        yield curr


def list_files(path):
    """ List each file in the directory tree at a given *path*. """
    logger.debug("finding files in %s", repr(path))

    result = []
    for curr, _, files in os.walk(path):
        for filename in files:
            result.append(os.path.join(curr, filename))
    return sorted(result)


def remove_directory(path):
    """ Remove directory at a given *path*. """
    for filename in list_files(path):
        logger.info("Deleting: %s", filename)
    shutil.rmtree(path)
    logger.info("Deleted directory tree: %s", path)


def print_directory(path):
    """ Print each file in the directory tree at a given *path*. """
    for filename in list_files(path):
        print(filename)


def normalize_dir(path):
    if not os.path.exists(path):
        raise ValueError("No directory: " + repr(path))
    if not os.path.isdir(path):
        raise ValueError("Not a directory: " + repr(path))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Delete old job-runner workdirs"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    workdir_arg = parser.add_argument(
        "--workdir",
        help=(
            "Process workdirs under %(metavar)s"
            " (defaults to `cereconf.JOB_RUNNER_LOG_DIR`)"
        ),
        metavar="<path>",
    )
    parser.add_argument(
        "--min-age",
        dest="min_age",
        type=int,
        default=7,
        help=(
            "Delete workdirs older than %(metavar)s days"
            " (default: %(default)s)"
        ),
        metavar="<n>",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Only process up to %(metavar)s workdirs"
            " (default: no limit)"
        ),
        metavar="<n>",
    )
    commit_group = parser.add_argument_group(
        "dryrun",
        """
        By default this script only prints the files that would be deleted
        (dryrun).
        """,
    )
    argutils.add_commit_args(
        commit_group,
        commit_desc="Actually delete files and dirs",
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    default_log_preset = "tee" if args.commit else "console"
    Cerebrum.logutils.autoconf(default_log_preset, args)
    logger.info("Start %s", parser.prog)
    logger.debug("args=%s", repr(args))

    with argutils.ParserContext(parser, workdir_arg):
        workdir = normalize_dir(args.workdir or cereconf.JOB_RUNNER_LOG_DIR)

    cutoff = date_utils.to_timestamp(
        date_utils.now()
        - datetime.timedelta(days=args.min_age)
    )

    if args.commit:
        process_path = remove_directory
    else:
        process_path = print_directory

    for n, path in enumerate(find_workdirs(workdir, cutoff), 1):
        process_path(path)
        if not args.limit or n < args.limit:
            continue
        logger.info("Limit reached (%d) - stopping", args.limit)
        break

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
