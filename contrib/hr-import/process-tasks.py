#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Process tasks on the hr import queues.
"""
import argparse
import logging
import functools
import itertools

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.Utils import Factory
from Cerebrum.config.loader import read_config as read_config_file
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.tasks.task_queue import sql_get_queue_counts
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.date import now
from Cerebrum.utils.module import resolve


logger = logging.getLogger(__name__)


def get_config(config_file):
    """ Load config. """
    config = TaskImportConfig()
    config.load_dict(read_config_file(config_file))
    return config


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
        help='config to use (see Cerebrum.modules.consumer.config)',
    )
    parser.add_argument(
        '-l', '--limit',
        type=int,
        default=0,
        help='Limit number of tasks to %(metavar)s (required in dryrun)',
        metavar='<n>',
    )
    # parser.add_argument(
    #     '-m', '--max-retries',
    #     type=int,
    #     default=DEFAULT_MAX_RETRIES,
    #     help='Do not process tasks more than %(metavar)s times (%(default)s)',
    #     metavar='<n>',
    # )

    # TODO: we may want to separate between commit/rollback of tasks,
    # and commit/rollback of task processing.
    #
    # Commiting task result, but rollback changes from task processing would
    # be simple - the inverse (commit changes, rollback task) would require
    # some more refactoring.
    add_commit_args(parser)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    config = get_config(args.config)
    dryrun = not args.commit

    limit = args.limit

    handle = get_task_handler(config)

    if limit:
        counter = range(limit)
    elif args.commit:
        counter = itertools.count()
    else:
        # We need a limit when running in dry-run, as we'll end up
        # re-processing the same task again and again.
        #
        # *one* possible improvement for dryrun=True would be to wrap the
        # entire process in a db_context, and then replace the per-pop
        # db_context with a savepoint(db, dryrun=False)
        raise RuntimeError('Cannot run in --dryrun without --limit')

    nbf_cutoff = now()

    for n in counter:
        with db_context(get_db(), dryrun) as db:
            try:
                task = TaskQueue(db).pop_next(queues=handle.all_queues,
                                              nbf=nbf_cutoff,
                                              max_attempts=handle.max_attempts)
            except Cerebrum.Errors.NotFoundError:
                # No more tasks to process
                break

            # TODO: we may want separate dryrun/commit args for *db_context*
            # and *handle*
            handle(db, dryrun, task)

    # log info on events that we've given up on
    with db_context(get_db(), dryrun) as db:
        for row in sql_get_queue_counts(db, queues=handle.all_queues,
                                        min_attempts=handle.max_attempts):
            if row['num']:
                logger.warning('queue: %s, given up on %d failed items',
                               row['queue'], row['num'])


if __name__ == '__main__':
    main()
