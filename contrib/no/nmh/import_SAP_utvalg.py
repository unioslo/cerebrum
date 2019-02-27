#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""This script imports the data about 'utvalg' for persons from DFØ-SSØ.

NMH has their own behaviour for treating 'utvagl', which is why this is not
implemented into L{contrib/no/hia/import_SAP_person.py}.

The import of persons from SAP must already have been processed, as the person
has to exist for the 'utvalg' to be stored.

Note that the file could contain more than one 'utvalg' per person. In such
cases, the elements are joined and comma separated before being stored, as we
should only have one such element.

"""

### TODO: need to change behaviour to support more than one fagmiljo per person.
# Comma separated?

import sys
import io
import getopt
import re
from mx.DateTime import now

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia.mod_sap_utils import make_utvalg_iterator

logger = Factory.get_logger("cronjob")
const = Factory.get("Constants")()
db = Factory.get("Database")()
db.cl_init(change_program='import_SAP')
co = Factory.get("Constants")(db)
pe = Factory.get('Person')(db)

def usage(exitcode=0):
    print __doc__
    print """
    Usage: import_SAP_utvalg.py --utv-file UTVALGFILE

    -u --utv-file       The SAP person utvalg file to import from. The file is
                        in CSV format and is normally called feide_perutv.txt.

    -d --dryrun         Do not commit changes.

    -h --help           Show this and quit.

    """
    sys.exit(exitcode)

def populate_fagmiljo(person_id, fagmiljo):
    """Add a given fagmiljo string to the given person."""
    logger.debug("Populating fagmiljo for person_id=%s", person_id)
    pe.clear()
    pe.find(person_id)
    pe.populate_trait(code=co.trait_fagmiljo, date=now(), strval=fagmiljo)
    pe.write_db()

def process_utvalg(filename, use_fok):
    """Scan file and perform all the necessary imports.

    Each line in filename contains SAP information about one utvalg for a given
    person.

    """
    logger.info('Start importing utvalg from file: %s', filename)
    sapid2pe = dict((r['external_id'], r['entity_id']) for r in
                    pe.search_external_ids(source_system=co.system_sap,
                                           id_type=co.externalid_sap_ansattnr,
                                           fetchall=False))
    # Fagmiljø already stored in Cerebrum:
    pe2fag_cb = dict((r['entity_id'], r['strval']) for r in
                  pe.list_traits(co.trait_fagmiljo))
    # Caching all fagmiljø from SAP:
    sapid2fag_sap = dict()

    with io.open(filename, 'r', encoding='latin1') as f:
        for u in make_utvalg_iterator(f, use_fok, logger):
            if not u.valid():
                logger.info("Ignoring invalid utvalg for sap_id=%s: %s",
                            u.sap_ansattnr, u.sap_fagmiljo)
                # TODO: remove some data?
                continue
            if u.expired():
                logger.info("Ignoring expired utvalg for sap_id=%s: %s",
                            u.sap_ansattnr, u.sap_fagmiljo)
                # TODO: remove some data?
                continue
            sapid2fag_sap.setdefault(u.sap_ansattnr, []).append(u.sap_fagmiljo)

    logger.debug("Found %d valid employees with 'utvalg'", len(sapid2fag_sap))

    # Update Cerebrum
    for sap_id, fag in sapid2fag_sap.iteritems():
        # Comma separate in case of more than one element from the file.
        # TODO: only unique elements? Remove those who are identical?
        fag = ','.join(fag)

        if sap_id not in sapid2pe:
            logger.info("Ignoring utvalg %s, unknown employee sap_id=%s",
                        fag, sap_id)
            continue
        e_id = sapid2pe[sap_id]
        if fag != pe2fag_cb.get(e_id):
            logger.info("Populating fagmiljo for sap_id=%s: %s",
                        sap_id, fag)
            populate_fagmiljo(e_id, fag)

    # Remove traits for persons that are no longer included in the file
    for sap_id, e_id in sapid2pe.iteritems():
        if not sap_id in sapid2fag_sap and e_id in pe2fag_cb:
            logger.info('Removing old utvalg from person %s', e_id)
            pe.clear()
            pe.find(e_id)
            pe.delete_trait(code=co.trait_fagmiljo)
            pe.write_db()

def main():
    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "u:d",
                                      ["utv-file=",
                                       "dryrun",])
    except getopt.GetoptError, e:
        print e
        usage(1)

    input_name = None
    dryrun = False
    use_fok = True
    for option, value in options:
        if option in ("-u", "--utv-file"):
            input_name = value
        elif option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-h", "--help"):
            usage()
        else:
            print "Unknown argument: %s" % option
            usage(1)

    if input_name is None:
        print "No SAP file specified"
        usage(1)

    process_utvalg(input_name, use_fok)

    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")

if __name__ == "__main__":
    main()
