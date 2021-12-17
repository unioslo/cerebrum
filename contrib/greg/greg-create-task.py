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
""" Manually add a greg-person import task. """

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.greg.tasks import GregImportTasks
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.utils import json
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def pprint(data):
    print(json.dumps(data, indent=2, sort_keys=True))


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Manually add a greg import task to the task queue',
    )
    parser.add_argument(
        'reference',
        type=str,
        help='A Greg person id to import',
    )

    db_args = parser.add_argument_group('Database')
    add_commit_args(db_args)

    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'INFO',
    })
    args = parser.parse_args(inargs)

    default_preset = 'tee' if args.commit else 'console'
    Cerebrum.logutils.autoconf(default_preset, args)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    dryrun = not args.commit

    task = GregImportTasks.create_manual_task(args.reference)

    with db_context(Factory.get('Database')(), dryrun) as db:
        result = TaskQueue(db).push_task(task)

    if dryrun:
        print('Dryrun, would have added:')
    else:
        print('Task added:')
    pprint(result.to_dict())


if __name__ == '__main__':
    main()
