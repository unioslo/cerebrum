#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

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
This file is a HiA-specific extension of Cerebrum. It contains code which
generates an export 'back' from Cerebrum to SAP. There is one entry per
employee. Each entry contains four fields. They are (in order):

PERNR	CHAR8	SAP id
TLFINT	CHAR30	Internal phone number 
TLFMOD	CHAR30	Work cellular phone number
EMAIL	CHAR60	Work e-mail
"""

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia.mod_sap_utils import tuple_to_sap_row
from Cerebrum.Utils import AtomicFileWriter

import sys
import getopt
import string





def locate_person(person, person_id):
    """
    Locate a person owning sap_id external id.
    """

    try:
        person.clear()
        person.find(person_id)
    except Errors.NotFoundError:
        logger.debug("Cannot locate person person id «%s»", person_id)
        return False
    else:
        return True
    # yrt
# end locate_person



def get_contact(person, type, const):
    """
    Return a string with contact information TYPE for person.entity_id
    """

    # list_contact_info returns the results sorted by preference
    result = person.list_contact_info(person.entity_id,
                                      const.system_sap, type)
    if result:
        return str(result[0].contact_value)
    else:
        return ""
    # fi
# end get_contact



def get_email(person, account):
    """
    Return a string with primary e-mail address for person.person_id
    """

    # Hmm... did we not write this somewhere earlier?
    accounts = account.get_account_types(owner_id = person.entity_id)
    if not accounts:
        return ""
    # fi

    # This cannot fail
    account.find(accounts[0].account_id)

    try:
        mail = account.get_primary_mailaddress()
        return mail
    except Errors.NotFoundError:
        return ""
    # yrt
# end get_email



def process_employees(filename, db):
    """
    Read all entries from FILENAME and insert information into Cerebrum.
    """

    stream = AtomicFileWriter(filename, "w")

    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)
    account = Factory.get("Account")(db)

    total = 0; failed = 0

    for db_row in person.list_external_ids(const.system_sap,
                                           const.externalid_sap_ansattnr):

        if not locate_person(person, db_row.person_id):
            logger.error("Aiee! list_external_ids returned person id %s,"
                         "but person.find() failed",
                         db_row.person_id)
            failed += 1
            continue
        # fi

        sap_id = str(db_row.person_id)
        phone = get_contact(person, const.contact_phone, const)
        cellphone = get_contact(person, const.contact_phone_cellular, const)
        email = get_email(person, account)
            
        stream.write(tuple_to_sap_row((sap_id, phone, cellphone, email)))
        stream.write("\n")
        total += 1
    # od

    stream.close()
    logger.debug("Total %d record(s) exported; %d record(s) failed",
                 total, failed)
# end process_employees
        


def main():
    """
    Entry point for this script.
    """ 
        
    global logger
    logger = Factory.get_logger("console")

    options, rest = getopt.getopt(sys.argv[1:],
                                  "s:d",
                                  ["sap-file=",
                                   "dryrun",])
    input_name = None
    dryrun = False
    
    for option, value in options:
        if option in ("-s", "--sap-file"):
            input_name = value
        elif option in ("-d", "--dryrun"):
            dryrun = True
        # fi
    # od

    db = Factory.get("Database")()

    process_employees(input_name, db)

    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")
    # fi
# end main





if __name__ == "__main__":
    main()
# fi
