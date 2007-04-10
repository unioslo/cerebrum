#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
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

p = Factory.get('Person')(db)

auto = sets.Set()
manual = sets.Set()

def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'v:d:h',['verbose','dryrun','help'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    verbose = False
    

    for opt,val in opts:
        if opt in ('-d','--dryrun'):
            dryrun = True
        if opt in ('-v','--verbose'):
            verbose = True
        if opt in ('-h','--help'):
            usage()

    for person,ou,aff,source,status,dd,cd in p.list_affiliations():
        if source == co.system_manual:
            manual.add((person, ou, aff))
        else:
            auto.add((person, ou, aff))

    count=0
    # If you have 2 affiliations of same type and ou and one of them
    # is added manually, it will be marked for deletion
    for person,ou,aff in manual.intersection(auto):
        try:
            # Use delete_date?
            p.clear()
            p.find(person)
            print "Deleting affiliation %s on %s of type manual for entity %s" % (aff,ou,person)
            p.delete_affiliation(ou, aff, co.system_manual)
            p.write_db()
            count+=1
        except Errors.NotFoundError:
            pass
            
    if dryrun:
        print "%d manual affiliations would have been removed" % count
        db.rollback()
    else:
        print "%d manual affiliations removed from database" % count
        db.commit()

def usage():
    print """Usage: %s
    -d | --dry-run : if you only want to show which would have been marked for deletion - use this option.
    -v | --verbose : print out the affiliation on ou for person that would/will be marked for deletion.
    -h | --help    : duh
    """ % sys.argv[0]
    sys.exit(1)


if __name__ == '__main__':
    main()
