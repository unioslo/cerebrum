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
assigns affiliations/affiliation stati to people, based on their employments
records from SAP.

Furthermore, we have to consider the SAP data file containing person
information. If a person's end date is in the past, we remove all
ANSATT affiliations pertaining to that person. 
"""

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia.mod_sap_utils import sap_row_to_tuple
from Cerebrum.modules.no.hia.mod_sap_codes import SAPForretningsOmradeKode
from Cerebrum.modules.no import fodselsnr

import sys
import getopt
import string
import time

FIELDS_IN_ROW_PERSON = 36
FIELDS_IN_ROW_EMPLOYMENT = 9
NOW = time.strftime("%Y%m%d")





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



def locate_name(person, const):
    """
    Try to find a suitable SAP name for the person.
    """

    name = "n/a"
    for variant in (const.name_full, const.name_last):
        try:
            name = person.get_name(const.system_sap, variant)
        except Errors.NotFoundError:
            pass
        # yrt
    # od

    return name
# end locate_name



def remove_affiliations(expired_employees, person, const):
    """
    Go through all records in EXPIRED_EMPLOYEES and 
    """

    for sap_person_id in expired_employees:
        # delete all ANSATT affiliations.
        # FIXME: HOW??

        if not locate_person(person, sap_person_id, const):
            logger.warn("Person with SAP id %s expired, but it does not " +
                        "exist in Cerebrum", sap_person_id)
            continue
        # fi

        name = locate_name(person, const)
        fnr = person.get_external_id(const.system_sap,
                                     const.externalid_fodselsnr)
        if fnr:
            fnr = fnr[0]["external_id"]
        else:
            fnr = "n/a"
        # fi

        # Now we fetch all affiliations for this person and explicitely
        # delete all affiliation_ansatt entries.
        for row in person.get_affiliations():
            db_aff = row["affiliation"]
            db_deleted = row["deleted_date"]

            # It's not an ANSATT affiliation
            if int(db_aff) != int(const.affiliation_ansatt):
                continue
            # fi

            # It has already been deleted
            if db_deleted:
                continue
            # fi

            try:
                person.delete_affiliation(row["ou_id"], row["affiliation"],
                                          row["source_system"])
            except:
                logger.error("Deleting ANSATT affiliation for ... failed")
            else:

                logger.info("Removed ANSATT affiliation (status %s) for "
                            "person (sap id: %s, fnr: %s, name: %s) : " +
                            "end date: %s",
                            row["status"], sap_person_id, fnr, name,
                            expired_employees[sap_person_id])
            # yrt
        # od

        person.write_db()
    # od
# end remove_affiliations
    


def adjust_affiliations(stream, ou, person, const, expired):
    """
    Adjust affiliations for all employees.

    STREAM  -- SAP data file with employment information
    EXPIRED -- dictionary mapping SAP person ids to termination dates.
    """

    orgeh_index = 1
    fo_kode_index = 4
    person_id_index = 0
    aff_index = 3

    for row in stream:
        fields = sap_row_to_tuple(row)

        assert len(fields) == FIELDS_IN_ROW_EMPLOYMENT, \
               ("Aiee! Wrong number of fields: %d != %d (row %s)" %
                (len(fields), FIELDS_IN_ROW_EMPLOYMENT), row)

        if not locate_ou(ou, fields[orgeh_index],
                         fields[fo_kode_index], const):
            continue
        # fi

        if not locate_person(person, fields[person_id_index], const):
            continue
        # fi

        # At this point, we have an ou and a person and we can create an
        # affiliation.
        affiliation_status = get_affiliation_status(fields, aff_index, const)
        if affiliation_status is None:
            continue
        # fi
        
        if (fields[person_id_index] not in expired or
            expired[fields[person_id_index]] >= NOW):
            person.add_affiliation(ou.entity_id,
                                   const.affiliation_ansatt,
                                   const.system_sap, 
                                   affiliation_status)
            logger.debug("Added affiliation %s (status %s) to person %s",
                         const.affiliation_ansatt,
                         affiliation_status,
                         person.entity_id)
        # fi

        person.write_db()
    # od

    # Process expired employees
    remove_affiliations(expired, person, const)
# end adjust_affiliations



def get_affiliation_status(fields, index, const):
    """
    Determine affiliation status, based on SAP.STELL/Lonnstittel (It's
    either 'tekadm' og 'vitenskaplig').
    """

    from Cerebrum.modules.no.hia.mod_sap_codes import SAPLonnsTittelKode

    try:
        category = SAPLonnsTittelKode(fields[index]).get_kategori()
    except Errors.NotFoundError:
        logger.warn("Aiee! No SAP.STELL/Lonnstittel '%s' in Cerebrum!",
                    fields[index])
        return None
    # yrt
    
    return { "ØVR" : const.affiliation_status_ansatt_tekadm,
             "VIT" : const.affiliation_status_ansatt_vitenskapelig }[category]
# end get_affiliation_status



def build_expired_employees(person_file, person, const):
    """
    Scan PERSON_FILE and build a dictionary mapping SAP person id's to
    termination dates (formatted as a string, YYYYMMDD) for people whose
    termination date is in the past.

    Returns the dictionary on success and None on failure. 
    """
    
    person_id_index = 0
    date_index = 32
    fo_kode = 25

    result = dict()

    try:
        stream = open(person_file, "r")
    except IOError:
        logger.warn("Cannot open file '%s'", person_file)
        return None
    # yrt

    for row in stream:
        fields = sap_row_to_tuple(row)

        assert len(fields) == FIELDS_IN_ROW_PERSON, \
               ("Aiee! Wrong number of fields: %d != %d (row: %s)" %
                (len(fields), FIELDS_IN_ROW_PERSON, row))

        person_id, expire_date = fields[person_id_index], fields[date_index]

        if (fields[fo_kode] and 
            int(SAPForretningsOmradeKode(fields[fo_kode])) ==
            int(const.sap_eksterne_tilfeldige)):
            logger.debug("Ignored external person: «%s»", person_id)
            continue 
        # fi

        if expire_date < NOW:
            result[ person_id ] = expire_date

            name = "n/a"
            if locate_person(person, person_id, const):
                name = locate_name(person, const)
            # fi
            
            logger.info("Person %s (sap id: %s) has expired: %s < %s (now)",
                        name, person_id, expire_date, NOW)
        # fi
    # od

    stream.close()
    return result
# end build_valid_employees



def process_affiliations(db, person_file, employment_file):
    """
    Scan PERSON and EMPLOYMENT files and adjust respective affiliations of
    their owners:

    -> PERSON => Used to decide when to remove affiliations from people
    -> EMPLOYMENT => affiliation_ansatt,
                     affiliation_status_ansatt_{tekadm, vitenskaplig}

    The idea is to create a mapping of which person records are still valid
    based on their 'expiration date' in PERSON_FILE. Those that are valid
    get affiliations from EMPLOYMENT_FILE. Those that are not, get all their
    SAP affiliations removed.
    """

    ou = Factory.get("OU")(db)
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)

    expire_information = build_expired_employees(person_file, person, const)

    if expire_information is None:
        logger.error("Cannot create employees' SAP end dates. Aborting")
        return
    # fi
    
    try:
        stream = open(employment_file, "r")
    except IOError:
        logger.warn("Cannot open file '%s'", employment_file)
        return
    # yrt

    adjust_affiliations(stream, ou, person, const, expire_information)

    stream.close()
# end process_affiliations



def deal_account_types(db):
    """
    Scan all SAP employees and for each account held by a SAP employee,
    populate account_type with:

    affiliation -+
    ou_id -------+--> from person_affiliation
    person_id ---+

    priority = 10 (this would give a possibility to adjust priorities later).

    The ou_id/affiliation above are selected based on:

    affiliation = affiliation_ansatt,
    status = affiliation_status_ansatt_primaer

    NB! This function is no longer used.
    """

    logger.error( "deal_account_types functionality is no longer available" )
    return

    # NOTREACHED

    person = Factory.get("Person")(db)
    account = Factory.get("Account")(db)
    const = Factory.get("Constants")(db)

    for row in person.list_external_ids(const.system_sap,
                                        const.externalid_sap_ansattnr):
        accounts = account.list_accounts_by_owner_id(row["person_id"])
        if not accounts:
            logger.debug("Person %s has no accounts. Skipped", row["person_id"])
            continue
        # fi

        logger.debug("Person %s has %d account%s",
                     row["person_id"], len(accounts),
                     # C's ?: operator
                     len(accounts) > 1 and "s." or ".")

        # We need an OU. This is the only reason for this lookup
        logger.debug("Looking up affiliations for %s", row["person_id"])

        # For now, we do *NOT* care about the affiliation status. This
        # has to be clarified with HiA. baardj plays the ball.
        primary = person.list_affiliations(
                    person_id = row["person_id"],
                    source_system = const.system_sap,
                    affiliation = const.affiliation_ansatt)

        # There can be at most one (and after process_affiliations has
        # been called there should be at least one)
        if not primary:
            logger.debug("Aiee! Person %s has no ansatt affiliation "
                         "(status: primary)", row["person_id"])
            continue
        else:
            primary = primary[0]
        # fi

        for account_row in accounts:
            account_id = account_row["account_id"]

            account.clear()
            account.find(account_id)

            account.set_account_type(primary["ou_id"],
                                     primary["affiliation"])
            account.write_db()
            logger.debug("Account %s (owner == %s) has new type",
                         account_id, row["person_id"])
        # od
    # od 
# end deal_account_types



def main():
    """
    Entry point for this script.
    """ 
        
    global logger
    logger = Factory.get_logger("console")

    options, rest = getopt.getopt(sys.argv[1:],
                                  "dp:e:a",
                                  ["dryrun",
                                   "person-file=",
                                   "employment-file=",
                                   "account-types",])
    dryrun = False
    person_file = ""
    employment_file = ""
    process_account_types = False
    
    for option, value in options:
        if option in ("-p", "--person-file"):
            person_file = value
        elif option in ("-e", "--employment-file"):
            employment_file = value
        elif option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-a", "--account-types"):
            process_account_types = True
        # fi
    # od

    db = Factory.get("Database")()
    db.cl_init(change_program='import_SAP')

    if person_file or employment_file:
        process_affiliations(db, person_file, employment_file)
    # fi

    if process_account_types:
        deal_account_types(db)
    # fi

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

# arch-tag: ddb1c800-7193-4113-85d4-7618849945c1
