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

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.modules.tasks.queue_processor import QueueProcessor
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.module import resolve


logger = logging.getLogger(__name__)


def get_task_handler(config):
    import_cls = resolve(config.import_class)
    logger.info('import_cls: %s', config.import_class)

    task_cls = resolve(config.task_class)
    logger.info('task_cls: %s', config.task_class)

    def callback(db, task):
        import_obj = import_cls(db, config=config)
        dfo_id = task.payload.data['id']
        return import_obj.handle_reference(dfo_id)

    return task_cls(callback)


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
    add_commit_args(db_args)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %r", args)

    config = TaskImportConfig.from_file(args.config)
    dryrun = not args.commit

    proc = QueueProcessor(get_task_handler(config),
                          limit=args.limit,
                          dryrun=dryrun)

    tasks = proc.select_tasks()
    for task in tasks:
        proc.process_task(task)

    # Check for tasks that we've given up on (i.e. over the
    # GregImportTasks.max_attempts threshold)
    logger.info('checking for abandoned tasks...')
    for (queue, sub), count in proc.get_abandoned_counts():
        logger.warning('queue: %s/%s, given up on %d failed items',
                       queue, sub, count)

    logger.info('done %s', parser.prog)


if __name__ == '__main__':
    main()
