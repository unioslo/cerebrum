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
HR import person.

Runs an HR sync for a single object to update a Cerebrum object.

See :mod:`Cerebrum.modules.hr_import.config` for configuration instructions.
"""
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.config.loader import read_config as read_config_file
from Cerebrum.modules.hr_import.config import HrImportConfig
from Cerebrum.modules.hr_import.handler import db_context
from Cerebrum.utils.module import resolve
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Utils import Factory


logger = logging.getLogger(__name__)


def get_config(config_file):
    """ Load config.

    :param str config_file:
        Read configuration from this file.

    :return ConsumerConfig:
        Returns a configuration object.
    """
    config = HrImportConfig()
    config.load_dict(read_config_file(config_file))
    return config


def get_importer(importer_config):
    init = resolve(importer_config.module)
    return init(importer_config.config_file)


def get_db():
    db = Factory.get('Database')()
    db.cl_init(change_program='hr-import-person')
    return db


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Run import for a single hr-system object',
    )
    parser.add_argument(
        '-c', '--config',
        required=False,
        help='config to use (see Cerebrum.modules.consumer.config)',
    )
    parser.add_argument(
        'reference',
        help='A source system reference to import (e.g. employee id)',
    )

    add_commit_args(parser)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('tee', args)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    config = get_config(args.config)

    import_init = get_importer(config.importer)
    logger.info('employee importer: %r', import_init)

    with db_context(get_db, not args.commit) as db:
        importer = import_init(db)

        logger.info('handle reference=%r', args.reference)
        importer.handle_reference(args.reference)


if __name__ == '__main__':
    main()
