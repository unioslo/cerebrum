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
r"""
Clean up old, failed atomicfile writes.

This script pretty much does:
::

    find <path> -maxdepth <max_depth> -mtime +<min_age> \
        -name '<glob_pattern>' -delete

... with logging and a dryrun option, for each pattern given on the command
line.

The typical use case is to iterate through files under ``<prefix>/var/cache``,
and remove old files that matches the naming pattern used by
:mod:`Cerebrum.utils.atomicfile` for temporary files.  These files are normally
removed as the file writer completes its work, but are kept around for
debugging if file writing fails for any reason.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import fnmatch
import logging
import os
import re
import textwrap

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils import argutils
from Cerebrum.utils import date_compat
from Cerebrum.utils import date as date_utils

logger = logging.getLogger(__name__)


def find_files(path, max_depth, patterns, before):
    """
    Find files in *path* with matching criterias.

    :param path:
        Root of the directory tree to find files in.

    :param int max_depth:
        Max recursion depth.

        A depth of N>0 finds files in up to N sub-directory levels of *path*
        A depth of N=0 will prevent recursion, and only find files in *path*.
        A depth of N<0 disables the limit, and will recurse into all
        subdirectories.

        Note that symlinks are ignored (to prevent directory cycles).

    :type patterns: list, tuple, set
    :param patterns:
        Only include filenames matching a glob-like pattern in this collection.

        Will match all filenames if no patterns are given.

    :type before: datetime.date, datetime.datetime, NoneType
    :param datetime.date before:
        Upper mtime threshold for matching files.

        Files newer than this will be ignored.  Set to ``None`` to disable
        mtime filtering.

    """
    logger.info("Finding files in %s, depth=%d, name in %s, modified<%s",
                repr(path), max_depth, repr(patterns), before.isoformat())

    file_regex = re.compile(
        "|".join(fnmatch.translate(pattern) for pattern in (patterns or []))
        or fnmatch.translate("*")
    )
    cutoff = (
        date_utils.to_timestamp(date_compat.get_datetime_tz(before))
        if before else 0
    )
    logger.debug("pattern=%s, cutoff=%s", file_regex.pattern, cutoff)

    depth_map = {path: 0}

    for currdir, subdirs, files in os.walk(path):
        depth = depth_map[currdir]
        for subdir in subdirs:
            depth_map[os.path.join(currdir, subdir)] = depth + 1
        if max_depth >= 0 and depth > max_depth:
            # Maybe replace os.walk with a recursive os.listdir to actually cut
            # off at max_depth?
            logger.debug("ignoring path %s (maxdepth reached)", currdir)
            continue
        for filename in files:
            fullname = os.path.join(currdir, filename)
            if not file_regex.match(filename):
                logger.debug("ignoring file %s (no pattern match)", fullname)
                continue
            if os.path.getmtime(fullname) > cutoff:
                logger.debug("ignoring file %s (too new)", fullname)
                continue
            logger.debug("matched file %s", fullname)
            yield fullname


def delete_files(iterable):
    for filename in iterable:
        os.unlink(filename)
        logger.info("deleted %s", filename)


def print_files(iterable):
    for filename in iterable:
        print(filename)


DEFAULT_GLOB = "*.?????"
DEFAULT_AGE_DAYS = 7


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Delete old, failed export files from a given path."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        help="Directory subtree to clean",
    )

    cond_group = parser.add_argument_group(
        "conditions",
        textwrap.dedent(
            """
            Only delete files that matches certain criteria.

            By default, this script deletes filenames from all subdirectories,
            with a filename matching {default_glob}, that hasn't been modified
            in {default_age_days} days.

            Note that the default glob pattern *may* match files that *aren't*
            temporary files - beware of the file naming schemes in use in the
            directory before using this script.

            To prevent recursion: `--max-depth=0`  (only delete files directly
            in <path>, and not subfolders of <path>).

            To match all file ages: `--min-age=0`.  Note: Only do this in file
            trees that *doesn't* use the AtomicFileWriter, or when no
            AtomicFileWriter writes are happening.
            """
        ).lstrip().format(
            default_glob=DEFAULT_GLOB,
            default_age_days=DEFAULT_AGE_DAYS,
        ),
    )
    cond_group.add_argument(
        "--min-age",
        dest="min_age",
        type=int,
        default=DEFAULT_AGE_DAYS,
        help=(
            "Delete files older than %(metavar)s days"
            " (default: %(default)s)"
        ),
        metavar="<n>",
    )
    cond_group.add_argument(
        "--max-depth",
        dest="max_depth",
        type=int,
        default=-1,
        help=(
            "Limit subtree depth to %(metavar)s directories"
            " (default: no limit)"
        ),
        metavar="<n>",
    )
    cond_group.add_argument(
        "--glob-pattern",
        dest="glob_patterns",
        action="append",
        help=(
            "Limit to files with name pattern %(metavar)s"
            " (default: %(default)s)"
        ),
        metavar="<glob>",
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
        commit_desc="Actually delete files",
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    default_log_preset = "tee" if args.commit else "console"
    Cerebrum.logutils.autoconf(default_log_preset, args)
    logger.info("Start %s", parser.prog)
    logger.debug("args=%s", repr(args))

    glob_patterns = (args.glob_patterns if args.glob_patterns
                     else [DEFAULT_GLOB])

    if args.commit:
        process_files = delete_files
    else:
        process_files = print_files

    process_files(
        find_files(
            args.path,
            max_depth=args.max_depth,
            patterns=glob_patterns,
            before=(
                date_utils.now()
                - datetime.timedelta(days=args.min_age)
            ),
        ),
    )

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
