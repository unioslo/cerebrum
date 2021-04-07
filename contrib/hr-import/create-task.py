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
""" Process tasks on the hr import queues. """
from __future__ import print_function
import argparse
import pprint
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.module import resolve


logger = logging.getLogger(__name__)


def get_task_class(config):
    return resolve(config.task_class)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Create a hr-import task for a given task processor',
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help='config to use (see Cerebrum.modules.consumer.config)',
    )
    parser.add_argument(
        'reference',
        type=str,
    )

    add_commit_args(parser)

    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'INFO',
    })
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('tee', args)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    config = TaskImportConfig.from_file(args.config)
    dryrun = not args.commit

    task_cls = get_task_class(config)
    task = task_cls.create_manual_task(args.reference)

    with db_context(Factory.get('Database')(), dryrun) as db:
        result = TaskQueue(db).push(task)

    if dryrun:
        print('dryrun, would have added:')
    else:
        print('added:',)
    pprint.pprint(result.to_dict())


if __name__ == '__main__':
    main()
