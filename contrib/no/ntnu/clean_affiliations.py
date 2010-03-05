#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2007 University of Oslo, Norway
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

# Clean out manually registered affiliation if an equivalent affiliation
# has been registered by an authoritative system.


import cerebrum_path
from Cerebrum import Utils
from Cerebrum import Person
from Cerebrum import Errors

import sets
import getopt
import sys

Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='clean_affs')

person = Factory.get('Person')(db)
account = Factory.get('Account')(db)
logger = Factory.get_logger("console")

def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'v:d:h',
                                  ['verbose','dryrun','help','remove_bdb_affs'])
    except getopt.GetoptError:
        usage()

    global dryrun
    global remove_bdb_affs

    dryrun = False
    verbose = False
    remove_bdb_affs = False

    for opt,val in opts:
        if opt in ('-d','--dryrun'):
            dryrun = True
        if opt in ('--remove_bdb_affs'):
            remove_bdb_affs = True
        if opt in ('-h','--help'):
            usage()

    if verbose:
        logger = Factory.get_logger("console")
    else:
        logger = Factory.get_logger("cronjob")
        
    clean_inferior_affiliations()
    clean_deleted_affiliations()


def clean_deleted_affiliations():
    active = set()
    for paff in person.list_affiliations():
        afftup = (paff['person_id'], paff['ou_id'], paff['affiliation'])
        active.add(afftup)

    to_delete = {}
    for at in account.list_accounts_by_type(filter_expired=False):
        afftup = (at['person_id'], at['ou_id'], at['affiliation'])
        if not afftup in active:
            to_delete.setdefault(at['account_id'], []).append(
                (at['ou_id'], at['affiliation']))
    
    count = 0
    acount = 0
    for account_id, ats in to_delete.items():
        account.clear()
        account.find(account_id)
        logger.info("Removing affiliations from %s: %s",
                    account.account_name,
                    ", ".join("%s:%d" % (co.PersonAffiliation(aff), ou_id)
                              for ou_id, aff in ats))
        acount += 1
        for ou_id, aff in ats:
            account.del_account_type(ou_id, aff)
            count += 1

    if dryrun:
        logger.info("%d affiliations would have been removed in %d accounts",
                    count, acount)
        db.rollback()
    else:
        logger.info("%d affiliations removed from %d accounts",
                    count, acount)
        db.commit()


def clean_inferior_affiliations():
    auto = set()
    manual = set()
    bdb = set()

    for paff in person.list_affiliations():
        afftup = (paff['person_id'], paff['ou_id'], paff['affiliation'])
        source = paff['source_system']

        if source == co.system_manual:
            manual.add(afftup)
        elif source == co.system_bdb:
            bdb.add(afftup)
        else:
            auto.add(afftup)

    count=0
    # If you have 2 affiliations of same type and ou and one of them
    # is added manually, it will be marked for deletion
    todelete=[]
    for person_id, ou_id, aff in (manual & (auto | bdb)):
        todelete.append((person_id, ou_id, aff, co.system_manual))
    # Also do the same if an affiliation comes from BDB and also a
    # better source.
    if remove_bdb_affs:
        for person_id, ou_id, aff in (bdb & auto):
            todelete.append((person_id, ou_id, aff, co.system_bdb))

    for person_id, ou_id, aff, source in todelete:
        try:
            person.clear()
            person.find(person_id)
            logger.info("Deleting affiliation %s on %s of type %s for person %s",
                        co.PersonAffiliation(aff), ou_id,
                        co.AuthoritativeSystem(source), person_id)
            person.delete_affiliation(ou_id, aff, source)
            person.write_db()
            count+=1
        except Errors.NotFoundError:
            pass
            
    if dryrun:
        logger.info("%d manual affiliations would have been removed" % count)
        db.rollback()
    else:
        logger.info("%d manual affiliations removed from database" % count)
        db.commit()

def usage():
    print """Usage: %s
    -d | --dry-run : if you only want to show which would have been marked for deletion - use this option.
    -h | --help    : duh
    """ % sys.argv[0]
    sys.exit(1)


if __name__ == '__main__':
    main()
