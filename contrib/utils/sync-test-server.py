#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2019 University of Oslo, Norway
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
Script for syncing cerebrum state to test servers.

This script is used for syncing files from production servers to a test server.
Currently only import/export files can be synced.


Configuration
-------------
The following configuration affects how this script behaves.

cereconf.TESTSYNC_DATAFILES
    Files to sync.  Should be a dictionary that maps subdirectories to files
    for that subdirectory.  E.g.:

        ``{'SAP': ['foo.xml', 'bar.xml'], 'FS': ['baz.xml']}``

    would sync the files:

    - /cerebrum/var/cache/SAP/foo.xml
    - /cerebrum/var/cache/SAP/bar.xml
    - /cerebrum/var/cache/FS/baz.xml


TODO
----
Implement code sync, config sync, database sync


History
-------
This script was previously a part of the old cerebrum_config repository. It was
moved into the main Cerebrum repository, as it was currently in use by many
deployments of Cerebrum.

The original can be found in cerebrum_config.git, as
'bin/sync_testserver.py at:

  Commit: 73dafcf6bc3a444189136947c4b3e097653c4509
  Merge:  247aa931 2eb69c17
  Date:   Mon Sep 9 08:41:30 2019 +0200

"""
from __future__ import unicode_literals

import argparse
import logging
import os
import subprocess
import sys

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options


logger = logging.getLogger(__name__)

SSH_CMD = '/usr/bin/ssh'
RSYNC_CMD = '/usr/bin/rsync'
RSYNC_PARAMS = [
    # Can't use -a option, because of symlinks and perms
    '-rLtgoz',
    '--chmod=Dg+rx,ug+rs,Fo-rwx',
]


CACHE_DIR = os.path.join(sys.prefix, 'var/cache')


def get_basedir(instance):
    if instance:
        return os.path.join('/cerebrum', instance)
    else:
        return '/cerebrum'


def run_cmd(cmd):
    """
    Run given command by subprocess.call

    :type cmd: list
    :param cmd: Command and parameters given as a list

    :return: None
    """
    # subprocess.call is a convenience function that doesn't return
    # until completion (P_WAIT). Returns exit code of the process, or
    # -signal if the process was killed.
    logger.debug('run_cmd(%r)', cmd)
    try:
        retcode = subprocess.call(cmd)
        if retcode < 0:
            logger.error("Child process was terminated by signal %d",
                         -retcode)
    except OSError:
        logger.error('Command failed', exc_info=True)


def sync_files(from_path, to_path, commit=False):
    """
    Sync files from from_path to to_path. Log error if running the
    command isn't succesful.

    :type from_path: str
    :param from_path: path which files should be fetched from

    :type from_path: str
    :param from_path: path which files should be synced to

    :return: None
    """
    logger.info("Syncing %r to %r", from_path, to_path)

    cmd = [RSYNC_CMD] + RSYNC_PARAMS + [from_path, to_path]

    if commit:
        run_cmd(cmd)
    else:
        logger.debug("DRYRUN: would run_cmd(%r)", cmd)


def sync_data_files(host, rootdir, commit=False):
    """
    Sync data files for the given host to the test server.

    :param str host:
        The hostname to copy files to

    :param str rootdir:
        The destination root directory.

    :param bool commit:
        Run in commit mode. Default: False.
    """
    for datadir in sorted(cereconf.TESTSYNC_DATAFILES):
        files = cereconf.TESTSYNC_DATAFILES[datadir]
        for datafile in files:
            from_file = os.path.join(CACHE_DIR, datadir, datafile)
            to_path = '{}:{}'.format(
                host,
                os.path.join(rootdir, 'var/cache', datadir))
            sync_files(from_file, to_path, commit)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Sync files and data to a test server',
    )
    parser.add_argument(
        '--sync-data',
        dest='sync_data',
        action='store_true',
        default=False,
        help='Sync files (cereconf.TESTSYNC_DATAFILES)',
    )
    parser.add_argument(
        '--dest-host',
        dest='dest_host',
        required=True,
        help='Sync files to %(metavar)s',
        metavar='<host>',
    )
    parser.add_argument(
        '--instance',
        dest='instance',
        help=('Set root directory to an instance subdirectory'
              ' (/cerebrum/%(metavar)s)'),
        metavar='<name>',
    )
    parser.add_argument(
        '--commit',
        action='store_true',
        default=False,
        help='Run in commit mode',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    if not args.commit:
        logger.warning("No --commit given, won't actually do anything")

    rootdir = get_basedir(args.instance)

    if args.sync_data:
        logger.info('Syncing files to host=%r, rootdir=%r',
                    args.dest_host, rootdir)
        sync_data_files(args.dest_host, rootdir, args.commit)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
