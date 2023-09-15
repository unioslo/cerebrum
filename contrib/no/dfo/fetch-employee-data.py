#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
Fetch employees and assignments from the hr-system.

This script fetches all objects the HR system, and writes to a named JSON file.
See :class:`Cerebrum.modules.no.dfo.client` for configuration instructions.

Example
--------
To get employees and assignments at a given date:

::

    python fetch-all-employees.py --date 2023-01-01 <client-config> <filename>

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import logging
import json

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.no.dfo.client import get_client
from Cerebrum.utils import date as date_utils


logger = logging.getLogger(__name__)


def fetch_employee_data(client, date=None):
    date_str = (date or datetime.date.today()).isoformat()
    logger.info("fetching employee data at date=%s with client=%s",
                date_str, repr(client))

    employees = client.list_employees(date=date)
    assignments = client.list_assignments(date=date)

    logger.info("found %d employees, %d assignments",
                len(employees), len(assignments))
    return {
        'date': date_str,
        'employees': employees,
        'assignments': assignments,
    }


def write_employee_data(data, filename):
    with open(filename, 'w') as fd:
        json.dump(
            data,
            fd,
            indent=2,
            sort_keys=True,
        )
    logger.info("Wrote output to %s", filename)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Fetch all employee data',
        epilog="""
            This script fetches and stores listings from the hr-system.
        """.strip()
    )
    parser.add_argument(
        '--date',
        type=date_utils.parse_date,
        help="Get result at a given date",
    )
    parser.add_argument(
        'config',
        help='client config to use (see Cerebrum.modules.no.dfo.client)',
    )
    parser.add_argument(
        'filename',
        help='JSON-file to write to',
    )
    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'INFO',
    })

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    client = get_client(args.config)
    data = fetch_employee_data(client, date=args.date)
    write_employee_data(data, args.filename)

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
