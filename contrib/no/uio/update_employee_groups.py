#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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

This file performs group information update for certain people registered in
Cerebrum.

Specifically,

1) for all active employees with at least one 'tilsetting' registered, their
   respective primary account (user) is subscribed to groups 'uio-tils' and
   'uio-ans'.

2) for all people who had received a 'bilagslønn' within the past 180 days,
   subscribe their respective primary account (user) to group
   'uio-ans'. Such people are referred to as 'temporaries' in this script.

LT keeps track of the employment information; Cerebrum keeps track of
groups, accounts and the like. The Norwegian social security number
('fødselsnummer') binds these two together.

This script generates no output. All updates are written back to the
cerebrum database:

<LT db> --------+
                |
                +--> update_employee_groups.py --+
                |                                |
<cerebrum db> --+ <------------------------------+

"""

import sys
import time
import getopt
import string
import traceback

import cerebrum_path
import cereconf

import Cerebrum
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_LT import LT
from Cerebrum.modules.no import fodselsnr

# FIXME: As of python 2.3, this module is part of the standard distribution
if sys.version >= (2, 3):
    import logging
else:
    from Cerebrum.extlib import logging
# fi





# 
# It looks like there is way too much time spent looking up things. The
# output structure suggests that it might be beneficial to cache
# (no_ssn,uname) mappings
#
no_ssn_cache = {}

def cached_value(key):
    """
    Returns a tuple -- the cached value for the KEY and a status telling
    whether this value actually existed in the cache.
    """
    
    value = no_ssn_cache.get(key, None)
    hit = no_ssn_cache.has_key(key)

    return value, hit
# end cached_value

def cache_value(key, value):
    """
    Insert a new pair into the cache.
    """

    # NB! This is potentially very dangerous, as no upper limit is placed on
    # the cache
    no_ssn_cache[key] = value
# end cache_value



def fetch_no_ssn(db_row):
    """
    This is a helper function for constructing NO_SSNs (11-siffrede
    personnumre).
    """
    no_ssn = "%02d%02d%02d%05d" % (int(db_row["fodtdag"]),
                                   int(db_row["fodtmnd"]),
                                   int(db_row["fodtar"]),
                                   int(db_row["personnr"]))
    try:
        fodselsnr.personnr_ok(no_ssn)
    except (ValueError, fodselsnr.InvalidFnrError), exc_value:
        logger.error("Aiee! Failed to construct proper NO_SSN %s: %s",
                     no_ssn, exc_value)
        return None
    # yrt

    return no_ssn
# end fetch_no_ssn



def fetch_primary_account(no_ssn, db_person, constants):
    """
    Fetch primary account id of a person with NO_SSN
    """

    account, hit = cached_value(no_ssn)
    # 
    # Note that account might still be None, meaning that this no_ssn had
    # been looked up earlier without a match.
    if hit:
        return account
    # fi

    # Now, this is the first time we see this NO_SSN
    # Locate the person in the Cerebrum db

    # NB! This is a pretty dangerous stunt -- in worst case, we ignore the
    # source of the external id. While this would work fine for NO_SSNs, it
    # might fail miserably as soon as we start inserting other external ids
    # similar in 'shape' to NO_SSNs.
    # Also, should cereconf.SYSTEM_LOOKUP_ORDER matter?
    person_exists = False
    for source in [ constants.system_lt, None ]:
        try:
            db_person.clear()
            db_person.find_by_external_id(constants.externalid_fodselsnr,
                                          no_ssn,
                                          source)
            person_exists = True
            break
        except Cerebrum.Errors.NotFoundError:
            # We hope to get a match later
            pass
        # yrt
    # od

    if not person_exists:
        logger.error("Aiee! NO_SSN %s has an employment record but no " +
                     "registration in Cerebrum", no_ssn)
        cache_value(no_ssn, None)
        return None
    # fi

    # Locate the primary account
    account = db_person.get_primary_account()
    if not account:
        logger.warn("NO_SSN %s has no accounts; no group memberships " +
                    "will be updated",
                    no_ssn)
        cache_value(no_ssn, None)
        return None
    # fi

    cache_value(no_ssn, account)
    return account
# end fetch_primary_account



def process_employees(db_cerebrum, lt):
    """
    Run task 1) 
    """

    db_person = Factory.get("Person")(db_cerebrum)
    constants = Factory.get("Constants")(db_cerebrum)
    group1 = Factory.get("Group")(db_cerebrum)
    group2 = Factory.get("Group")(db_cerebrum)
    db_account = Factory.get("Account")(db_cerebrum)

    try:
        group1.find_by_name("uio-tils")
        group2.find_by_name("uio-ans")
    except Cerebrum.Errors.NotFoundError:
        logger.error("Aiee! Critical groups not found. " +
                     "Aborting all employee updates")
        return
    # yrt
    
    values = lt.GetTilsettinger()
    now = time.strftime("%Y%m%d")
    for row in values:
        # Reconstruct NO_SSN first
        no_ssn = fetch_no_ssn(row)
        if no_ssn is None:
            continue
        # fi

        # Skip outdated records
        if not (row["dato_fra"] <= now <= row["dato_til"]):
            logger.debug("Skipping irrelevant employment information: " +
                         "NO_SSN=%s; [%s;%s]",
                         no_ssn, row["dato_fra"], row["dato_til"])
            continue
        # fi

        # Get primary account id belonging to NO_SSN
        account_id = fetch_primary_account(no_ssn, db_person, constants)
        if account_id is None:
            continue
        # fi

        # Subscribe to various groups
        adjoin_member(account_id, group1, db_account, constants)
        adjoin_member(account_id, group2, db_account, constants)
    # od 
# end process_employees



def process_temporaries(db_cerebrum, lt):
    """
    Run task 2)
    """

    db_person = Factory.get("Person")(db_cerebrum)
    constants = Factory.get("Constants")(db_cerebrum)
    db_group = Factory.get("Group")(db_cerebrum)
    db_account = Factory.get("Account")(db_cerebrum)

    try:
        db_group.find_by_name("uio-ans")
    except Cerebrum.Errors.NotFoundError:
        logger.error("Aiee! Critical group not found. " +
                     "Aborting all bilag updates")
        return
    # yrt

    # import_from_LT uses UTC. Why?
    # timestamp is 180 days ago
    timestamp = time.strftime("%Y%m%d",
                              time.localtime(time.time() - (3600*24*180)))
    values = lt.GetLonnsPosteringer(timestamp)
    logger.debug("All payments fetched")
    for row in values:
        no_ssn = fetch_no_ssn(row)
        if no_ssn is None:
            continue
        # fi

        # Now, we do not care about dates here, since GetLonnsPosteringer
        # returns only the most recent rows.
        account_id = fetch_primary_account(no_ssn, db_person, constants)
        if account_id is None:
            continue
        # fi

        adjoin_member(account_id, db_group, db_account, constants)
    # od
# end process_temporaries



def adjoin_member(account_id, db_group, db_account, constants):
    """
    Adds a new member ACCOUNT_ID to group DB_GROUP, unless the account is
    already there.
    """
    
    if db_group.has_member(account_id,
                           constants.entity_account,
                           constants.group_memberop_union):
        logger.debug("%s is already a member of %s",
                     account_id, db_group.entity_id)
        return
    # fi

    # FIXME: we should have an atomic "test-and-set" operation
    # Even though one update fails, the others do not have to
    try:
        logger.debug("db_group.add_member(%d, %d, %d)",
                     int(account_id),
                     int(constants.account_namespace),
                     int(constants.group_memberop_union))
        
        db_group.add_member(account_id,
                            constants.entity_account,
                            constants.group_memberop_union)
    except:
        type, value, tb = sys.exc_info()
        logger.error("Got an exception while updating group memberships: %s",
                     str(value))
        logger.error("%s", string.join(traceback.format_tb(tb), ""))
    # yrt
# end adjoin_member



def perform_updates(user, sid):
    """
    """

    db_lt = Database.connect(user = user, service = sid, DB_driver = "Oracle")
    lt = LT(db_lt)

    db_cerebrum = Factory.get("Database")()
    db_cerebrum.cl_init(change_program="update_employee")

    # process active employees
    logger.debug("Processing employees (<tils>)")
    process_employees(db_cerebrum, lt)

    # process 'bilag' people
    logger.debug("Processing temporaries (<bilag>)")
    process_temporaries(db_cerebrum, lt)

    if not dryrun:
        db_cerebrum.commit()
        logger.info("Committed changes to the database")
    else:
        db_cerebrum.rollback()
        logger.info("No changes were committed to the database")
    # fi
# end



def usage():
    """
    Display option summary
    """

    options = """
options: 
-d, --dryrun:      do not write anything to the database, just display the
                   changes.
-v, --verbose:     output some debugging
-h, --help:        display usage
    """
    logger.info(options)
# end usage



def main(argv):
    """
    Start method for this script. 
    """
    global logger
    logger = Factory.get_logger("console")
    logger.setLevel(logging.INFO)
    logger.info("Performing employement group updates")
    
    try:
        options, rest = getopt.getopt(argv,
                                      "dvhu:s:", ["dryrun",
                                                  "verbose",
                                                  "help",
                                                  "user=",
                                                  "sid=",])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    global dryrun
    dryrun = False
    user = "ureg2000"
    sid = "LTPROD.uio.no"
    for option, value in options:
        if option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-v", "--verbose"):
            logger.setLevel(logging.DEBUG)
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)
        elif option in ("-u", "--user"):
            user = value
        elif option in ("-s", "--sid"):
            sid = value
        # fi
    # od

    perform_updates(user, sid)
# fi





if __name__ == "__main__":
    main(sys.argv[1:])
# fi

# arch-tag: b8f43327-af3a-4376-a0eb-0160aa3b01ed
