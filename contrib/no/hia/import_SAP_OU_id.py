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
This file is part of Cerebrum. It contains code to import HiA SAP-specific OU
identifiers (ORGEH and GSBER) and map them to the Cerebrum-specific OU
identifier (ou_id). This script is also applicable for Hi�f-data.

There is no deep magic or any sort of validation of this mapping. This script
assumes that

fs.sted.stedkode_konv

column contains the proper SAP id for an OU identified by the FS stedkode in
the same row. The format of stedkode_konv column is:

[ORGEH]-[GSBER]

... where [ORGEH] is an 8-digit code and [GSBER] is a 4-digit
forretningsomr�dekode, which must match one of the values in the
sap_forretningsomrade table in mod_sap.sql.

In order for this script to run successfully, it is required that:

* all necessary OUs have been imported (that is, ou_info is populated)
* all stedkode entries have been imported (that is, stedkode is populated)
"""

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.modules.no.Constants import SAPForretningsOmradeKode

import getopt
import re
import string
import sys




def process_OUs(db, ou_stream):

    ou = Factory.get("OU")(db)

    total = 0; success = 0
    for row in ou_stream:
        total += 1
        try:
            ou.clear()
            ou.find_stedkode(row["faknr"], row["instituttnr"], row["gruppenr"],
                             cereconf.DEFAULT_INSTITUSJONSNR)
        except Errors.NotFoundError:
            logger.warn("  cerebrum id: n/a for (%s, %s, %s)",
                        row["faknr"], row["instituttnr"], row["gruppenr"])
            continue

        # Not every OU has SAP ids. Those that do not, cannot be mapped to SAP
        # IDs.
        if not row["stedkode_konv"]:
            continue

        orgeh, gsber = string.split(row["stedkode_konv"], "-")
        # This forces us to check data for sanity
        # However, try-catch should be unnecessary unless the data source
        # is erroneous.
        try:
            internal_gsber = int(SAPForretningsOmradeKode(gsber))
        except Errors.NotFoundError:
            logger.exception("Aiee! gsber �%s� does not exist in Cerebrum",
                             gsber)
            continue
        
        ou.populate_SAP_id(orgeh, internal_gsber)

        # FIXME: This is a hack for catching up OUs that share a SAP id. It
        # should be impossible, but it happens nonetheless. The exception
        # thrown concerns violation of a unique constraint. The hack below
        # should reduce the noise in the logs (at least until we change the
        # database driver)
        try: 
            ou.write_db()
            # NB! We *must* commit after each write_db()
            if dryrun:
                db.rollback()
                logger.debug("Rolled back all changes")
            else:
                db.commit()
                logger.debug("Committed all changes")

            success += 1
        except:
            # IVR 2007-02-16 FIXME: This is a butt-ugly hack. But there is no
            # other easy way to detect this "impossible" error.
            typ, value, tb = sys.exc_info()
            if (str(value).find("duplicate key violates unique constraint")
                != -1):
                logger.error("Attempt to insert duplicate key �%s-%s�",
                             orgeh, gsber)
            else:
                logger.exception("Failed writing SAP id �%s-%s� to the db",
                                 orgeh, gsber)
        else:
            # IVR 2007-11-12 FIXME: get_SAP_id() will fail, if we ran rollback
            # above.
            logger.debug("[%10d] <=> [%15s] <=> [%12s]",
                         ou.entity_id, ou.get_SAP_id(),
                         "(%d, %d, %d)" % 
                         (ou.fakultet, ou.institutt, ou.avdeling))

    logger.debug("Total: %d OUs", total)
    logger.debug("Successful id translations: %d", success)
# end process_OUs



def ou_id_generator(filename, separator=";"):
    keys = ("faknr", "instituttnr", "gruppenr", "stedkode_konv")

    for line in file(filename, "r"):
        line = line.strip()
        # skip empty lines
        if not line:
            continue
        # skip commented lines
        if line[0] == "#":
            continue

        fields = re.split(separator, line)
        result = dict()
        for index, key in enumerate(keys):
            result[key] = fields[index]
        yield result
# end ou_id_generator



def main():
    "Entry point for this script." 
	
    global logger
    logger = Factory.get_logger("cronjob")

    options, rest = getopt.getopt(sys.argv[1:],
                                  "do:",
                                  ["dryrun","ou-file="])

    global dryrun
    dryrun = False
    ou_stream = None
    for option, value in options:
        if option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-o", "--ou-file",):
            ou_stream = ou_id_generator(value)

    if ou_stream is None:
        fs = Factory.get("FS")()
        ou_stream = fs.info.list_ou()

    db = Factory.get("Database")()
    db.cl_init(change_program="import_SAP")

    process_OUs(db, ou_stream)
# end main





if __name__ == "__main__":
    main()
