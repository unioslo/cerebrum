#!/usr/bin/env python
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



def make_key(db_row):
    return "%02d%02d%02d%05d" % (db_row.fodtdag, db_row.fodtmnd,
                                    db_row.fodtar, db_row.personnr)
# end make_key



def synchronize_attribute(cerebrum_lookup,
                          lt_people,
                          lt_lookup,
                          lt_update,
                          lt_delete,
                          lt_insert,
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
    cere2attr = cerebrum_lookup(const.externalid_fodselsnr)
    logger.debug("Done fetching information from Cerebrum")

    logger.debug("Fetching comm information from LT")
    lt2attr = dict()
    for row in lt_lookup():
        fnr = make_key(row)
        lt2attr[fnr] = row.kommnrverdi
    # od
    logger.debug("Done fetching information from LT")

    #
    # Now, for each person in LT (LT_PERSON), check if the attribute value
    # in Cerebrum (cerebrum2attribute) matches the one in LT (lt2attribute).
    # If they mismatch, cerebrum's value takes precendence.
    #
    # Please not that there is a delay between looking up the values in
    # respective databases and checking them for matches. If an update happens
    # within this time period, we might end up with "old" data (... which
    # should be taken care of in the next run of the script).
    # 
    for db_row in lt_people:
        fnr = make_key(db_row)

        # This FNR exists in Cerebrum
        if fnr in cere2attr:
            # ... but does NOT exist in LT
            if fnr not in lt2attr:
                # ... then we *insert* the new value into LT
                logger.debug("Inserting for %s in LT: -> %s",
                             fnr, cere2attr[fnr])
                lt_insert(fnr, cere2attr[fnr])
                attempt_commit(lt)
            # ... and the attribute exists in LT, but is different from
            # Cerebrum
            elif cere2attr[fnr] != lt2attr[fnr]:
                # ... then we *update* the value in LT
                logger.debug("Updating for %s in LT: %s -> %s",
                             fnr, lt2attr[fnr], cere2attr[fnr])
                lt_update(fnr, cere2attr[fnr])
                attempt_commit(lt)
            # fi
        # ... this FNR does NOT exist in Cerebrum
        else:
            # ... and if it exists in LT
            if lt2attr.get(fnr) is not None:
                # ... it should be deleted
                logger.debug("Deleting %s's attribute %s in LT",
                             fnr, lt2attr[fnr])
                lt_delete(fnr, lt2attr[fnr])
                attempt_commit(lt)
            # fi
        # fi
    # od

    logger.debug("Done synchronizing attribute")
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

    logger.debug("Fetching all people from LT")
    lt_people = lt.GetAllPersons()
    logger.debug("done")

    if email:
        synchronize_attribute(person.getdict_external_id2mailaddr,
                              lt_people,
                              lt.GetAllPersonsUregEmail,
                              lt.UpdatePriMailAddr,
                              lt.DeletePriMailAddr,
                              lt.InsertPriMailAddr,
                              const, lt)
    # fi

    if uname:
        synchronize_attribute(person.getdict_external_id2primary_account,
                              lt_people,
                              lt.GetAllPersonsUregUser,
                              lt.UpdatePriUser,
                              lt.DeletePriUser,
                              lt.InsertPriUser,
                              const, lt)
    # fi
# end main    


    
    

if __name__ == "__main__":
    main()
# fi

# arch-tag: 8573c49c-8d23-498e-a45e-f68e94c912f7
