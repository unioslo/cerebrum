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
checks SAP OU dumpfile content against Cerebrum db. Since the OU information
is populated from FS, it might be a good idea to check the SAP content
against FS information for consistency.

For now, the script does not do much more than report the differences.
"""

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia.mod_sap_utils import sap_row_to_tuple
from Cerebrum.modules.no.hia.mod_sap_codes import SAPForretningsOmradeKode

import sys
import getopt
import string

FIELDS_IN_ROW = 7





def process_OUs(filename):
    """
    Go through all entries in FILENAME and check the data against Cerebrum.
    """

    db = Factory.get("Database")()
    ou = Factory.get("OU")(db)

    stream = open(filename, "r")
    for entry in stream:
        fields = sap_row_to_tuple(entry)

        if len(fields) != FIELDS_IN_ROW:
            logger.warn("Strange line in %s: %s",
                        filename, entry)
            continue
        # fi

        # Split them into interesting fields
        orgeh, full_name, _, _, gsber, short_name, _ = fields

        # Look up the OU by SAP id
        try:
            ou.clear()
            # Map SAP gsber to internal Cerebrum id
            gsber_internal = int(SAPForretningsOmradeKode(gsber))
            ou.find_by_SAP_id(orgeh, gsber_internal)
        except Errors.NotFoundError:
            logger.warn("Aiee! No ou_id for (%s, %s)" % (orgeh, gsber))
            continue
        # yrt

        # FIXME: Is is sensible to perform upper case comparison?
        if (ou.name != full_name and
            string.upper(ou.name) != string.upper(full_name)):
            logger.warn("name mismatch: |%s| != |%s| for %s",
                        ou.name, full_name, ou.entity_id)
        # fi

        if (ou.short_name != short_name and
            string.upper(ou.short_name) != string.upper(short_name)):
            logger.warn("short name mismatch: |%s| != |%s| for %s",
                        ou.short_name, short_name, ou.entity_id)
        # fi
    # od 
# end process_OUs



def main():
    """
    Entry point for this script.
    """ 
	
    global logger
    logger = Factory.get_logger("cronjob")

    options, rest = getopt.getopt(sys.argv[1:],
                                  "s:l",
                                  ["sap-file=",
				   "logger-name=",])
    input_name = None
    for option, value in options:
        if option in ("-s", "--sap-file"):
            input_name = value
        # fi
    # od
    
    process_OUs(input_name)
# end main





if __name__ == "__main__":
    main()
# fi
