#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
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
Cerebrum is considerer authoritative source system in respect to the mail
addresses and primary user names of the persons with registrations in LT.

This script is very similar in nature to update_FS_mailadr.

"""

import getopt
import sys

import cerebrum_path
import cereconf

from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_LT import LT





def usage():
    message = """
This script synchronizes email and uname information in LT with Cerebrum.

--help, -h		display this message
--email, -e		synchronize email
--uname, -u		synchronize uname
--dryrun, -d		run everything, but do not commit results to LT
"""
    logger.info(message)
# end usage



def synchronize_attribute(cerebrum_lookup,
                          lt_lookup,
                          lt_update,
                          lt_delete,
                          db):
    """
    Synchronize an attribute from Cerebrum to LT
    """

    logger.debug("Synchronizing with functions:\n"
                 "cerebrum lookup: %s\n"
                 "LT lookup: %s\n"
                 "LT update: %s\n"
                 "LT delete: %s",
                 cerebrum_lookup.__name__, lt_lookup.__name__,
                 lt_update.__name__, lt_delete.__name__)

    const = Factory.get("Constants")(db)

    logger.debug("Fetching information from Cerebrum")
    fnr2attribute = cerebrum_lookup(const.externalid_fodselsnr)
    logger.debug("Done fetching information from Cerebrum")

    # Commit/rollback every COMMIT_LIMIT processed rows, to reduce the
    # number of rows locked by this job
    commit_limit = 100
    count = 0
    for db_row in lt_lookup():
        fnr = "%02d%02d%02d%05d" % (db_row.fodtdag, db_row.fodtmnd,
                                    db_row.fodtar, db_row.personnr)
        lt_attribute = db_row.kommnrverdi
        
        # This FNR exists in Cerebrum
        if fnr2attribute.has_key(fnr):
            # ... but Cerebrum's value is different from LT's
            if fnr2attribute[fnr] != lt_attribute:
                logger.debug("Updating for %s in LT: %s -> %s",
                             fnr, lt_attribute, fnr2attribute[fnr])
                lt_update(fnr, fnr2attribute[fnr])
            # fi
        # This FNR does NOT exist in Cerebrum
        else:
            # ... and it should be deleted
            if lt_attribute is not None:
                logger.debug("Deleting %s's attribute %s in LT",
                             fnr, lt_attribute)
                lt_delete(fnr, lt_attribute)
            # fi
        # fi
    # od

    logger.debug("Done synchronizing email information")
# end synchronize_attribute
        


def main():

    global logger
    logger = Factory.get_logger("cronjob")
    logger.info("Starting LT sync")

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "deuh",
                                      ["help",
                                       "email",
                                       "uname",
                                       "dryrun",])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    global dryrun
    dryrun = False
    email = False
    uname = False

    for option, value in options:
        if option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)
        elif option in ("-e", "--email"):
            logger.debug("Running sync for email")
            email = True
        elif option in ("-u", "--uname"):
            logger.debug("Running sync for uname")
            uname = True
        # fi
    # od

    lt = LT(Database.connect(user="ureg2000", service = "LTPROD.uio.no",
                             DB_driver = "DCOracle2"))
    db = Factory.get("Database")()
    person = Factory.get("Person")(db)

    if email:
        synchronize_attribute(person.getdict_external_id2mailaddr,
                              lt.GetAllPersonsUregEmail,
                              lt.UpdatePriMailAddr,
                              lt.DeletePriMailAddr,
                              db)
    # fi

    if uname:
        synchronize_attribute(person.getdict_external_id2primary_account,
                              lt.GetAllPersonsUregUser,
                              lt.UpdatePriUser,
                              lt.DeletePriUser,
                              db)
    # fi

    if dryrun:
        lt.db.rollback()
        logger.info("Rolled back all changes in LT")
    else:
        lt.db.commit()
        logger.info("Committed all changes to LT")
    # fi
# end main    


    
    

if __name__ == "__main__":
    main()
# fi
