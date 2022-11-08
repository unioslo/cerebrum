#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020-2022 University of Oslo, Norway
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
Fetch and show normalized data from hr-system.

This script fetches an object from the HR system.  The type of object depends
on the configured import datasource.  See
:class:`Cerebrum.modules.hr_import.config.TaskImportConfig` for configuration
instructions.

Examples
--------
::

    python fetch-resource.py --config <employee-config> <employee-id>
    python fetch-resource.py --config <assignment-config> <assignment-id>

"""
from __future__ import print_function
import argparse
import logging
import functools

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.hr_import.config import TaskImportConfig
from Cerebrum.modules.hr_import.datasource import RemoteObject
from Cerebrum.utils.module import resolve
from Cerebrum.Utils import Factory


logger = logging.getLogger(__name__)


def get_import_factory(config):
    """ Get import handler from config.

    :rtype: callable
    :returns:
        a factory function that takes a database argument and returns an
        EmployeeImport object.
    """
    import_cls = resolve(config.import_class)
    return functools.partial(import_cls, config=config)


def pretty(d, indent='  ', _level=0):
    for key in sorted(d):
        value = d[key]
        if isinstance(value, RemoteObject):
            value = dict(value)

        print(indent * _level, str(key), sep='', end=':')
        if isinstance(value, dict):
            print('')
            pretty(value, indent=indent, _level=_level + 1)
        else:
            print('', repr(value))


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Fetch employee/assignment data by reference',
        epilog="""
            This script fetches and shows a single object directly from the
            hr-system.
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
    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'WARNING',
    })

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    # we don't really need the full TaskImportConfig here, but it's easier to
    # re-use the existing config.
    config = TaskImportConfig.from_file(args.config)
    get_import = get_import_factory(config)

    with db_context(Factory.get('Database')(), dryrun=True) as db:
        employee_import = get_import(db)
        datasource = employee_import.datasource

    employee_data = datasource.get_object(args.reference)
    pretty((employee_data))


if __name__ == '__main__':
    main()
