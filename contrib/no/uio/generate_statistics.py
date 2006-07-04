#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright 2006 University of Oslo, Norway
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

import sys
import getopt

from mx.DateTime import *

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.CLProcessors import *

"""This program provides statistics about various activities within Cerebrum.

Currently it reports the following:
* 'Create person'-events
* 'Create account'-events
* 'Create group'-events

Where such information can be found, it also breaks the event-counts
down by affiliation, when the 'affiliation'-option is used.

"""

__version__ = "$Revision$"
# $Source$


logger = Factory.get_logger("cronjob")


# Default choices for script options
options = {"affiliations": False,
           "from": now() + RelativeDateTime(days=-7,weekday=(Monday,0)),
           "to": now() + RelativeDateTime(days=-7, weekday=(Sunday,0))}


def usage(exitcode=0, message=None):
    """Gives user info on how to use the program and its options."""

    if message is not None:
        print "\n%s" % message
    
    print """\nUsage: %s [options]

    --help           Prints this message.
    --affiliations   Break down totals by affiliation also.
    --from           Start date for events to be processed (inclusive).
                     Default value is Monday of last week.
    --to             End-date for events to be processed (inclusive).
                     Default value is Sunday of last week.

    Using the defaults will give you a report without affiliation
    info, spanning all of last week.

    'from' and 'to' must be given in standard ISO format, i.e. YYYY-MM-DD.

    """ % sys.argv[0]
    
    sys.exit(exitcode)


def main():
    """Main processing 'hub' of program.
    
    Decides which areas to generate, then generates them sequentially,
    dumping collected and relevant info to STDOUT along the way.

    """
    logger.info("Statistics for Cerebrum activities - processing started")
    logger.debug("Time period: from: '%s'; to: '%s' (inclusive)" %
                 (options['from'].date, options['to'].date))

    print ""
    print ("Statistics covering the period from %s to %s (inclusive)" %
           (options['from'].date, options['to'].date))

    if cereconf.STATISTICS_EXPLANATION_TEMPLATE is not None:
        print ""
        try:
            f = file(cereconf.STATISTICS_EXPLANATION_TEMPLATE)
            for line in f.readlines():
                print line,
        except IOError:
            logger.warning("Unable to find explanatory file: '%s'"
                           % cereconf.STATISTICS_EXPLANATION_TEMPLATE)
    else:
        logger.debug("No explanation file defined in cereconf")

    # List of event types that will be looked into. If you wish to add
    # to this list, you'll need to also make new subclass(es) of
    # EventProcessor.
    event_types = [
        "Person creation",
        "Account creation",
        "Group creation",
        ]

    # Iterate over all event types, retrieve info and generate output
    # based on it.
    for current_type in event_types:
        logger.info("Looking at '%s'" % current_type)
        
        processor = EventProcessor.get_processor(current_type)
        processor.process_events(start_date=options['from'],
                                 end_date=options['to'])

        if options['affiliations']:
            processor.calculate_count_by_affiliation()
            
        processor.print_report(options['affiliations'])

    print ""  # For a nice newline at the end of the report
    

if __name__ == '__main__':
    logger.info("Statistics for Cerebrum activities")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "haf:t:",
                                   ["help", "affiliations", "from=", "to="])
    except getopt.GetoptError:
        # print help information and exit
        usage(1)

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            
        elif opt in ('-f', '--from',):
            logger.debug("Will process events since %s" % val)
            try:
                options['from'] =  ISO.ParseDate(val)
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

    main()

    logger.info("Statistics for Cerebrum activities - done")

# arch-tag: 8aa29596-b8c1-11da-872b-80bcc4277318
