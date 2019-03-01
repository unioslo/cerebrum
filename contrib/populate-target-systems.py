#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2013-2015 University of Oslo, Norway
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
Utility for purging and/or populating the event_to_target table
"""
import getopt
import sys

import cereconf

import eventconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.event import EventToTargetUtils

logger = Factory.get_logger("console")
database = Factory.get("Database")()
ettu = EventToTargetUtils.EventToTargetUtils(database)


def purge_systems(sync_type):
    for target in eventconf.CONFIG[sync_type]['event_channels']:
        try:
            ettu.delete(target_system=target)
        except Exception as e:
            error_msg = ('Purge failed for target={target}: '
                         '{error}'.format(
                             target=target,
                             error=e))
            sys.stderr.write(error_msg + '\n')
            logger.error(error_msg)
            sys.exit(1)
        logger.info('Removing all event-bindings related to %s' % target)


def populate_systems(sync_type):
    purge_systems(sync_type)
    for event in eventconf.CONFIG[sync_type]['event_types']:
        for target in eventconf.CONFIG[sync_type]['event_channels']:
            try:
                ettu.populate(target, event)
            except Exception as e:
                error_msg = ('Populate failed for {event} → {target}: '
                             '{error}'.format(
                                 event=event,
                                 target=target,
                                 error=e))
                sys.stderr.write(error_msg + '\n')
                logger.error(error_msg)
                sys.exit(1)
            logger.info('Inserting %s → %s' % (event, target))


# TODO: Better descriptions of the various options
def usage(exitcode):
    """Help text for the commandline options."""
    print("\nPopulate them target systems\n")
    print(__doc__)
    print("Options:\n")
    print(" -d or --dryrun\t\tPerform a dry run\n")
    print(" -t or --type\t\tType\n")
    print(" --purge")
    sys.exit(exitcode)


def main():
    options, junk = getopt.getopt(sys.argv[1:],
                                  "t:pdh",
                                  ("type=",
                                   "purge",
                                   "dryrun",
                                   "help"))

    dryrun = False
    sync_type = None
    purge = False

    for option, value in options:
        if option in ("-t", "--type"):
            sync_type = value
        elif option in ('-p', '--purge'):
            purge = True
        elif option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-h", "--help"):
            usage(1)

    if purge:
        purge_systems(sync_type)

    populate_systems(sync_type)

    if dryrun:
        database.rollback()
        logger.debug("Rolled back all changes")
    else:
        database.commit()
        logger.debug("Committed all changes")


if __name__ == "__main__":
    main()
