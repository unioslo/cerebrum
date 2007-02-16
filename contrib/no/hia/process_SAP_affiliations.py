#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2007 University of Oslo, Norway
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
assigns and deletes affiliations/aff. statuses for people based on their
employment records in SAP (feide_persti)

The rules for assigning affiliations are thus:

* Each valid[1] entry in feide_persti results in exactly one
  affiliation_ansatt. The aff. status for this affiliation is calculated based
  on the employment code (lønnstittelkode) from that entry.
* Each affiliation in Cerebrum must have a corresponding entry in the file.

There are roughly two different ways of synchronising all the affiliations:

#. Drop all affiliation_ansatt (this should be the only script assigning them)
   in Cerebrum and re-populate them from data file.
#. Cache the affiliation_ansatt in the db, compare it to file, remove the
   affs in the cache but not in the file, add the affs in the file, but not in
   cache.

The problem with the first approach is that 1) there is no telling what the
various mixin classes would do on delete 2) we'd flood the change_log with
bogus updates (remove A, add A) 3) the db would probably not appreciate such a
usage pattern.
"""

import sys
import getopt
from mx.DateTime import strptime, now

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia.mod_sap_utils import sap_row_to_tuple
from Cerebrum.modules.no.Constants import SAPForretningsOmradeKode
from Cerebrum.modules.no.Constants import SAPLonnsTittelKode

from Cerebrum.modules.no import fodselsnr
from Cerebrum.extlib.sets import Set as set





cerebrum_db = Factory.get("Database")()
cerebrum_db.cl_init("import_SAP")
cerebrum_ou = Factory.get("OU")(cerebrum_db)
constants = Factory.get("Constants")(cerebrum_db)
logger = Factory.get_logger("cronjob")



def sap_employment2aff_status(lonnstittelkode):
    "Map a SAP employment code (lønnstittelkode) to VIT/ØVR aff. status."
    
    try:
        category = SAPLonnsTittelKode(lonnstittelkode).get_kategori()
    except Errors.NotFoundError:
        logger.warn("No SAP.STELL/lønnstittelkode <%s> found in Cerebrum",
                    lonnstittelkode)
        return None

    return {"ØVR": constants.affiliation_status_ansatt_tekadm,
            "VIT": constants.affiliation_status_ansatt_vitenskapelig}[category]
# end sap_employment2aff_status



def sap_ou_number2ou_id(fo_kode, sap_ou_number):
    """Return an ou_id corresponding to the SAP pair (fo_kode, nr)."""

    try:
        fo_kode = int(SAPForretningsOmradeKode(fo_kode))
    except Errors.NotFoundError:
        logger.warn("Forretningsområdekode <%s> is unknown in Cerebrum",
                    fo_kode)
        return None

    try:
        cerebrum_ou.clear()
        cerebrum_ou.find_by_SAP_id(sap_ou_number, fo_kode)
    except Errors.NotFoundError:
        logger.warn("Cannot locate OU with SAP-id <%s-%s>",
                    fo_kode, sap_ou_number)
        return None

    return int(cerebrum_ou.entity_id)
# end sap_ou_number2ou_id
    
    
    
def cache_db_affiliations(person):
    """Return a cache with all affilliation_ansatt.

    The cache itself is a mapping person_id -> person-mapping, where
    person-mapping is a mapping ou_id -> status. I.e. with each person_id we
    associate all affiliation_ansatt that the person has indexed by ou_id.
    """

    cache = dict()
    for row in person.list_affiliations(source_system=constants.system_sap,
                                      affiliation=constants.affiliation_ansatt):
        p_id, ou_id, status = [int(row[x]) for x in
                               ("person_id", "ou_id", "status")]
        cache.setdefault(p_id, dict())[ou_id] = status

    return cache
# end cache_db_affiliations



def remove_affiliations(cache):
    "Remove all affiliations in cache from Cerebrum."

    # cache is mapping person-id => mapping ou-id => status. All these
    # mappings are all for affiliation_ansatt.
    person = Factory.get("Person")(cerebrum_db)
    logger.debug("Removing affiliations for %d people", len(cache))

    for person_id in cache:
        try:
            person.clear()
            person.find(person_id)
        except Errors.NotFoundError:
            logger.warn("person_id %s is in cache, but not in Cerebrum",
                        person_id)
            continue

        # person is here, now we delete all the affiliation_ansatt
        # affiliations.
        for ou_id in cache[person_id]:
            person.delete_affiliation(ou_id,
                                      constants.affiliation_ansatt,
                                      constants.system_sap)
            logger.debug("Removed affiliation_ansatt/ou_id=%s for %s",
                         ou_id, person_id)
# end remove_affiliations



def process_affiliations(employment_file):
    """Parse employment_file and determine all affiliations.

    There are roughly 3 distinct parts:

    #. Cache all the affiliations in Cerebrum
    #. Scan the file and compare the file data with the cache. When there is a
       match, remove the entry from the cache.
    #. Remove from Cerebrum whatever is left in the cache (once we are done
       with the file, the cache contains those entries that were in Cerebrum 
    """

    FIELDS_PER_ROW = 9

    person = Factory.get("Person")(cerebrum_db)

    # first we cache all existing affiliations. It's a mapping person-id =>
    # mapping ou-id => status. Why no affiliation?  Because we deal with
    # affiliation_ansatt *only*.
    db_aff_cache = cache_db_affiliations(person)

    #
    # for each line in file decide what to do with affiliations
    for row in file(employment_file, "r"):
        tmp = sap_row_to_tuple(row)
        assert len(tmp) == FIELDS_PER_ROW, "Error in input: %s" % row

        fo_kode = tmp[4]
        sap_ansattnr = tmp[0]
        sap_ou_number = tmp[1]
        sap_lonnstittelkode = tmp[3]
        date_start = strptime(tmp[5], "%Y%m%d")
        date_end = strptime(tmp[6], "%Y%m%d")

        #
        # Records associated with this fo_kode are invalid by design.
        if (fo_kode and
            SAPForretningsOmradeKode(fo_kode) ==
            constants.sap_eksterne_tilfeldige):
            logger.debug("Ignored external person: «%s»", sap_ansattnr)
            continue 

        # Can we find the OU in Cerebrum?
        ou_id = sap_ou_number2ou_id(fo_kode, sap_ou_number)
        if ou_id is None:
            logger.warn("Cannot map SAP OU %s-%s to Cerebrum ou_id",
                        fo_kode, sap_ou_number)
            continue

        # Can we find the person in Cerebrum?
        try:
            person.clear()
            person.find_by_external_id(constants.externalid_sap_ansattnr,
                                       sap_ansattnr, constants.system_sap)
            person_id = int(person.entity_id)
        except Erorrs.NotFoundError:
            logger.warn("Cannot map SAP ansattnr %s to cerebrum person_id",
                        sap_ansattnr)
            continue

        #
        # Is the entry in the valid timeframe?
        if not (date_start <= now() <= date_end):
            logger.debug("Row %s has wrong timeframe (start: %s, end: %s)",
                         row, date_start, date_end)
            continue

        # Decide on the affiliation status (VIT/ØVR)
        affiliation_status = sap_employment2aff_status(sap_lonnstittelkode)
        if affiliation_status is None:
            logger.warn("Cannot decide on affiliation status for %s", row)
            continue

        # 
        # Ok, now we have everything we need to register/adjusted affiliations
        # case 1: the affiliation did not exist => make a new affiliation
        if (person_id not in db_aff_cache or
            ou_id not in db_aff_cache[person_id]):
            person.add_affiliation(ou_id,
                                   constants.affiliation_ansatt,
                                   constants.system_sap,
                                   affiliation_status)
            logger.debug("New affiliation %s/%s for (p_id: %s; sap_nr: %s)",
                         constants.affiliation_ansatt, affiliation_status,
                         person_id, sap_ansattnr)
        # case 2: the affiliation did exist => update aff.status and fix the
        # cache
        else:
            cached_status = db_aff_cache[person_id][ou_id]
            # Update cache info (we'll need this to delete obsolete
            # affiliations from Cerebrum). Remember that if aff.status is the
            # only thing changing, then we should not delete the "old"
            # aff.status entry. Thus, regardless of the aff.status, we must
            # clear the cache.
            del db_aff_cache[person_id][ou_id]
            if not db_aff_cache[person_id]:
                del db_aff_cache[person_id]

            # The affiliation is there, but the status is different => update
            if cached_status != int(affiliation_status):
                # add_affiliation performs aff.status updates as well
                person.add_affiliation(ou_id, constants.affiliation_ansatt,
                                       constants.system_sap, affiliation_status)
                logger.debug("Updating affiliation status %s => %s for "
                             "(p_id: %s; sap_nr: %s)",
                             cached_status, affiliation_status,
                             person_id, sap_ansattnr)

    # We are done with fetching updates from file.
    # All the affiliations left in cache exist in Cerebrum, but NOT in the
    # datafile. Ergo, delete them!
    remove_affiliations(db_aff_cache)
# end process_affiliations



def main():
    options, rest = getopt.getopt(sys.argv[1:],
                                  "e:dp:",
                                  ("employment-file=", "dryrun"))
    employment_file = None
    dryrun = False
    for option, value in options:
        if option in ("-e", "--employment_file"):
            employment_file = value
        elif option in ("-d", "--dryrun"):
            dryrun = True

    if employment_file:
        process_affiliations(employment_file)

    if dryrun:
        cerebrum_db.rollback()
        logger.info("All changes rolled back")
    else:
        db.commit()
        logger.info("All changes committed")
# end main

            
            


if __name__ == "__main__":
    main()

