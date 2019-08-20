#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2019 University of Oslo, Norway
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
This program provides statistics about various activities within Cerebrum.

Currently it reports the following:
* 'Create person'-events
* 'Create account'-events
* 'Modify account'-events (reactivation only)
* 'Create group'-events

Where such information can be found, it also breaks the event-counts
down by affiliation, when the 'affiliation'-option is used.

cereconf
--------

STATISTICS_EXPLANATION_TEMPLATE
    The default header file (plaintext utf-8 encoded file) to include in the
    report output.

"""
from __future__ import print_function

import argparse
import io
import logging

import mx.DateTime

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils import argutils
from Cerebrum.Utils import Factory
from Cerebrum.modules.CLProcessors import get_processor

import cereconf

logger = logging.getLogger(__name__)

help_epilog = """
Using the defaults will give you a report about all event types,
without affiliation info, with no details about the events, with
the cereconf-defined template as header, spanning all of last
week.

'from' and 'to' must be given in standard ISO format, i.e. YYYY-MM-DD.
""".strip()

default_events = ('person_create', 'account_create', 'account_mod',
                  'group_create')

default_header_file = getattr(cereconf, 'STATISTICS_EXPLANATION_TEMPLATE')


def relative_date(days):
    """ Get a date relative to monday. """
    weekday = (mx.DateTime.Monday, 0)
    return mx.DateTime.now() + mx.DateTime.RelativeDateTime(days=days,
                                                            weekday=weekday)


def get_header(filename, encoding='utf-8'):
    if filename:
        logger.debug('Printing header from %r', filename)
        try:
            with io.open(filename, 'r', encoding=encoding) as f:
                return f.read() + "\n"
        except IOError:
            logger.warning('Unable to open header file %r', filename,
                           exc_info=True)
    else:
        logger.debug('No header file')
    return ""


def main(inargs=None):
    """Main processing 'hub' of program.

    Decides which areas to generate, then generates them sequentially,
    dumping collected and relevant info to STDOUT along the way.
    """
    parser = argparse.ArgumentParser(
        description="Prints changelog summaries to stdout",
        epilog=help_epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        '--affiliations',
        action='store_true',
        default=False,
        help='Break down totals by affiliation',
    )
    src_arg = parser.add_argument(
        '--source-system',
        help='Show information for given source system',
    )
    parser.add_argument(
        '--details',
        action='store_true',
        default=False,
        help=('List details about the events in question. '
              'The exact type of details will vary by event.'),
    )
    parser.add_argument(
        '--from',
        dest='from_date',
        type=mx.DateTime.ISO.ParseDate,
        default=relative_date(-7),
        help=('Start date for events to be processed. '
              'Default value is Monday of last week.'),
    )
    parser.add_argument(
        '--to',
        dest='to_date',
        type=mx.DateTime.ISO.ParseDate,
        default=relative_date(0),
        help=('End-date for events to be processed. '
              'Default value is Sunday of last week.'),
    )
    parser.add_argument(
        '--header',
        default=default_header_file,
        help=('Template-file to use as header rather than the one '
              'specified in cereconf.'),
    )
    events_arg = parser.add_argument(
        '--events',
        help=('Comma-seperated list of events to process. '
              'Default is to process alt events that have handlers '
              'defined, i.e: %s' % (default_events, )),
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Statistics for Cerebrum activities")
    logger.debug('args=%r', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    cl = Factory.get('CLConstants')(db)

    def get_change_type(value):
        const_value = cl.resolve_constant(db, value, cl.ChangeType)
        if const_value is None:
            raise ValueError("invalid constant value: %r" % (value, ))
        return const_value

    if args.source_system:
        source_system = argutils.get_constant(
            db, parser, co.AuthoritativeSystem, args.source_system,
            argument=src_arg)
    else:
        source_system = None
    logger.debug('source_system=%r', source_system)

    with argutils.ParserContext(parser, events_arg):
        event_types = [get_change_type(v) for v in (args.events.split(',')
                                                    if args.events
                                                    else default_events)]
        if not event_types:
            raise ValueError('No valid event-types specified')
    logger.debug('event_types=%r', event_types)

    logger.info("Statistics for Cerebrum activities - processing started")
    logger.debug("Time period: from: '%s'; up to: '%s'",
                 str(args.from_date.date), str(args.to_date.date))

    print("")
    print("Statistics covering the period from %s up to %s" %
          (args.from_date.date, args.to_date.date))
    print(get_header(args.header))

    # Iterate over all event types, retrieve info and generate output
    # based on it.
    for current_type in event_types:
        logger.info("processing change_type=%r", current_type)
        processor = get_processor(db, current_type)
        logger.debug('using processor=%r', processor)
        processor.process_events(start_date=args.from_date,
                                 end_date=args.to_date)
        if args.affiliations:
            processor.calculate_count_by_affiliation()
        # count by source system only makes sense for person entities
        if source_system and str(current_type) == 'person:create':
            processor.calculate_count_by_source_system(source_system)
        processor.print_report(
            print_affiliations=args.affiliations,
            print_source_system=bool(source_system),
            print_details=args.details)
    print("")

    logger.info("Statistics for Cerebrum activities - done")


if __name__ == '__main__':
    main()
