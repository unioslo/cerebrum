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



def attempt_commit(lt):
    """
    Command-line controlled committing to LT.

    This is a convenience function.
    """
    
    if dryrun:
        lt.db.rollback()
    else:
        lt.db.commit()
    # fi
# end attempt_commit



def synchronize_attribute(cerebrum_lookup,
                          lt_lookup,
                          lt_update,
                          lt_delete,
                          const, lt):
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

    logger.debug("Fetching information from Cerebrum")
    fnr2attribute = cerebrum_lookup(const.externalid_fodselsnr)
    logger.debug("Done fetching information from Cerebrum")

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

                attempt_commit(lt)
            # fi
        # This FNR does NOT exist in Cerebrum
        else:
            # ... and it should be deleted
            if lt_attribute is not None:
                logger.debug("Deleting %s's attribute %s in LT",
                             fnr, lt_attribute)
                lt_delete(fnr, lt_attribute)

                attempt_commit(lt)
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
    const = Factory.get("Constants")(db)

    if email:
        synchronize_attribute(person.getdict_external_id2mailaddr,
                              lt.GetAllPersonsUregEmail,
                              lt.UpdatePriMailAddr,
                              lt.DeletePriMailAddr,
                              const, lt)
    # fi

    if uname:
        synchronize_attribute(person.getdict_external_id2primary_account,
                              lt.GetAllPersonsUregUser,
                              lt.UpdatePriUser,
                              lt.DeletePriUser,
                              const, lt)
    # fi
# end main    


    
    

if __name__ == "__main__":
    main()
# fi

# arch-tag: 8573c49c-8d23-498e-a45e-f68e94c912f7
