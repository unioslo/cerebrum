#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
""" Process tasks on the hr-import queues.  """
import argparse
import logging
import functools
import itertools

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.tasks.task_queue import sql_get_queue_counts
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.date import now
from Cerebrum.utils.module import resolve


logger = logging.getLogger(__name__)


def get_task_handler(config):
    import_cls = resolve(config.import_class)
    logger.info('import_cls: %s', config.import_class)

    task_cls = resolve(config.task_class)
    logger.info('task_cls: %s', config.task_class)

    get_importer = functools.partial(import_cls, config=config)
    return task_cls(get_importer)


def get_db():
    db = Factory.get('Database')()
    db.cl_init(change_program='hr-import-tasks')
    return db


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Process the hr-import task queues',
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help='config to use (see Cerebrum.modules.hr_import.config)',
    )
    parser.add_argument(
        '-l', '--limit',
        type=int,
        default=0,
        help='Limit number of tasks to %(metavar)s (required in dryrun)',
        metavar='<n>',
    )

    db_args = parser.add_argument_group('Database')
    db_args.add_argument(
        '--dryrun-import',
        dest='task_dryrun',
        action='store_true',
        help='rollback all hr-import changes (only when --commit)',
    )
    add_commit_args(db_args)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %r", args)

    config = TaskImportConfig.from_file(args.config)

    handle_task = get_task_handler(config)
    nbf_cutoff = now()
    queues = handle_task.all_queues
    max_attempts = handle_task.max_attempts
    limit = args.limit

    # Actually process tasks
    # The transaction management is somewhat complicated, but:
    #
    # When args.commit
    # - Pop one and one task from the queue in its own transaction
    # - handle the task using a savepoint that is committed/rolled back
    #   according to args.task_dryrun
    #
    # When args.dryrun
    # - Search and process all tasks in a single transaction
    logger.info('processing tasks (nbf=%s, limit=%r, max-attempts=%r)',
                nbf_cutoff, limit, max_attempts)

    count = 0
    if args.commit:
        if limit:
            counter = range(1, limit + 1)
        else:
            counter = itertools.count()

        for count in counter:
            with db_context(get_db(), dryrun=False) as db:
                try:
                    task = TaskQueue(db).pop_next(
                        queues=queues,
                        nbf=nbf_cutoff,
                        max_attempts=max_attempts)
                except Cerebrum.Errors.NotFoundError:
                    # No more tasks to process
                    break

                # Note: args.task_dryrun here
                logger.info('processing task %r', task)
                handle_task(db, dryrun=args.task_dryrun, task=task)

    else:
        with db_context(get_db(), dryrun=True) as db:
            for count, task in enumerate(TaskQueue(db).search(
                    queues=queues,
                    nbf_before=nbf_cutoff,
                    max_attempts=max_attempts,
                    limit=limit)):
                # Note: we ignore args.task_dryrun here
                logger.info('processing task %r', task)
                handle_task(db, dryrun=True, task=task)

    logger.info('processed %d tasks', count)

    # Check for tasks that we've given up on (i.e. over the
    # max_attempts threshold)
    logger.info('checking for abandoned tasks...')
    with db_context(get_db(), dryrun=True) as db:
        for row in sql_get_queue_counts(
                db,
                queues=handle_task.all_queues,
                min_attempts=handle_task.max_attempts):
            if row['num']:
                logger.warning('queue: %s, given up on %d failed items',
                               row['queue'], row['num'])

    logger.info('done %s', parser.prog)


if __name__ == '__main__':
    main()
