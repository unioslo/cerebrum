#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2021-2023 University of Oslo, Norway
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
Import person from Greg directly, without using tasks.

See :py:class:`Cerebrum.modules.greg.client.GregClientConfig` for
configuration instructions.
"""
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
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.greg.client import get_client
from Cerebrum.modules.greg.importer import get_import_class
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def get_db():
    """ Get an initialized db connection. """
    db = Factory.get('Database')()
    db.cl_init(change_program='greg-manual-import')
    return db


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Update a single employee by reference',
        epilog="""
            This script fetches and updates a single guest directly
            from Greg, without any use of tasks or
            notifications
        """.strip()
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help='Greg client config (see Cerebrum.modules.greg.client)',
    )
    parser.add_argument(
        'reference',
        help='A Greg person id to import',
    )

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    default_preset = 'tee' if args.commit else 'console'
    Cerebrum.logutils.autoconf(default_preset, args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %r", args)

    client = get_client(args.config)
    import_class = get_import_class()

    with db_context(get_db(), not args.commit) as db:
        greg_import = import_class(db, client=client)

        logger.info('handle reference=%r', args.reference)
        greg_import.handle_reference(args.reference)

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
