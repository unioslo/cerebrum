#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2025 University of Oslo, Norway
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
"""Utilities/script to export quarantines to file."""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import json
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.Utils import Factory
from Cerebrum.utils import file_stream
from Cerebrum.utils.argutils import get_constant
from Cerebrum.utils.date_compat import get_date, to_mx_format

logger = logging.getLogger(__name__)


class JsonEncoder(json.JSONEncoder):
    """ datetime-aware json encoder. """
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return to_mx_format(obj)
        return json.JSONEncoder.default(self, obj)


def get_account_name_cache(db):
    """ Get a cache of all account names (including expired accounts). """
    ac = Factory.get('Account')(db)
    cache = {}
    logger.debug("caching account names...")
    for row in ac.search(expire_start=None):
        account_id = row['account_id']
        account_name = row['name']
        cache[account_id] = account_name
    logger.info("Found %d account names", len(cache))
    return cache


def get_quarantines(db, quarantine_types):
    """
    List active account quarantines of the given type(s).

    :type db: Cerebrum.database.Database
    :param list quarantine_types: one or more quarantine types to filter by.

    :returns generator: An iterable of matching quarantine dicts
    """
    eq = EntityQuarantine(db)
    for row in eq.list_entity_quarantines(
            quarantine_types=quarantine_types,
            entity_types=int(eq.const.entity_account)):
        yield {
            'entity_id': row['entity_id'],
            'quarantine_type': row['quarantine_type'],
            'start_date': get_date(row['start_date'], allow_none=False),
            'disable_until': get_date(row['disable_until'], allow_none=True),
            'end_date': get_date(row['end_date'], allow_none=True),
            'description': row['description'],
        }


def prepare_entries(db, quarantines):
    """
    Prepare quarantine entries from *get_quarantines* for export.

    This step adds useful information like quarantine names and account names.

    :type db: Cerebrum.database.Database
    :param iterable quarantines: results from *get_quarantines*

    :returns generator: An iterable with updated quarantine dicts
    """
    co = Factory.get('Constants')(db)
    name_cache = get_account_name_cache(db)

    for q in quarantines:
        q['quarantine_type'] = six.text_type(
            co.Quarantine(q['quarantine_type']))
        name = name_cache.get(q['entity_id'])
        if name:
            q['account_name'] = name
            del q['entity_id']
        yield q


def write_report(filename, quarantines):
    """Dump a list of quarantines to JSON-file.

    :param list quarantines: quarantine database rows to report.
    :param file outfile: file-like object to write to
    """
    # If the default str is a bytestring, then json.dump produces bytestrings
    # for our file stream:
    encoding = None if str is bytes else "utf-8"

    # Sort results by quarantine start date and account name or id
    quarantines = sorted(
        quarantines,
        key=lambda q: (q['start_date'].isoformat(),
                       q.get('account_name') or six.text_type(q['entity_id']))
    )
    with file_stream.get_output_context(filename, encoding=encoding) as stream:
        json.dump(
            quarantines,
            stream,
            cls=JsonEncoder,
            indent=4,
            sort_keys=True,
        )
        # Writing a unicode newline to a byte stream in Python 2.  This works
        # because of Python 2 implicit conversion:
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Export quarantines in JSON-format to file",
    )
    parser.add_argument(
        '--outfile',
        dest='output',
        default='-',
        metavar='FILE',
        help='Output file for report, defaults to stdout',
    )
    q_arg = parser.add_argument(
        '--quarantines',
        nargs='+',
        required=True,
        help="Quarantines that should be exported (i.e. 'radius vpn')",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    quarantines = [get_constant(db, parser, co.Quarantine, q, q_arg)
                   for q in args.quarantines]

    logger.info('Start: %s', parser.prog)
    logger.debug("quarantines: %r", quarantines)

    quarantines = prepare_entries(db, get_quarantines(db, quarantines))
    write_report(args.output, quarantines)

    logger.info('Report written to %s', args.output)
    logger.info('Done: %s', parser.prog)


if __name__ == '__main__':
    main()
