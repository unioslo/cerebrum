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
assigns affiliations to people, based on their employments records from SAP.

Please not that this script is guessing when it comes to populating account
types based on affiliations. It is a crude first approximation until
baardj/HiA can specify the task better.
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

FIELDS_IN_ROW_PERSON = 36
FIELDS_IN_ROW_EMPLOYMENT = 9





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



def _internal_process(stream, ou, person, const, **keys):
    """
    An help function for dealing affiliations.

    Keyword arguments are:

    fields_in_row      -- the number of columns per line in STREAM.
    orgeh_index        -- the column number (0 indexed) of a column containing
                          ORGEH part of SAP OU id.
    fo_kode_index      -- Similar to orgeh_index, except it's for GSBER part.
    person_id_index    -- Similar to orgeh_index, except it's for person id
    affiliation_status -- Person affiliation status for affiliation 'ansatt'.

    All keyword arguments are required.
    """

    for row in stream:
        fields = sap_row_to_tuple(row)

        assert len(fields) == keys["fields_in_row"], \
               "Aiee! Wrong number of fields: %d != %d" % (len(fields),
                                                           keys["fields_in_row"])

        if not locate_ou(ou, fields[keys["orgeh_index"]],
                         fields[keys["fo_kode_index"]], const):
            continue
        # fi

        if not locate_person(person, fields[keys["person_id_index"]], const):
            continue
        # fi

        # At this point, we have an ou and a person and we can create an
        # affiliation.
        affiliation_status = keys["affiliation_status"](fields)
        if affiliation_status is None:
            continue
        # fi
        
        person.add_affiliation(ou.entity_id,
                               const.affiliation_ansatt,
                               const.system_sap, 
                               affiliation_status)
        person.write_db()
        logger.debug("Added affiliation %s (status %s) to person %s",
                     const.affiliation_ansatt,
                     keys["affiliation_status"](fields),
                     person.entity_id)
    # od
# end 



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



def process_affiliations(db, person_file, employment_file):
    """
    Scan PERSON and EMPLOYMENT files and assign respective affiliations to
    their owners:

    -> PERSON => affiliation_ansatt, affiliation_status_ansatt_primaer
    -> EMPLOYMENT => affiliation_ansatt,
                     affiliation_status_ansatt_{tekadm, vitenskaplig}
    """

    ou = Factory.get("OU")(db)
    person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)

    try:
        stream = open(person_file, "r")
    except IOError:
        logger.warn("Cannot open file '%s'", person_file)
    else:
        _internal_process(stream, ou, person, const,
                          fields_in_row = FIELDS_IN_ROW_PERSON,
                          orgeh_index = 11,
                          fo_kode_index = 25,
                          person_id_index = 0,
                          affiliation_status =
                            lambda x: const.affiliation_status_ansatt_primaer)
        stream.close()
    # yrt

    try:
        stream = open(employment_file, "r")
    except IOError:
        logger.warn("Cannot open file '%s'", employment_file)
    else:
        _internal_process(stream, ou, person, const,
                          fields_in_row = FIELDS_IN_ROW_EMPLOYMENT,
                          orgeh_index = 1,
                          fo_kode_index = 4,
                          person_id_index = 0,
                          affiliation_status =
                            # 4th field (index 3) contains SAP.STELL, which can
                            # be used to determine the affiliation status
                            lambda x: get_affiliation_status(x, 3, const))
        stream.close()
    # yrt
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
    """

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
