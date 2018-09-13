#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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
"""This program provides statistics about various activities within Cerebrum.

Currently it reports the following:
* 'Create person'-events
* 'Create account'-events
* 'Modify account'-events (reactivation only)
* 'Create group'-events

Where such information can be found, it also breaks the event-counts
down by affiliation, when the 'affiliation'-option is used.

"""

import sys
import getopt

from mx.DateTime import now, RelativeDateTime, ISO, Monday

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.CLProcessors import EventProcessor
from Cerebrum.Constants import _ChangeTypeCode

db = Factory.get('Database')()
clconstants = Factory.get('CLConstants')(db)
logger = Factory.get_logger("cronjob")


# Default choices for script options
options = {"affiliations": False,
           "source_system": None,
           "details": False,
           "header": None,
           "events": "person_create,account_create,account_mod,group_create",
           "from": now() + RelativeDateTime(days=-7, weekday=(Monday, 0)),
           "to": now() + RelativeDateTime(weekday=(Monday, 0))}


def usage(exitcode=0, message=None):
    """Gives user info on how to use the program and its options."""

    if message is not None:
        print "\n%s" % message
    print """\nUsage: %s [options]

    --help           Prints this message.

    --affiliations   Break down totals by affiliation also.

    --source-system  Show information for given source system.

    --from           Start date for events to be processed (inclusive).
                     Default value is Monday of last week.

    --to             End-date for events to be processed (exclusive).
                     Default value is Sunday of last week.

    --details        List details about the events in question. The
                     exact type of details will vary by event.

    --header         Template-file to use as header rather than the one
                     specified in cereconf.

    --events         Comma-seperated list of events to process.
                     Default is to process alt events that have handlers
                     defined, i.e:
                     %s

    Using the defaults will give you a report about all event types,
    without affiliation info, with no details about the events, with
    the cereconf-defined template as header, spanning all of last
    week.

    'from' and 'to' must be given in standard ISO format, i.e. YYYY-MM-DD.

    """ % (sys.argv[0], options["events"])
    sys.exit(exitcode)


def main():
    """Main processing 'hub' of program.

    Decides which areas to generate, then generates them sequentially,
    dumping collected and relevant info to STDOUT along the way.

    """
    logger.info("Statistics for Cerebrum activities - processing started")
    logger.debug("Time period: from: '%s'; up to: '%s'" %
                 (options['from'].date, options['to'].date))

    # Check the given events to make sure they are valid changelog events
    event_types = []
    for element in options['events'].split(','):
        try:
            event = getattr(clconstants, element)
            if not isinstance(event, _ChangeTypeCode):
                raise AttributeError
        except AttributeError:
            logger.warning("Unknown event-type '%s'" % element)
            continue
        event_types.append(event)

    if not event_types:
        usage(exitcode=3, message="ERROR: No valid event-types specified")

    print ""
    print ("Statistics covering the period from %s up to %s" %
           (options['from'].date, options['to'].date))

    if options['header'] is None:
        options['header'] = cereconf.STATISTICS_EXPLANATION_TEMPLATE

    if options['header'] is not None:
        print ""
        try:
            f = file(options['header'])
            for line in f.readlines():
                print line,
        except IOError:
            logger.warning("Unable to find explanatory file: '%s'"
                           % options['header'])
    else:
        logger.debug("No explanation file defined in cereconf")

    # Iterate over all event types, retrieve info and generate output
    # based on it.
    for current_type in event_types:
        logger.info("Looking at '%s'" % current_type)
        processor = EventProcessor.get_processor(current_type)
        processor.process_events(start_date=options['from'],
                                 end_date=options['to'])
        if options['affiliations']:
            processor.calculate_count_by_affiliation()
        # count by source system only makes sense for person entities
        if options['source_system'] and str(current_type) == 'person:create':
            processor.calculate_count_by_source_system(
                options['source_system'])
        processor.print_report(
            print_affiliations=options['affiliations'],
            print_source_system=bool(options['source_system']),
            print_details=options['details'])
    print ""  # For a nice newline at the end of the report


if __name__ == '__main__':
    logger.info("Statistics for Cerebrum activities")
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "hadf:t:h:e:s:",
                                   ["help", "affiliations", "details",
                                    "from=", "to=", "header=", "events=",
                                    "source-system="])
    except getopt.GetoptError:
        # print help information and exit
        usage(1)

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
        elif opt in ('-f', '--from',):
            logger.debug("Will process events since %s" % val)
            try:
                options['from'] = ISO.ParseDate(val)
            except ValueError:
                logger.error("Incorrect 'from'-format")
                usage(exitcode=2, message="ERROR: Incorrect 'from'-format")
        elif opt in ('-t', '--to',):
            logger.debug("Will process events till %s" % val)
            try:
                options['to'] = ISO.ParseDate(val)
            except ValueError:
                logger.error("Incorrect 'to'-format")
                usage(exitcode=2, message="ERROR: Incorrect 'to'-format")
        elif opt in ('-a', '--affiliations',):
            logger.debug("Will process and display info about affiliations")
            options['affiliations'] = True
        elif opt in ('-s', '--source-system',):
            logger.debug("Will process and display info about source system")
            options['source_system'] = val
        elif opt in ('-d', '--details',):
            logger.debug("Will display details about the events in question")
            options['details'] = True
        elif opt in ('-h', '--header',):
            logger.debug("Will use alternative template file '%s' as header",
                         val)
            options['header'] = val
        elif opt in ('-e', '--events',):
            logger.debug("Will process these events: '%s'" % val)
            options['events'] = val
    main()
    logger.info("Statistics for Cerebrum activities - done")
