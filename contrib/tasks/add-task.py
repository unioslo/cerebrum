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
""" add event to the Cerebrum.modules.event_queue """
from __future__ import print_function, unicode_literals

import argparse
import io
import logging

import aniso8601

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.date import now
from Cerebrum.Utils import Factory
from Cerebrum.modules.tasks.task_queue import TaskQueue
from Cerebrum.modules.tasks.task_models import Task

logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(
    description='Push event onto queue',
)

parser.add_argument(
    '--delay',
    type=aniso8601.parse_duration,
    help='set nbf to now + %(metavar)s, %(metavar)s is an ISO8601 duration',
    metavar='<delay>',
)
parser.add_argument(
    '--force',
    action='store_true',
    help='replace existing events, even if the new nbf is after the next nbf',
)

parser.add_argument(
    'queue',
    default='test-queue',
    help='push event onto queue %(metavar)s (default: %(default)s)',
    metavar='<queue>',
)
parser.add_argument(
    'key',
    help='set event key to %(metavar)s (default: generate)',
    metavar='<key>',
)

add_commit_args(parser.add_argument_group('Database'))
log_sub = Cerebrum.logutils.options.install_subparser(parser)


def pretty_format(task):
    out = io.StringIO()
    out.write('  queue: {}\n'.format(task.queue))
    out.write('  key:   {}\n'.format(task.key))
    out.write('  iat:   {}\n'.format(task.iat))
    out.write('  nbf:   {}\n'.format(task.nbf))
    return out.getvalue()


def main(inargs=None):
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    if args.delay:
        nbf = now() + args.delay
    else:
        nbf = now()

    task = Task(
        queue=args.queue,
        key=args.key,
        nbf=nbf,
        reason=(
            'add-task: manually added task to queue=%r with key=%r' %
            (args.queue, args.key)),
    )

    db = Factory.get('Database')()
    queue = TaskQueue(db)

    added = queue.push(task, ignore_nbf_after=(not args.force))
    if added:
        print('Added/updated task:')
        print(pretty_format(added))
    else:
        print('Ignored task:')
        print(pretty_format(task))
        existing = queue.get(task.queue, task.key)
        print('Already exists as:')
        print(pretty_format(existing))

    if args.commit:
        db.commit()
        logger.info('changes commited (--commit)')
    else:
        db.rollback()
        logger.info('changes rolled back (--dryrun)')

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
