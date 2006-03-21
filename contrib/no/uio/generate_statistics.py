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

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError

"""
This file is a UiO-specific extension of Cerebrum.

It provides statistics about specific activities within Cerebrum.

"""

__version__ = "$Revision$"
# $Source$


# THIS IS JUST WAAAAY TOO HARD-CODED....
affiliations_by_code = {129: "ANSATT",
                        130: "MANUELL",
                        131: "STUDENT",
                        132: "TILKNYTTET",
                        133: "UPERSONLIG"}
# Most to least significant affiliation. Determines what entitites
# with multiple affiliations will be counted under.
affiliations_by_priority = [129, 131, 132, 130, 133]
no_affiliation = "(INGEN)"


db = Factory.get('Database')()
constants = Factory.get('Constants')(db)
logger = Factory.get_logger()

# Default choices for script options
options = {"affiliations": False,
           "from": now() + RelativeDateTime(days=-7,weekday=(Monday,0)),
           "to": now() + RelativeDateTime(days=-7, weekday=(Sunday,0))}


class EventNotDefinedError(Exception):
    
    """
    For use by EventProcessor. Raised when a requested event-type has
    not been defined yet.
    
    """
    def __init__(self, message):
        "Sets up exception."
        if message is None:
            self.message = "Event type handling not defined for this event type"
        else:
            self._message = message
        
    def __str__(self):
        "Returns exception's message."
        return self._message
    


class EventProcessor(object):
    
    """
    Abstract baseclass for processing a given area of event-based
    statistics.

    Subclasses should override at least
    'calculate_count_by_affiliation' to yield desired results. Other
    functions can be overridden as necessary for that particular
    event.

    """

    def __init__(self):
        """
        Initializes processor; should be called with
        'EventProcessor.__init__(self)' by subclasses before any
        subclass-specific initialization takes place.

        """
        self._log_events = 0
        self._total_count = 0
        self._count_by_affiliation = {}
        self._entity_ids = []
        self._description = ""
        

    def get_processor(event_type):
        """
        Static factory method. Returns an event processor based on
        'event_type'.

        """
        if event_type == "Person creation":
            return CreatePersonProcessor()
        elif event_type == "Account creation":
            return CreateAccountProcessor()
        elif event_type == "Group creation":
            return CreateGroupProcessor()
        else:
            raise EventNotDefinedError("Handling not defined for '%s'" % event_type)
    get_processor = staticmethod(get_processor)


    def process_events(self, start_date=0, end_date=0):
        """
        Extracts desired events from database and places entity IDs
        into 'self._entity_ids', where they later can be counted and
        extracted for further purposes.

        """
        event_rows = db.get_log_events_date(sdate=start_date, edate=end_date, type=self._log_events)

        for row in event_rows:
            self._entity_ids.append(row["subject_entity"])

        logger.info("Number of events for '%s' is %i" % (self._description, self._get_total()))



    def calculate_count_by_affiliation(self):
        """
        Calculates counts by affiliation for the particular
        event-type. Must be implemented by subclasses.

        """
        raise NotImplementedError("This method should be implemented by subclasses")


    def _get_total(self):
        """Returns the total number of events for the event-type."""
        return len(self._entity_ids)
    

    def print_report(self, print_affiliations=False):
        """
        Prints a report for the data collected by this particular
        event processor.
        
        """
        print ""
        print ("Event:        '%s'" % self._description),
        print " " * (20 - len(self._description)),
        print (" total count: %s" % self._get_total())

        if print_affiliations:
            self._print_affiliation_info()

        print ""


    def _print_affiliation_info(self):
        """
        Prints affiliation info for this particular prosessor. Can be
        overridden by subclasses, e.g. if there has been collected no
        affiliation-info by them.
        
        """
        print ""
        # The no-affiliation line should be printed last, and will
        # therefore be specially treated. This will also handle if
        # there is no "no-affiliation".
        no_affiliation_line = "" 
        for affiliation, count  in self._count_by_affiliation.iteritems():
            outline = (" " * 18) + affiliation + (" " * (34 -len(affiliation))) + str(count)
            
            if affiliation == no_affiliation:
                no_affiliation_line = outline + "\n"
            else:
                print outline
        
        print no_affiliation_line,


    def get_most_significant_affiliation(self, affiliations):
        """Determines which of 'affiliations' is the most significant one."""
        for aff in affiliations_by_priority:
            if aff in affiliations:
                return affiliations_by_code[aff]


    def _add_to_affiliation(self, affiliation):
        """Adds an event to the count for a given affiliation."""
        if self._count_by_affiliation.has_key(affiliation):
            self._count_by_affiliation[affiliation] += 1
        else:
            self._count_by_affiliation[affiliation] = 1

    def _process_affiliation_rows(self, affiliation_rows):
        """
        Processes any affiliation rows found for an entity and adds
        to the count for the affiliations as determined.
        
        """
        designated_affiliation = no_affiliation
        if affiliation_rows:
            affiliations = []
            for row in affiliation_rows:
                logger.debug("Found affiliation: '%s'" % row['affiliation']);
                affiliations.append(row['affiliation'])

            designated_affiliation = self.get_most_significant_affiliation(affiliations)

        self._add_to_affiliation(designated_affiliation)   
        


class CreatePersonProcessor(EventProcessor):

    """
    Handles 'create person'-events.

    """

    def __init__(self):
        EventProcessor.__init__(self)
        self._log_events = int(constants.person_create)
        self._description = "Create Person"
        
    def calculate_count_by_affiliation(self):
        "Implementations of superclass' abstract function"
        person = Factory.get('Person')(db)
        for current_entity in self._entity_ids:
            logger.debug("Checking affiliations for person entity '%s'", current_entity)

            person.clear()
            affiliation_rows = []
            try:
                person.find(current_entity)
                affiliation_rows = person.list_affiliations(person_id=current_entity)
            except NotFoundError:
                # Unable to look up person (deleted?) Let rows be empty, so affiliation will be none
                logger.debug("Unable to find person with entity-id '%s'" % current_entity)
            self._process_affiliation_rows(affiliation_rows)



class CreateAccountProcessor(EventProcessor):
    
    """
    Handles 'create account'-events.

    """

    def __init__(self):
        EventProcessor.__init__(self)
        self._log_events = int(constants.account_create)
        self._description = "Create Account"
        
    def calculate_count_by_affiliation(self):
        "Implementations of superclass' abstract function"
        for current_entity in self._entity_ids:
            logger.debug("Checking affiliations for person entity '%s'", current_entity)

            account = Factory.get('Account')(db)
            account.clear()
            account.find(current_entity)
            affiliation_rows = account.list_accounts_by_type(account_id=current_entity)

            self._process_affiliation_rows(affiliation_rows)

     

class CreateGroupProcessor(EventProcessor):
    
    """
    Handles 'create group'-events. Groups are a bit special compared
    to other events, since they do not have any associations with
    affiliations.
    
    """

    def __init__(self):
        EventProcessor.__init__(self)
        self._log_events = int(constants.group_create)
        self._description = "Create Group"
        
    def calculate_count_by_affiliation(self):
        "Groups do not have affiliations"
        pass

    def _print_affiliation_info(self):
        "Groups do not have affiliations"
        print ""
        print "        (no affiliation info)"



def usage(exitcode=0):
    """Gives user info on how to use the program and its options."""
    
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
    """
    Main processing 'hub' of program.
    Decides which areas to generate, then generates them sequentially

    """
    logger.info("Statistics for Cerebrum activities - processing started")

    logger.debug("Time period: from: '%s'; to: '%s' (inclusive)" %
                 (options['from'].date, options['to'].date))

    print ""
    print ("Statistics covering the period from %s to %s (inclusive)" %
           (options['from'].date, options['to'].date))
    
    event_types = [
        "Person creation",
        "Account creation",
        "Group creation",
        ]
    
    for current_type in event_types:
        logger.debug("Looking at '%s'" % current_type)
        
        processor = EventProcessor.get_processor(current_type)
        processor.process_events(start_date=options['from'], end_date=options['to'])

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
                print "\nERROR: Incorrect 'from'-format"
                usage(2)
                
        elif opt in ('-t', '--to',):
            logger.debug("Will process events till %s" % val)
            try:
                options['to'] = ISO.ParseDate(val)
            except ValueError:
                print "\nERROR: Incorrect 'to'-format"
                usage(2)
                
        elif opt in ('-a', '--affiliations',):
            logger.debug("Will process and display info about affiliations")
            options['affiliations'] = True

    main()

    logger.info("Statistics for Cerebrum activities - done")

# arch-tag: 8aa29596-b8c1-11da-872b-80bcc4277318
