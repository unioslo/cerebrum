#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005-2019 University of Oslo, Norway
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
This script removes a given type external_id from a given source
system if the person in question also has the same type of external_id
from one of the systems defined in cereconf.SYSTEM_LOOKUP_ORDER.

The script may be run for removing externalid_fodselsnr from MIGRATE
if a person at the same time has externalid_fodselsnr from e.g. SAP.

The script may be run without commiting results in order to check
changes.

Example:

  python remove_src_extid.py -e externalid_fodselsnr -s system_migrate

"""

import sys
import getopt                   # REMOVE!
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory

def process_person (source_sys, e_id_type):
    other_sys_list = set(cereconf.SYSTEM_LOOKUP_ORDER) - set([source_sys])
    logger.info("Remove %s from %s if person has same external_id from one or more of the systems: %s" % (e_id_type, source_sys, other_sys_list))
    logger.debug("Processing all persons...")
    for p in person.list_persons():
        pid = p['person_id']
        person.clear()
        person.find(pid)
        if not person.get_external_id(source_sys, e_id_type):
            # Person hasn't e_id_type from source_sys. Nothing to delete
            continue
        for tmp in other_sys_list:
            tmp_sys = getattr(co, tmp)
            # If person also has a fnr from one of the
            # source_systems in cereconf.SYSTEM_LOOKUP_ORDER,
            # delete the fnr from source_sys
            if person.get_external_id(tmp_sys, e_id_type):
                person._delete_external_id(source_sys, e_id_type)
                logger.info("Removed %s from %s for person_id |%s|" %
                            (e_id_type, source_sys, pid))
                break
        else:
            logger.debug("Did not find any other external_id for person_id |%s|",
                         person.entity_id)
    logger.debug("Done processing all persons")

def attempt_commit():
    if dryrun:
        db.rollback()
        logger.debug("Rolled back all changes")
    else:
        db.commit()
        logger.debug("Committed all changes")

def usage(exitcode=0):
    print """Usage: [-d] -s  <surce_system> -e <external_id_type>
    Removes all norwegian national id numbers imported from ureg2000
    if an id of same type is imported from LT or FS also

    -d : log changes, do not commit # deprecate this!!
    -c commit changes
    -s <source_system> : source_system to remove fnrs from
    -e <external_id_type> : type of external id
    """
    sys.exit(exitcode)

def main():
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-s', '--source_system',
                        help='source_system to remove fnrs from',
        # dest='days',
        # type=int,
        # default=30,
        # metavar='<days>',
    )
    parser.add_argument(
        '-p', '--pretend', '-d', '--dryrun',
        action='store_true',
        dest='pretend',
        default=True,
        help='Log changes, do not commit (this is the default behaviour)'
    )
    parser.add_argument(
        '-c', '--commit',
        action='store_true',
        dest='pretend',
        default=False,
        help='Commit changes (default: log changes, do not commit)'
    )

    global db, co, person, source_sys, e_id_type, pers
    global dryrun, logger
    logger = Factory.get_logger("console")
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ds:e:',
                                   ['dryrun', 'source-system=', 'external-id='])
    except getopt.GetoptError:
        usage()

    dryrun = False
    source_system = None
    external_id_type = None
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-s', '--source-system'):
            source_system = val
        elif opt in ('-e', '--external-id'):
            external_id_type = val

    db = Factory.get('Database')()
    db.cl_init(change_program='remove_src_fnrs')
    co = Factory.get('Constants')(db)
    person = Factory.get('Person')(db)

    # Get source_system constant
    try:
        source_system = getattr(co, source_system)
    except AttributeError:
        logger.error("No such source system: %s" % source_system)
        usage(1)
    try:
        external_id_type = getattr(co, external_id_type)
    except AttributeError:
        logger.error("No such external_id type: %s" % external_id_type)
        usage(1)

    process_person(source_system, external_id_type)
    attempt_commit()

if __name__ == '__main__':
    main()
