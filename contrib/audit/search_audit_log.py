# -*- coding: utf-8 -*-
#
# Copyright 2018-2023 University of Oslo, Norway
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
Search audit log for records.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import datetime
import itertools
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.audit.auditdb import AuditLogAccessor
from Cerebrum.modules.audit.formatter import (
    AuditRecordFormatter,
    AuditRecordProcessor,
)
from Cerebrum.utils import argutils
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import date_compat

logger = logging.getLogger(__name__)


def _entity_lookup(db):
    """ create an entity lookup function. """
    def lookup_entity(value):
        """ Lookup entity_id from names, etc... """
        if isinstance(value, int):
            return value
        if isinstance(value, tuple):
            e_type, e_value = value
            # TODO: We should have a re-usable lookup system,
            #       generalize BofhdCommandBase._get_* ?
            raise NotImplementedError('implement lookup')
        raise ValueError("invalid value %r" % (value, ))
    return lookup_entity


def _change_type_lookup(db):
    """ create a ChangeType lookup function. """
    clconst = Factory.get('CLConstants')(db)

    def lookup_change(value):
        """ Look up change type constant """
        const_value = clconst.human2constant(value, clconst.ChangeType)
        if const_value is None:
            raise ValueError("invalid constant value: %r" % (value, ))
        return const_value
    return lookup_change


def build_search_params(db, args):
    """ args -> AuditLogAccessor.search() kwargs. """
    lookup_entity = _entity_lookup(db)
    lookup_change = _change_type_lookup(db)

    search_params = {}
    if args.change_types:
        search_params['change_types'] = [lookup_change(c) for c in
                                         (args.change_types)]

    if args.operators:
        search_params['operators'] = [lookup_entity(e) for e in args.operators]
    if args.entities:
        search_params['entities'] = [lookup_entity(e) for e in args.entities]
    if args.targets:
        search_params['targets'] = [lookup_entity(e) for e in args.targets]

    if args.record_ids:
        search_params['record_ids'] = set(itertools.chain(*(args.record_ids)))
    if args.min_id is not None:
        search_params['after_id'] = args.min_id
    if args.max_id is not None:
        search_params['before_id'] = args.max_id

    if args.after is not None:
        search_params['after_timestamp'] = args.after
    if args.before is not None:
        search_params['before_timestamp'] = args.before
    return search_params


def entity_type(value):
    if value.isdigit():
        return int(value)

    e_type, _, e_ident = value.partition(':')
    if not e_type:
        raise ValueError('No type (%r)' % (e_type, ))
    if not e_type:
        raise ValueError('No value (%r)' % (e_ident, ))
    return (e_type, e_ident)


def change_id_type(value):
    """ strval to int iterables.

    >>> list(change_id_type('8'))
    [8]
    >>> list(change_id_type('3-5'))
    [3, 4, 5]
    """
    start, _, end = value.partition('-')
    start = int(start)
    if end:
        end = int(end)
        return six.moves.range(start, end + 1)
    else:
        return six.moves.range(start, start + 1)


def datetime_type(value):
    def _parse_time(value):
        t = date_utils.parse_time(value)
        return datetime.datetime.combine(datetime.date.today(), t)

    for parser in (
            date_utils.parse_datetime,
            date_utils.parse_date,
            _parse_time):
        try:
            dt = date_compat.get_datetime_tz(parser(value))
            logger.debug("%s(%r) succeeded: %s", parser.__name__, value, dt)
            return dt
        except Exception as e:
            logger.debug("%s(%r) failed: %s", parser.__name__, value, e)
    raise ValueError("invalid datetime (%r)" % (value, ))


def get_formatter(args):
    _process = AuditRecordProcessor()

    if args.format:
        _formatter = AuditRecordFormatter(args.format)
    else:
        _formatter = AuditRecordFormatter(
            '{timestamp} - {change_type} - {change_by} - {message}')

    def format_record(record):
        return _formatter(_process(record))
    return format_record


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Search audit log for records")

    type_args = parser.add_argument_group(
        'change type',
        'limit records by change type')
    type_args.add_argument(
        '-c', '--change-type',
        dest='change_types',
        action='append',
        help='Only include changes of type %(metavar)s',
        metavar='TYPE')

    entity_args = parser.add_argument_group(
        'operator, entity, target',
        'limit records to a subset of entities')
    entity_args.add_argument(
        '-o', '--operator',
        dest='operators',
        action='append',
        type=entity_type,
        help='entity_id (or <type:name>) of an operator',
        metavar='ENTITY')
    entity_args.add_argument(
        '-e', '--entity',
        dest='entities',
        action='append',
        type=entity_type,
        help='entity_id (or <type:name>) of an entity',
        metavar='ENTITY')
    entity_args.add_argument(
        '-t', '--target',
        dest='targets',
        action='append',
        type=entity_type,
        help='entity_id (or <type:name>) of a target entity',
        metavar='ENTITY')

    record_id_args = parser.add_argument_group(
        'record id',
        'limit records by record id')
    record_id_args.add_argument(
        '-i', '--record-id',
        dest='record_ids',
        action='append',
        type=change_id_type,
        help='record ids (range %(metavar)s-%(metavar)s or'
             ' single value %(metavar)s)',
        metavar='N')
    record_id_args.add_argument(
        '--min-id',
        type=int,
        help='limit results to record ids > %(metavar)s',
        metavar='ID')
    record_id_args.add_argument(
        '--max-id',
        type=int,
        help='limit results to record ids < %(metavar)s',
        metavar='ID')

    date_args = parser.add_argument_group(
        'timestamp',
        'Filter records by date and time. '
        'Use ISO 8601 formatted date and time strings')
    date_args.add_argument(
        '-A', '--after',
        type=datetime_type,
        help='only include results logged after %(metavar)s',
        metavar='DATE')
    date_args.add_argument(
        '-B', '--before',
        type=datetime_type,
        help='only include results logged before %(metavar)s',
        metavar='DATE')

    parser.add_argument(
        '--format',
        default='{timestamp}  [{change_by}]:  {message}',
        type=argutils.UnicodeType(),
        help="specify format usign str.format syntax",
        metavar="FORMAT",
    )

    parser.add_argument(
        '-l', '--limit',
        type=int,
        help='Limit to %(metavar)s results',
        metavar='N')

    parser.add_argument(
        '-s', '--sort',
        action='store_true',
        default=False,
        help='Sort records by timestamp')

    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: "ERROR",
    })
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf("console", args)

    db = Factory.get("Database")()

    logger.info("start: %s", parser.prog)
    logger.debug("args: %r", args)

    record_db = AuditLogAccessor(db)
    format_record = get_formatter(args)
    search_params = build_search_params(db, args)
    logger.info("search: %r", search_params)
    records = iter(record_db.search(**search_params))

    if args.sort:
        logger.debug("sorting records by timestamp")
        records = sorted(records, key=lambda r: r.timestamp)

    if args.limit:
        logger.debug("limiting to %r first records", args.limit)
        records = itertools.islice(records, 0, args.limit)

    for r in records:
        print(format_record(r))

    logger.info("done: %s", parser.prog)


if __name__ == "__main__":
    main()
