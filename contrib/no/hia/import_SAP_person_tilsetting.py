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
imports SAP employment information into Cerebrum.

NB! This script assumes that every employee and every OU exported from SAP
has already been registered in Cerebrum.

"""

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia.mod_sap_utils import sap_row_to_tuple
from Cerebrum.modules.no.hia.mod_sap_codes import SAPLonnsTittelKode
from Cerebrum.modules.no.hia.mod_sap_codes import SAPStillingsTypeKode
from Cerebrum.modules.no.hia.mod_sap_codes import SAPForretningsOmradeKode

import sys
import getopt
import string

FIELDS_IN_ROW = 9





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



def locate_ou(ou, orgeh, fo_kode, const):
    """
    Locate an OU owning (orgeh, fo_kode) SAP id.
    """

    # Convert the code between internal/external representation
    try:
        fo_kode = int(SAPForretningsOmradeKode(fo_kode))
    except Errors.NotFoundError:
        logger.warn("Forretningsområdekode «%s» not registered in Cerebrum",
                    fo_kode)
        return False
    # yrt
    
    try:
        ou.clear()
        ou.find_by_SAP_id(orgeh, fo_kode)
    except Errors.NotFoundError:
        logger.debug("Cannot locate OU with SAP id «%s-%s»", orgeh, fo_kode)
        return False
    # yrt
    
    return True
# end locate_ou



def populate_tilsetting(person, ou, fields, const):
    """
    Populate PERSON with tilsetting (employment) information from FIELDS.

    Return True if the import was successful and False otherwise
    """

        
    (sap_id, orgeh, funksjonstittel,
     lonnstittel, fo_kode,
     start_date, end_date, stillingstype, percentage) = fields
    
    # External project/people/whatever. They are not supposed to be in
    # Cerebrum.
    if (fo_kode and
        int(SAPForretningsOmradeKode(fo_kode)) ==
          int(const.sap_eksterne_tilfeldige)):
        logger.debug("External employment, ignored")
        return True
    # fi

    if not locate_person(person, sap_id, const):
        logger.warn("Aiee! Cannot locate person with SAP id «%s»",
                    sap_id)
        return False
    # fi

    if not locate_ou(ou, orgeh, fo_kode, const):
        logger.warn("Aiee! Cannot locate OU with SAP id «%s-%s»",
                    orgeh, fo_kode)
        return False
    # fi

    #
    # Convert the codes between external/internal representation
    try:
        lonnstittel = int(SAPLonnsTittelKode(lonnstittel))
        stillingstype = int(SAPStillingsTypeKode(stillingstype))
    except Errors.NotFoundError:
        logger.warn("Aiee! Cerebrum has no information about "
                    "SAP.STELL/lønnskode = «%s»", lonnstittel)
        return False
    # yrt

    # No further checking is possible :(
    funksjonstittel = int(funksjonstittel)
    percentage = float(percentage)

    person.populate_tilsetting(ou.entity_id, lonnstittel, funksjonstittel,
                               stillingstype, start_date, end_date,
                               percentage)
    person.write_db()

    return True
# end populate_tilsetting



def process_tilsettinger(filename, db):
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
            logger.debug("Strange line: «%s»", entry)
            continue
        # fi

        if not populate_tilsetting(person, ou, fields, const):
            logger.warn("Skipping employment record «%s»", entry.strip())
            continue
        # fi

        success += 1
    # od

    logger.debug("Total %d records, %d successful updates", total, success)
# end process_tilsettinger



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

    process_tilsettinger(input_name, db)

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

# arch-tag: 7d0a2875-1ead-4610-a4bb-6cc10616ae90
