#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2013 University of Oslo, Norway
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

"""TODO
"""
import getopt
import sys

import cerebrum_path
import cereconf

import eventconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.event import EventToTargetUtils

logger = Factory.get_logger("console")
database = Factory.get("Database")()
ettu = EventToTargetUtils.EventToTargetUtils(database)


def purge_systems(type):
    for target in eventconf.CONFIG[type]['event_channels']:
        # TODO: This should be tried, and excepted?
        ettu.delete(target_system=target)
        logger.info('Removing all event-bindings related to %s' % target)

def populate_systems(type):
    for event in eventconf.CONFIG[type]['event_types']:
        for target in eventconf.CONFIG[type]['event_channels']:
            # TODO: This should be tried, and excepted?
            ettu.populate(target, event)
            logger.info('Inserting %s → %s' % (event, target))

# TODO: Better descriptions of the various options
def usage(exitcode):
    """Help text for the commandline options."""
    print
    print("Populate them target systems")
    print
    print __doc__
    print("Options:")
    print
    print(" -t or --type\t\tType")
    print(" -d or --dryrun\t\t\tPerform a dry run")
    print
    sys.exit(exitcode)


def main():

    options, junk = getopt.getopt(sys.argv[1:],
                                  "t:pdh",
                                  ("type=",
                                   "purge",
                                   "dryrun",
                                   "help"))

    dryrun = False
    type = None
    purge = False

    for option, value in options:
        if option in ("-t", "--type"):
            type = value
        elif option in ('-p', '--purge'):
            purge = True
        elif option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-h", "--help"):
            usage(1)

    if purge:
        purge_systems(type)

    populate_systems(type)
    
    if dryrun:
        database.rollback()
        logger.debug("Rolled back all changes")
    else:
        database.commit()
        logger.debug("Committed all changes")


if __name__ == "__main__":
    main()
