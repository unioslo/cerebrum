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
import cereconf

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_FS import FS





def synchronize_attribute(cerebrum_lookup, fs_lookup, 
                          fs_update, index, const):
    """
    Synchronize an attribute A (e-mail or primary account) between Cerebrum
    and FS.

    CEREBRUM_LOOKUP is a function yielding a mapping between no_ssn and A
    from Cerebrum.

    FS_LOOKUP is a function yielding a mapping between no_ssn and A from FS.

    FS_UPDATE is a function that update A's value for a given no_ssn in FS.
    """

    logger.debug("Fetching information from Cerebrum")
    fnr2attribute = cerebrum_lookup(const.externalid_fodselsnr)
    logger.debug("Done fetching information from Cerebrum")

    for row in fs_lookup():
	fnr = "%06d%05d" % (int(row['fodselsdato']), int(row['personnr']))
        cere_attribute = fnr2attribute.get(fnr, None)
        fs_attribute = row[index]
        
        # Cerebrum has a record of this fnr
        if fnr in fnr2attribute:
            # We update only when the values differ
            if cere_attribute != fs_attribute:
                logger.debug1("Updating for %s: %s -> %s",
                              fnr, fs_attribute, cere_attribute)

                fs_update(row['fodselsdato'], row['personnr'], cere_attribute)
		attempt_commit()
            # fi

        # Attribute registered in FS does not exist in Cerebrum anymore
	else:

	    if fs_attribute is not None:
                logger.debug1("Deleting address for %s.", fnr)

                # None in FS means "no value"
                fs_update(row['fodselsdato'], row['personnr'], None)
                attempt_commit()
            # fi
        # fi
    # od

    logger.debug("Done updating attributes")
# end 



def usage( exitcode = 0 ):
    print """
Updates all e-mail adresses in FS that come from Cerebrum
Usage: update_FS_mailadr.py [options]
-d | --dryrun	       - Run synchronization, but do *not* update FS
-u | --db-user name    - Connect with given database username
-s | --db-service name - Connect to given database
-e | --email           - Synchronize e-mail information
-a | --account         - Synchronize account information
"""
    sys.exit(exitcode)
# end usage



def main():
    global logger

    logger = Factory.get_logger("cronjob")
    logger.info("Synchronizing FS with Cerebrum")

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "du:s:ea",
                                   ["dryrun",
                                    "db-user=",
                                    "db-service=",
                                    "email",
                                    "account",])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    # yrt

    user = "ureg2000"
    service = "fsprod.uio.no"
    dryrun = False
    email = False
    account = False

    for option, value in opts:
        if option in ('-d', '--dryrun'):
            dryrun = True
        elif option in ('-u', '--db-user',):
            user = value
        elif option in ('-s', '--db-service',):
            service = value
        elif option in ('-e', '--email',):
            email = True
        elif option in ('-a', '--account'):
            account = True
        # fi
    # od

    fs_db = Database.connect(user = user, service = service, DB_driver='DCOracle2')
    fs = FS(fs_db)

    db = Factory.get('Database')()
    person = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)

    def my_commit():
        if dryrun:
            fs.db.rollback()
            logger.info("Rolled back all changes")
        else:
            fs.db.commit()
            logger.info("Commited all changes")
        # fi
    # end my_commit
    global attempt_commit
    attempt_commit = my_commit

    if email:
        synchronize_attribute(person.getdict_external_id2mailaddr,
                              fs.GetAllPersonsEmail,
                              fs.WriteMailAddr,
                              "emailadresse", const)
    # fi

    if account:
        synchronize_attribute(person.getdict_external_id2primary_account,
                              fs.GetAllPersonsUname,
                              fs.WriteUname,
                              "brukernavn", const)
    # fi
# end main





if __name__ == '__main__':
    main()
# fi










