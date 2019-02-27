#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004-2018 University of Oslo, Norway
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


"""Populate Cerebrum with SAP OU ids.

This file contains code to import SSØ SAP OU ids from FS (the authoritative
system for OU structure). Typically SSØ SAP use their own OU ids in all data
files, and since FS is authoritative, we need to remap the
ids. fs.sted.stedkode_konv exists precisely for this purpose.

This file scans an XML file generated from FS and populates entity_external_id
for the corresponding OUs.
"""

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import database
from Cerebrum import Errors
from Cerebrum.modules.xmlutils.system2parser import system2parser

import getopt
import sys





def process_OUs(db, parser):
    ou = Factory.get("OU")(db)
    const = Factory.get("Constants")(db)

    total = 0
    success = 0
    no_translation = 0
    erroneous = 0
    for total, elem in enumerate(parser.iter_ou()):
        sko = elem.get_id(elem.NO_SKO)
        if sko is None:
            logger.error("OU %s has no sko", elem.iterids())
            erroneous += 1
            continue
        faknr, instituttnr, gruppenr = sko
        
        try:
            ou.clear()
            ou.find_stedkode(faknr, instituttnr, gruppenr,
                             cereconf.DEFAULT_INSTITUSJONSNR)
        except Errors.NotFoundError:
            logger.warn("  cerebrum id: n/a for (%s, %s, %s)",
                        faknr, instituttnr, gruppenr)
            erroneous += 1
            continue

        # Not every OU has SAP ids. Those that do not, cannot be mapped to SAP
        # IDs.
        stedkode_konv = elem.get_id(elem.NO_SAP_ID)
        if not stedkode_konv:
            no_translation += 1
            continue
        #
        # Several situations are possible now:
        #
        # 1) stedkode_konv is an external id belonging to ou.entity_id -> OK
        # 2) stedkode_konv is an external id belonging to another entity_id
        #    -> FAIL (ideally, this CAN NOT happen)
        # 3) stedkode_konv does not exist in cerebrum -> OK
        try:
            ou2 = Factory.get("OU")(db)
            ou2.find_by_external_id(const.externalid_sap_ou,
                                    stedkode_konv)
            if ou2.entity_id != ou.entity_id:
                # case #2
                logger.error("SAP OU id %s points to several OUs: "
                             "id=%s (in the db) and id=%s (via sko on file). "
                             "This is probably a failed registration and it "
                             "must be corrected manually (some ninja-sql may "
                             "be involved).",
                             stedkode_konv, ou2.entity_id, ou.entity_id)
                erroneous += 1
                continue
        except Errors.NotFoundError:
            # case 3
            ou.affect_external_id(const.system_sap, const.externalid_sap_ou)
            ou.populate_external_id(const.system_sap,
                                    const.externalid_sap_ou,
                                    stedkode_konv)
            ou.write_db()
            if dryrun:
                db.rollback()
                logger.debug("Rolled back all changes")
            else:
                db.commit()
                logger.debug("Committed all changes")

        # simple fallthru try-except would be case #1; also a successful run
        success += 1
        logger.debug("[%10d] <=> [%13s] <=> [%8s]",
                     ou.entity_id, stedkode_konv,
                     "%02d-%02d-%02d" %
                     (ou.fakultet, ou.institutt, ou.avdeling))

    logger.debug("Total: %d OUs (%s successful, %s missing, %s erroneous)",
                 total+1, success, no_translation, erroneous)
# end process_OUs



def main():
    global dryrun
    global logger
    logger = Factory.get_logger("cronjob")

    options, rest = getopt.getopt(sys.argv[1:],
                                  "do:",
                                  ["dryrun", "ou-file="])
    dryrun = False
    filename = None
    for option, value in options:
        if option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-o", "--ou-file",):
            source_system, filename = value.split(":", 1)

    if not filename:
        logger.error("Missing OU input file")
        sys.exit(1)

    db = Factory.get("Database")()
    db.cl_init(change_program="import_SAP")
    
    parser = system2parser(source_system)
    process_OUs(db, parser(filename, logger))
# end main





if __name__ == "__main__":
    main()
