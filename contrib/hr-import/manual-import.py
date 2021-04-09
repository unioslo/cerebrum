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
Import person from hr-system directly, without using tasks.

See :py:class:`Cerebrum.modules.hr_import.config.TaskImportConfig` for
configuration instructions.  Note that this script won't actually need or
require a valid *task_class*.
"""
import argparse
import logging
import functools

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.utils.module import resolve
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory


logger = logging.getLogger(__name__)


def get_db():
    """ Get an initialized db connection. """
    db = Factory.get('Database')()
    db.cl_init(change_program='manual-hr-import')
    return db


def get_import_factory(config):
    """ Get import handler from config.

    :rtype: callable
    :returns:
        a factory function that takes a database argument and returns an
        EmployeeImport object.
    """
    import_cls = resolve(config.import_class)
    return functools.partial(import_cls, config=config)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Update a single employee by reference',
        epilog="""
            This script fetches and updates a single employee directly
            from the hr-system, without any use of tasks or
            notifications
        """.strip()
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help='hr-import config to use (see Cerebrum.modules.hr_import.config)',
    )
    parser.add_argument(
        'reference',
        help='A source system reference to import (e.g. employee id)',
    )

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('tee', args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %r", args)

    # we don't really need the full TaskImportConfig here, but it's easier to
    # re-use the existing config.
    config = TaskImportConfig.from_file(args.config)
    get_import = get_import_factory(config)

    with db_context(get_db(), not args.commit) as db:
        employee_import = get_import(db)

        logger.info('handle reference=%r', args.reference)
        employee_import.handle_reference(args.reference)

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
