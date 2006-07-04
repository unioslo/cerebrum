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

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError

"""This module provides components for extracting information about
changelog events.

Typically, a processor should subclass 'EventProcessor' and override
any methods necessary to yield desired results. See code for examples
on how to do this.

The module makes use of two cereconf-variables:

* AFFILIATIONS_BY_PRIORITY - which is a list of most to least
  significant affiliation. This is important for those cases where an
  event can be associated with more than one affiliation, in order to
  know which affiliation counts the most.

* NO_AFFILIATION - which is the string that should be used as the name
  for grouping those events that cannot be related to any affiliation.

"""

__version__ = "$Revision$"
# $Source$


db = Factory.get('Database')()
constants = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")


# Most to least significant affiliation. Determines what entitites
# with multiple affiliations will be counted under.
affiliations_by_priority = []
# Need to map to numeric codes, since that's what we'll be getting
# from the database later.
for element in cereconf.AFFILIATIONS_BY_PRIORITY:
    try:
        code = int(constants.PersonAffiliation(element))
        affiliations_by_priority.append(code)
    except NotFoundError:
        logger.warning("Unable to find affiliation code for '%s'. Misspelling?" % element)
        
# Name used for group when no affiliation info can be associated with
# an event that normally has affiliation info.
no_affiliation = cereconf.NO_AFFILIATION



class EventNotDefinedError(Exception):
    
    """For use by EventProcessor.

    Raised when a requested event-type has not been defined yet.
    
    """
    pass



class EventProcessor(object):
    
    """Abstract baseclass for processing a given area of event-based
    statistics.

    Subclasses should override at least
    'calculate_count_by_affiliation' to yield desired results. Other
    functions can be overridden as necessary for that particular
    event.

    """

    def __init__(self):
        """Initializes processor.

        Should be called with 'EventProcessor.__init__(self)' by
        subclasses before any subclass-specific initialization takes
        place.

        """
        self._log_event = 0
        self._total_count = 0
        self._count_by_affiliation = {}
        self._entity_ids = []
        self._description = ""
        

    def get_processor(event_type):
        """Static factory method.

        @param event_type: The type of event we should get a processor for.
        @type event_type: String

        @return: An event processor for 'event_type'-events.

        @raise EventNotDefinedError: If 'event_type' is not defined/incorrect.

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
        """Main 'counting' function.

        Extracts desired events from database and places entity IDs
        into 'self._entity_ids', where they later can be counted and
        extracted for further purposes.

        @param start_date: Earliest date for events to include
        @type start_date: mx.DateTime

        @param end_date: Latest date for events to include
        @type end_date: mx.DateTime

        """
        event_rows = db.get_log_events_date(sdate=start_date, edate=end_date, type=self._log_event)

        for row in event_rows:
            self._entity_ids.append(row["subject_entity"])

        logger.info("Number of events for '%s' is %i" % (self._description, self._get_total()))



    def calculate_count_by_affiliation(self):
        """Calculates counts by affiliation for the particular
        event-type.

        @raise NotImplementedError: Always, since this method should
            be implemented(overridden by subclasses.

        """
        raise NotImplementedError("This method should be implemented by subclasses")


    def _get_total(self):
        """Returns the total number of events for the event-type."""
        return len(self._entity_ids)
    

    def print_report(self, print_affiliations=False):
        """Prints summary of collected info.

        Prints a report for the data collected by this particular
        event processor.
        
        @param print_affiliations: Whether or not affiliation info
            should be printed.
        @type print_affiliations: Boolean

        """
        print ""
        print ("Event:        '%s'" % self._description),
        print " " * (20 - len(self._description)),
        print (" total count: %s" % self._get_total())

        if print_affiliations:
            self._print_affiliation_info()

        print ""


    def _print_affiliation_info(self):
        """Prints affiliation info for this particular prosessor.

        Can be overridden by subclasses, e.g. if there has been
        collected no affiliation-info by them.
        
        """
        print ""
        # The no-affiliation line should be printed last, and will
        # therefore be specially treated. This will also handle if
        # there is no "no-affiliation".
        no_affiliation_line = "" 
        for affiliation, count  in self._count_by_affiliation.iteritems():
            # If 'affiliation' isn't a proper code (as is the case for
            # 'no_affiliation'), then PersonAffiliation will simply
            # use 'affiliation' as its string represnetation, and
            # that's sufficient for our purposes.
            aff_str = str(constants.PersonAffiliation(affiliation))
                
            outline = (" " * 18) + aff_str + (" " * (34 -len(aff_str))) + str(count)
            
            if aff_str.startswith(no_affiliation):
                # "No affiliation" might be specified further in some
                # cases; we want to gather all these groups at the end.
                no_affiliation_line = no_affiliation_line + outline + "\n"
            else:
                print outline
        
        print no_affiliation_line,


    def get_most_significant_affiliation(self, affiliations):
        """Determines which of 'affiliations' is the most significant one.

        @param affiliations: The set of affiliation IDs we wish to
            evaluate.        
        @type affiliations: List

        @return: The most significant affiliation, as defined by cereconf.
        
        """
        for aff in affiliations_by_priority:
            if aff in affiliations:
                return aff

        logger.warning("Unable to find most significant affiliation from " +
                       "list '" + str(affiliations) + "'. cereconf.AFFILIATIONS_BY_PRIORITY " +
                       "is probably undefined or missing some affiliations")
        
        return affiliations[0];


    def _add_to_affiliation(self, affiliation):
        """Adds an event to the count for a given affiliation.

        @param affiliation: The affiliation that should be added to.        
        @type affiliation: int

        """
        if self._count_by_affiliation.has_key(affiliation):
            self._count_by_affiliation[affiliation] += 1
        else:
            self._count_by_affiliation[affiliation] = 1


    def _process_affiliation_rows(self, affiliation_rows):
        """Generalized handling of affiliation data.

        Processes any affiliation rows found for an entity and adds to
        the count for the 'proper' affiliation as determined.

        Some processors might need to handle this differently and
        should therefore override this function.
        
        @param affiliation_rows: The database rows with affiliation
            info for the entity being evaluated.        
        @type affiliation_rows: List of database rows

        """
        designated_affiliation = no_affiliation #  Default till proven otherwise
        if affiliation_rows:
            affiliations = []
            for row in affiliation_rows:
                logger.debug("Found affiliation: '%s'" % row['affiliation']);
                affiliations.append(row['affiliation'])

            designated_affiliation = self.get_most_significant_affiliation(affiliations)

        self._add_to_affiliation(designated_affiliation)   
        


class CreatePersonProcessor(EventProcessor):

    """Handles 'create person'-events."""

    def __init__(self):
        EventProcessor.__init__(self)
        self._log_event = int(constants.person_create)
        self._description = "Create Person"
        
    def calculate_count_by_affiliation(self):
        """Implementations of superclass' abstract function."""
        person = Factory.get('Person')(db)
        for current_entity in self._entity_ids:
            logger.debug("Checking affiliations for person entity '%s'", current_entity)

            person.clear()
            affiliation_rows = []
            try:
                person.find(current_entity)
                affiliation_rows = person.list_affiliations(person_id=current_entity)
            except NotFoundError:
                # Unable to look up person (deleted? merged?) 
                logger.debug("Unable to find person with entity-id '%s'" % current_entity)
                self._add_to_affiliation(no_affiliation + " (deleted since creation)")
                continue

            if affiliation_rows:
                self._process_affiliation_rows(affiliation_rows)
            else:
                # Need to quantify with source, since no affiliation is known.
                event_rows = person.get_external_id()
                source_as_num = event_rows[0]['source_system']
                source = str(constants.AuthoritativeSystem(source_as_num))
            
                logger.debug("Source for entity '%s' determined to be %s " % (current_entity, source))
                self._add_to_affiliation(no_affiliation + " (source: " + source + ")")



class CreateAccountProcessor(EventProcessor):
    
    """Handles 'create account'-events."""

    def __init__(self):
        EventProcessor.__init__(self)
        self._log_event = int(constants.account_create)
        self._description = "Create Account"
        
    def calculate_count_by_affiliation(self):
        """Implementations of superclass' abstract function."""
        for current_entity in self._entity_ids:
            logger.debug("Checking affiliations for person entity '%s'", current_entity)

            account = Factory.get('Account')(db)
            account.clear()
            account.find(current_entity)
            affiliation_rows = account.list_accounts_by_type(account_id=current_entity)

            self._process_affiliation_rows(affiliation_rows)

     

class CreateGroupProcessor(EventProcessor):
    
    """Handles 'create group'-events.

    Groups are a bit special compared to other events, since they do
    not have any associations with affiliations.
    
    """

    def __init__(self):
        EventProcessor.__init__(self)
        self._log_event = int(constants.group_create)
        self._description = "Create Group"
        
    def calculate_count_by_affiliation(self):
        """Groups do not have affiliations."""
        pass

    def _print_affiliation_info(self):
        """Groups do not have affiliations."""
        print ""
        print "        (no affiliation info)"
