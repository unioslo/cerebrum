#! /usr/bin/env python2.2
# -*- coding: iso8859-1 -*-
#
# Copyright 2004 University of Oslo, Norway
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
This file is an UiO-specific extension of the Cerebrum framework.

Specifically, it ensures that all people that should have spread 'UA@uio'
actually do so.

The rules run like this:

* Every student should have spread 'UA@uio'
* Every employee should have spread 'UA@uio'.
  (NB! *any* employment would do, not necessarily an active one)

However, the student processing job at UiO (studentautomatikken) ensures
that all the *students* get the proper spread. Thus this job deals with all
the rest.

Specifically, the following updates are run:

* Give spread 'UA@uio' to all employees (i.e. persons having an employment
  (tilsetting) record.)
 
"""

import sys
import getopt

import cerebrum_path
import cereconf

import Cerebrum
from Cerebrum.Utils import Factory
from Cerebrum.extlib.sets import Set





def update_employees_spread(db):
    """
    Look through all employees, force the spread for every one having active
    employments (tilsetting).
    """

    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)

    processed_ids = Set()

    for db_row in person.list_tilsetting():
        person_id = int(db_row["person_id"])

        # skip the people that have been processed
        if person_id in processed_ids:
            logger.debug5("%s has already been processed", person_id)
            continue
        # fi

        processed_ids.add(person_id)

        # Ok, we must locate that person's spreads
        try:
            person.clear()
            person.find(person_id)
        except Cerebrum.NotFoundError:
            logger.exception("This is impossible: tilsetting for "
                             " non-existing person_id %s", person_id)
            continue
        # yrt

        # Let's have a look at the spreads:
        spreads = map(lambda x: int(x["spread"]),
                      person.get_spread())
        if int(const.spread_uio_ua) in spreads:
            logger.debug("%s has already spread 'UA@uio'", person.entity_id)
            continue
        # fi

        # person does not have UA@uio spread. Add it
        try:
            person.add_spread(const.spread_uio_ua)
        except:
            logger.exception("add_spread('UA@uio') failed for %s",
                             person.entity_id)
        # yrt
            
        person.write_db()
        logger.debug("%s obtained new spread 'UA@uio'", person.entity_id)
    # od
# end update_employees_spread



def usage():
    '''
    Display option summary
    '''

    options = '''
options: 
-h, --help:        Display this message
-d, --dryrun:      Run everything, but do not commit anything to the database
    '''

    logger.info(options)
# end usage



def main():
    """
    Start method for this script. 
    """
    global logger

    logger = Factory.get_logger("cronjob")
    logger.info("Updating spread 'UA@uio'")

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "hd",
                                      ["help",
                                       "dryrun",])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    dryrun = False
    for option, value in options:
        if option in ("-h", "--help"):
            usage()
            sys.exit(2)
        elif option in ("-d", "--dryrun"):
            dryrun = True
        # fi
    # od

    logger.info("The jobs runs with dryrun = %s", dryrun)

    db = Factory.get("Database")()
    db.cl_init(change_program="update_ua_spread")

    update_employees_spread(db)

    if dryrun:
        db.rollback()
        logger.info("All changes rolled back")
    else:
        db.commit()
        logger.info("All changes committed")
    # fi
# end main





if __name__ == "__main__":
    main()
# fi

# arch-tag: 1576e6d9-e936-4933-be6c-4dbca33dee3a
