#!/usr/bin/env python
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
imports SAP information about people's roles (utvalg) into Cerebrum.

Actually, there are two concepts here -- 'utvalg' and 'rolle i utvalg'
(sorry, no good translation into English is possible :)).

NB! This script assumes that every employee and every OU exported from SAP
has already been registered in Cerebrum.
"""

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia.mod_sap_utils import sap_row_to_tuple
from Cerebrum.modules.no.hia.mod_sap_codes import SAPUtvalgsKode

import sys
import getopt
import string

FIELDS_IN_ROW = 7





def locate_person(person, sap_id, const):
    """
    Locate a person owning sap_id external id.
    """

    try:
        person.clear()
        person.find_by_external_id(const.externalid_sap_ansattnr,
                                   sap_id,
                                   const.system_sap)
    except Errors.NotFoundError:
        logger.debug("Cannot locate person owning SAP id «%s»", sap_id)
        return False
    else:
        return True
    # yrt
# end locate_person



def populate_utvalg(person, ou, fields, const):
    """
    Populate PERSON with role (utvalg/rolle) information from FIELDS.

    Return True if the import was successful and False otherwise
    """
        
    (sap_id, orgeh, fo_kode,
     utvalg, start_date, end_date, rolle) = fields

    if not locate_person(person, sap_id, const):
        logger.warn("Aiee! Cannot locate person with SAP id «%s»",
                    sap_id)
        return False
    # fi

    # FIXME: We should perhaps not trust the dump blindly, and check that
    # «orgeh-fo_kode» is tied to the same OU as the OU of this person's
    # primary employment (hovedtilsetting).
    #
    # The rules are such that each role is tied to a person and an
    # OU. However, the role-OU tie is implicit and the OU is derived from
    # the OU in the person's primary employment (hovedtilsetting). Each
    # person with a role *must* have a primary employment (hovedtilsetting).
    #
    # For now, we will simply ignore «orgeh-fo_kode»

    #
    # Convert the codes between external/internal representation
    try:
        utvalg = int(SAPUtvalgsKode(utvalg))
    except Errors.NotFoundError:
        logger.warn("Aiee! Cerebrum has no information about "
                    "utvalg = «%s»", utvalg)
        return False
    # yrt

    person.populate_rolle(utvalg, start_date, end_date, rolle)
    
    person.write_db()

    return True
# end populate_utvalg



def process_utvalg(filename, db):
    """
    Read all entries from FILENAME and insert information into Cerebrum.
    """

    stream = open(filename, "r")

    person = Factory.get("Person")(db)
    ou = Factory.get("OU")(db)
    const = Factory.get("Constants")(db)

    # Debug accounting
    total = 0; success = 0

    for entry in stream:
        fields = sap_row_to_tuple(entry)
        total += 1

        if len(fields) != FIELDS_IN_ROW:
            logger.debug("Strange line: |%s|", entry)
            continue
        # fi

        if not populate_utvalg(person, ou, fields, const):
            logger.warn("Skipping utvalg record %s", entry.strip())
            continue
        # fi

        success += 1
    # od

    logger.debug("Total %d records, %d successful updates", total, success)
# end process_utvalg
        


def main():
    """
    Entry point for this script.
    """ 
        
    global logger
    logger = Factory.get_logger("cronjob")

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
    db.cl_init(change_program='import_SAP')

    process_utvalg(input_name, db)

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

# arch-tag: f1afcda1-8800-470b-843d-fb79aaa2e8f7
