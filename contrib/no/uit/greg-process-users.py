#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
""" Process tasks on the greg update user queues.  """
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.modules.no.uit import greg_users
from Cerebrum.modules.tasks.queue_processor import QueueProcessor
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)
QueueHandler = greg_users.UitGregUserUpdateHandler


# TODO: The various task processing scripts are starting to look very similar.
# We should reduce code duplication and try to make something generic for:
#
#   contrib/greg/greg-process-tasks.py
#   contrib/hr-import/process-tasks.py
#   <this script>
#


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Process the {} task queues'.format(QueueHandler.queue)
    )
    parser.add_argument(
        '-l', '--limit',
        type=int,
        default=None,
        help='Limit number of tasks to %(metavar)s (required in dryrun)',
        metavar='<n>',
    )

    db_args = parser.add_argument_group('Database')
    add_commit_args(db_args)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %r", args)

    dryrun = not args.commit
    queue_handler = QueueHandler()

    # The QueueProcessor gets db and does commit/rollback according to dryrun
    proc = QueueProcessor(queue_handler, limit=args.limit, dryrun=dryrun)

    tasks = proc.select_tasks()
    for task in tasks:
        proc.process_task(task)

    # Check for tasks that we've given up on (i.e. over the
    # QueueHandler.max_attempts threshold)
    logger.info('checking for abandoned tasks...')
    for (queue, sub), count in proc.get_abandoned_counts():
        logger.warning('queue: %s/%s, given up on %d failed items',
                       queue, sub, count)

    logger.info('done %s', parser.prog)


if __name__ == '__main__':
    main()
