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

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.tasks.task_queue import sql_get_subqueue_counts
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
        default=None,
        help='Limit number of tasks to %(metavar)s (required in dryrun)',
        metavar='<n>',
    )

    db_args = parser.add_argument_group('Database')
    db_args.add_argument(
        '--dryrun-import',
        dest='dryrun_import',
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
    max_attempts = handle_task.max_attempts
    dryrun = not args.commit
    dryrun_import = args.dryrun_import or dryrun

    # Actually process tasks
    logger.info('Collecting tasks (nbf=%s, limit=%r, max-attempts=%r)',
                nbf_cutoff, args.limit, max_attempts)

    database = get_db()

    tasks = list(
        TaskQueue(database).search(
            queues=handle_task.queue,
            nbf_before=nbf_cutoff,
            max_attempts=max_attempts,
            limit=args.limit))

    logger.info('Considering %d tasks', len(tasks))

    for task in tasks:
        # Remove the current task
        with db_context(database, dryrun=dryrun) as db:
            try:
                TaskQueue(db).pop(task.queue, task.sub, task.key)
            except Cerebrum.Errors.NotFoundError:
                logger.debug('task %s/%s/%s gone, already processed?',
                             task.queue, task.sub, task.key)
                # we collect and process tasks in different transactions,
                # so there is a slight chance that some tasks no longer exists
                continue

        logger.info('processing task %s/%s/%s (dryrun=%r)',
                    task.queue, task.sub, task.key, dryrun_import)

        # Process the current taask
        try:
            with db_context(database, dryrun=dryrun_import) as db:
                handle_task(db, dryrun=dryrun_import, task=task)
            task_failed = None
        except Exception as e:
            logger.warning('failed task %s/%s/%s',
                           task.queue, task.sub, task.key, exc_info=True)
            task_failed = e

        # Re-insert the current task on error
        #
        # There is a chance that _this_ part fails, and we're unable to
        # re-insert a failed task.  Ideally, the entire task processing should
        # happen in a single transaction, while `handle_task` should use
        # savepoints to roll back if the import fails.  However, this would
        # require a rewrite of all our ChangeLog implementations...
        if task_failed:
            with db_context(database, dryrun=dryrun) as db:
                retry_task = handle_task.get_retry_task(task, e)
                logger.debug('re-queueing %r as %r', task, retry_task)
                if TaskQueue(db).push(retry_task, ignore_nbf_after=True):
                    logger.info('queued retry-task %s/%s/%s at %s',
                                retry_task.queue, retry_task.sub,
                                retry_task.key, retry_task.nbf)

    # Check for tasks that we've given up on (i.e. over the
    # max_attempts threshold)
    logger.info('checking for abandoned tasks...')
    for row in sql_get_subqueue_counts(
            database,
            queues=handle_task.queue,
            min_attempts=handle_task.max_attempts):
        if row['num']:
            logger.warning('queue: %s/%s, given up on %d failed items',
                           row['queue'], row['sub'], row['num'])

    logger.info('done %s', parser.prog)


if __name__ == '__main__':
    main()
