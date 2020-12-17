#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2015 University of Oslo, Norway
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
import argparse
import json
import logging
import sys

from mx.DateTime import DateTimeType

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import get_constant

logger = logging.getLogger(__name__)


class JsonEncoder(json.JSONEncoder):
    """ mx.DateTime-aware json encoder. """
    def default(self, obj):
        if isinstance(obj, DateTimeType):
            return obj.strftime('%Y-%m-%d %H:%M:%S.00')
        return json.JSONEncoder.default(self, obj)


def get_quarantines(db, quarantine_types):
    """List quarantines.

    :param db: Database-object.
    :param quarantine_types: Quarantine-types to filter by.

    :param iterable quarantines: An iterable with quarantine db rows.
    :return iterable: An iterable with quarantine db rows.
    """
    eq = EntityQuarantine(db)
    for row in eq.list_entity_quarantines(quarantine_types=quarantine_types):
        yield row.dict()


def codes_to_human(db, quarantines):
    """Convert Cerebrum-codes to more usable information.
    :param db: Database-object.
    :param en: Entity-object.
    :param co: Constants-object.

    :param iterable quarantines: An iterable with quarantine db rows.
    :return iterable: An iterable with modified quarantine db rows.
    """
    en = Factory.get('Entity')(db)
    co = Factory.get('Constants')(db)
    for q in quarantines:
        q['quarantine_type'] = str(co.Quarantine(q['quarantine_type']))
        en.clear()
        en.find(q['entity_id'])
        if en.entity_type == co.entity_account:
            q['account_name'] = en.get_subclassed_object().account_name
            del q['entity_id']
        yield q


def write_report(stream, quarantines):
    """Dump a list of quarantines to JSON-file.

    Objects of type mx.DateTime.DateTimeType are serialized by calling str().

    :param list(<Cerebrum.extlib.db_row.row>) quarantines: List of quarantines.
    :param basestring outfile: File to write."""

    json.dump(list(quarantines), stream,
              cls=JsonEncoder, indent=4, sort_keys=True)
    stream.write("\n")
    stream.flush()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Export quarantines in JSON-format to file")
    parser.add_argument(
        '--outfile',
        dest='output',
        type=argparse.FileType('w'),
        default='-',
        metavar='FILE',
        help='Output file for report, defaults to stdout')
    q_arg = parser.add_argument(
        '--quarantines',
        nargs='+',
        required=True,
        help="Quarantines that should be exported (i.e. 'radius vpn')")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    quarantines = [get_constant(db, parser, co.Quarantine, q, q_arg)
                   for q in args.quarantines]

    logger.info('Start of script %s', parser.prog)
    logger.debug("quarantines: %r", quarantines)

    quarantines = codes_to_human(db, get_quarantines(db, quarantines))
    write_report(args.output, quarantines)

    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
