#! /usr/bin/env python2.2
# -*- coding: iso8859-1 -*-
#
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
This file is an UiO-specific extension of Cerebrum.

It updates external id information in Cerebrum. Specifically, people have a
tendency to change their external ids from time to time (e.g. no_ssn
(Norwegian 11-digit fnr)). This script scans through all input files and
updates the external ids in Cerebrum subject to these rules:

- old id (attribute 'old') does not exist in Cerebrum. This situation means
  that no record of prior external id exists in Cerebrum and thus no action
  is necessary.

- old id exists in Cerebrum, but new id (attribute 'new') does not. This
  situation means that a person is registered in Cerebrum under the old
  external id and must be updated. This update can be done automatically.

- Both old and new id exist in Cerebrum. This situation means that although
  there should have been only one person, somehow there are two person
  entities carrying each its own external id. This probably means that these
  two people should be merged into one. However, these updates are best left
  for humans to deal with.

A suitable message is generated for each case.

Each input file is an XML document formatted according to:

<!ELEMENT data (external_id*)>
<!ATTLIST data source_system CDATA #REQUIRED>
<!ATTLIST external_id kind CDATA #REQUIRED
                      old CDATA #REQUIRED
                      new CDATA #REQUIRED
                      date CDATA #REQUIRED>

The 'date' attribute is formatted thus 'YYYY-MM-DD HH:MM:SS'.
"""

import sys
import getopt
import xml.sax

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory





class ExternalIDParser(xml.sax.ContentHandler):
    """
    This class parses the file containing external_id changes data from LT.
    """

    def __init__(self, filename):
        self.current = None
        self.source_system = None
        self.data = list()

        xml.sax.parse(filename, self)
    # end __init__

    

    def startElement(self, name, attrs):
        attrs = dict([ (key.encode("iso8859-1"), value.encode("iso8859-1"))
                       for (key, value) in attrs.items() ])
        
        if name == "data":
            self.source_system = attrs.get("source_system")
        elif name == "external_id":
            self.current = attrs
        else:
            logger.warn("WARNING: unknown element: %s" % name)
        # fi
    # end startElement

    

    def endElement(self, name):
        if name == "external_id":
            self.data.append(self.current)
        # fi
    # end endElement



    def getSourceSystem(self):
        return self.source_system
    # end getSourceSystem


    def __iter__(self):
        return iter(self.data)
    # end __iter__
# end ExternalIDParser



def get_id_type(kind, const):
    """
    Convert KIND to internal code value
    """

    try:
        return int(const.PersonExternalId(kind))
    except Errors.NotFoundError:
        logger.warn("Cannot locate id type '%s'", kind)
        return None
    # yrt
# end get_id_type



def process_file(filename, db, const, person_old, person_new):
    """
    Scan the FILENAME and update Cerebrum with changes therein.
    """

    logger.info("Processing inputfile '%s'", filename)

    parser = ExternalIDParser(filename)
    try:
        source_system = parser.getSourceSystem()
        source_system = int(const.AuthoritativeSystem(source_system))
        source_system_name = str(const.AuthoritativeSystem(source_system))
    except Errors.NotFoundError:
        logger.warn("Failed to locate authoritative system '%s'", source_system)
        return
    # yrt

    logger.info("Source system is '%d' (%s)", source_system, source_system_name)
    
    for element in parser:
        old, new = element["old"], element["new"]
        prefix = "%s %s" % (source_system_name, element["date"])

        if old == new:
            logger.info("%s: %s (old) == %s (new). No changes in the db.",
                        prefix, old, new)
            continue
        # fi

        id_type = get_id_type(element["type"], const)
        if id_type is None:
            continue
        # fi

        try:
            person_old.clear()
            person_old.find_by_external_id(id_type, old, source_system)
        except Errors.NotFoundError:
            logger.info("%s: '%s' (old) does not exist in Cerebrum. "
                        "No changes in the db.", prefix, old)
            continue
        # yrt

        try:
            person_new.clear()
            person_new.find_by_external_id(id_type, new, source_system)
            logger.warn("%s: Both '%s/%s' (old) and '%s/%s' (new) exist "
                        " in Cerebrum. Manual intervention required. "
                        "No changes in the db.",
                        prefix, old, person_old.entity_id,
                        new, person_new.entity_id)
        except Errors.NotFoundError:
            logger.info("%s: '%s' (new) does not exist in Cerebrum, "
                        "but '%s/%s' (old) does. db updated.",
                        prefix, new, old, str(person_old.entity_id))
            person_old.affect_external_id(source_system, id_type)
            person_old.populate_external_id(source_system, id_type, new)
            person_old.write_db()
        # yrt
    # od
# end process_file



def main():
    """
    Start method for this script. 
    """

    global logger
    logger = Factory.get_logger("cronjob")
    logger.info("Generating external id updates")
    
    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "d",
                                      ["dryrun",])
    except getopt.GetoptError:
        logger.exception("Unknown option")
        sys.exit(1)
    # yrt

    dryrun = False
    
    for option, value in options:
        if option in ("-d", "--dryrun"):
            dryrun = True
        # fi
    # od

    db = Factory.get("Database")()
    db.cl_init(change_program="fnr_update")
    const = Factory.get("Constants")(db)
    person_old = Factory.get("Person")(db)
    person_new = Factory.get("Person")(db)

    for filename in rest:
        process_file(filename, db, const, person_old, person_new)
    # od

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
