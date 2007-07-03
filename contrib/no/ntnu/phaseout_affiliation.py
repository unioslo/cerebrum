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
db.cl_init(change_program='phaseout_aff')

p = Factory.get('Person')(db)

def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'vdh',['verbose','dryrun','help'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    verbose = False
    status = False

    for opt,val in opts:
        if opt in ('-d','--dryrun'):
            dryrun = True
        if opt in ('-s','--status'):
            status = True
        if opt in ('-v','--verbose'):
            verbose = True
        if opt in ('-h','--help'):
            usage()

    if (len(args) < 1):
        usage()
    froml = args[0].split(":")
    try:
        fromaff = co.PersonAffiliation(int(froml[0]))
    except ValueError:
        fromaff = co.PersonAffiliation(froml[0])
    fromstatus = None
    if len(froml) > 1:
        try:
            fromstatus = co.PersonAffStatus(int(froml[1]))
        except ValueError:
            fromstatus = co.PersonAffStatus(fromaff, froml[1])

    toaff = tostatus = tocomment = None
    if len(args) > 1:
        to = args[1].split(":")
        try:
            toaff = co.PersonAffiliation(int(to[0]))
        except ValueError:
            toaff = co.PersonAffiliation(to[0])
        try:
            tostatus = co.PersonAffStatus(int(to[1]))
        except ValueError:
            tostatus = co.PersonAffStatus(fromaff, to[1])
        tocomment = None
        if len(to) > 2:
            tocomment = to[2]
    phaseout_affiliation(int(fromaff), int(fromstatus),
                         int(toaff), int(tostatus), tocomment,
                         dryrun, verbose)


def phaseout_affiliation(fromaff, fromstatus, toaff, tostatus, todesc,
                         dryrun=False, verbose=False):
    count=0
    affs = p.list_affiliations(affiliation=fromaff, status=fromstatus,
                               include_deleted=True)
    for person,ou,aff,source,status,dd,cd in affs:
        assert aff == fromaff
        if fromstatus: assert status == fromstatus
        
        p.clear()
        p.find(person)
        if verbose:
            print "%s affiliation %s on %s for %s source %s" % (
                toaff is not None and "Converting" or "Deleting",
                aff, ou, person, source)
        if fromaff == toaff:
            p.populate_affiliation(source, ou, toaff, tostatus)
        else:
            p.nuke_affiliation(ou, aff, source, status)
            if toaff is not None:
                p.populate_affiliation(source, ou, toaff, tostatus)
        p.write_db()
        count+=1
        
    if dryrun:
        if verbose:
            print "%d affiliations would have been removed" % count
        db.rollback()
    else:
        if verbose:
            print "%d affiliations removed from database" % count
        db.commit()

def usage():
    print """Usage: %s FROM[:FROMSTATUS] [TO:TOSTATUS[:TOCOMMENT]]
    -d | --dry-run : if you only want to show which would have been marked for deletion - use this option.
    -v | --verbose : print out the affiliation on ou for person that would/will be marked for deletion.
    -h | --help    : duh
    """ % sys.argv[0]
    sys.exit(1)


def code(c, cl):
    try:
        return int(c)
    except ValueError:
        return int(cl(c))


if __name__ == '__main__':
    main()
