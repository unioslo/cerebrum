#! /usr/bin/env python2.2
# -*- coding: iso8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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

This file is a part of the Cerebrum framework. At the University of Oslo 
Cerebrum is considerer authoritative source system in respect to the
mail addresses of the persons with an affiliation to any of the 
organizational units at the University of Oslo.

As specified by the system owners for FS at the University of Oslo
(representened by SSA, Central student administration) each student 
at the University og Oslo has to have a working, official email address 
registered in FS (more specifically in the table FS.PERSON, the field 
EMAILADRESSE). Any other email addresses (privat email accounts) may be
registered in the field EMAILADRESSE_PRIVAT. 

Addresses of all the persons registered in FS are fetched via the
method GetAllPersonsEmail() as defined in 
/cerebrum/Cerebrum/modules/no/uio/access_FS.py. Currently registered 
primary address is then compared to the default mailadress for the 
primary account the person posesses. If there is a difference between 
these two addresses then FS is updated.

Problems: the addresses fetched from Cerebrum do not take the 
account_type nor the source system into consideration. This means that 
the default address fetched for a person is the primary address of 
that person primary account, not the persons primary student account. 
Something should probably be done about this. There is also a number of 
users in the Cerebrum database registered with faulty affiliations. 
This causes a number of persons to be registered with the addresses
uname@ulrik.uio.no

"""

import sys
import getopt
import cerebrum_path
from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_FS import FS

def main():
    db_user = db_service = None
    verbose = dryrun = 0
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dv",
                                   ["dryrun", "verbose", "db-user=",
                                    "db-service="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o, val in opts:
        if o in ('-v', '--verbose'):
            verbose += 1
        elif o in ('-d', '--dryrun'):
            dryrun = 1
        elif o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val

    db = Database.connect(user=db_user, service=db_service,
                          DB_driver='Oracle')
    fs = FS(db)
    db = Factory.get('Database')()
    acc = Factory.get('Account')(db)
    person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)

    fnr2primary = {}
    fnr2primary = person.getdict_external_id2mailaddr(const.externalid_fodselsnr)

    print "Start processing addresses."
    for row in fs.GetAllPersonsEmail():
	fnr = "%06d%05d" % (int(row['fodselsdato']), int(row['personnr']))
	if fnr2primary.has_key(fnr):
	    if fnr2primary[fnr] != row['emailadresse']:
		if verbose:
		    print "Updating address for %s, writing %s." % (fnr, fnr2primary[fnr])
		if not dryrun: 
		    fs.WriteMailAddr(row['fodselsdato'], row['personnr'], fnr2primary[fnr])
		    fs.db.commit()
	    else:
		# address registered in FS does not exist in Cerebrum anymore
		if row['emailadresse'] is not None:
		    if verbose:
			print "Deleting address for %s." % fnr
			fs.WriteMailAddr(row['fodselsdato'], row['personnr'],None)
			fs.db.commit() 

    print "Done processing addresses."

if __name__ == '__main__':
    main()










