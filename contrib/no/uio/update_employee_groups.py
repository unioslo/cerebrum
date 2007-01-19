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
This file performs group information update for certain employee categories.

Specifically,

1) for all active employees with at least one 'tilsetting' registered, their
   respective primary account (user) is subscribed to groups 'uio-tils' and
   'uio-ans'.

2) for all people who had received a 'bilagslønn' within the past 180 days,
   subscribe their respective primary account (user) to group 'uio-ans'. Such
   people are referred to as 'temporaries' in this script.

This script can deal with both LT and SAP input. Employment data from LT/SAP
are extracted from the corresponding XML files. The key to link file data to
Cerebrum is the Norwegian national id (fnr).

This script generates no output. All updates are writte back to the Cerebrum
database.

<employee XML data> -----+
                         |
                         +--> update_employee_groups.py --+
                         |                                |
<cerebrum db> -----------+ <------------------------------+

<TheBard> igorr: Ja, det skal den.  Dog slik at kun gyldige stillingskoder
          skal kunne gi medlemskap i 'uio-tils', mens man (inntil videre) kan
          la alle med gyldig hovedstilling få bli med i 'uio-ans'.
"""

import sys, time, getopt, string, traceback
from mx.DateTime import Date, DateTimeDeltaFromDays

import cerebrum_path, cereconf

import Cerebrum
from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.xmlutils.xml2object import SkippingIterator


logger = None





def build_cache(db, groupname):
    """Build a set with account_id/names of members of groupname."""

    logger.debug("Caching members of %s", groupname)
    try:
        db_group = Factory.get("Group")(db)
        db_group.find_by_name(groupname)
    except Errors.NotFoundError:
        logger.error("Group %s not found in Cerebrum. This script will fail.",
                     groupname)
        # TBD: sys.exit(1) ?
        return None, None
    # yrt

    #
    # TBD: Should we enforce empty intersection and difference?
    #
    
    # account_name->account_id mapping
    result = dict()
    for account_id, account_name in \
                    db_group.get_members(get_entity_name=True):
        result[account_name] = int(account_id)
    # od

    logger.debug("Group %s has %d cached entires", groupname, len(result))
    return result, db_group
# end build_cache



def build_employee_cache(db, sysname, filename):
    """Build a mapping of primary account names for employees to their
       employment status.
 
    Employment status in this case is a pair of booleans, that tell whether
    the person with that primary account has tilsettinger and bilag that we
    need.
    """

    logger.debug("Building employee cache")

    # Cache *all* primary accounts. This helps us bind a primary account to an
    # fnr in the XML data.
    db_person = Factory.get("Person")(db)
    const = Factory.get("Constants")(db)
    logger.debug("Fetching all fnr->account mappings...")
    fnr2uname = db_person.getdict_external_id2primary_account(
                                      const.externalid_fodselsnr)
    logger.debug("... done (%d mappings)", len(fnr2uname))

    # Build mapping for the employees
    parser = system2parser(sysname)(filename, False)
    it = parser.iter_persons()
    # mapping from uname to employment status
    employee_cache = dict()
    for xmlperson in SkippingIterator(it, logger):
        fnr = xmlperson.get_id(xmlperson.NO_SSN)
        if not fnr:
            logger.debug("Person %s has no fnr in XML source",
                         list(xmlperson.iterids()))
            continue
        # fi

        # If this fnr is not in Cerebrum, we cannot locate its primary account
        if fnr not in fnr2uname:
            logger.debug("Cerebrum has no fnr %s or primary account for fnr %s",
                         fnr, fnr)
            continue
        # fi

        # Everyone with bilag more recent than 180 days old is eligible
        bilag = filter(lambda x: ((not x.end) or
                                  (x.end >= (Date(*time.localtime()[:3]) -
                                             DateTimeDeltaFromDays(180)))) and
                                 x.kind == x.BILAG,
                       xmlperson.iteremployment())

        # each entry is a pair, telling whether the person has active
        # tilsetting and bilag (in that order). We do not need to know *what*
        # they are, only that they exist.
        employee_cache[fnr2uname[fnr]] = (xmlperson.has_active_employments(),
                                          bool(bilag))
    # od

    del fnr2uname
    logger.debug("employee_cache has %d uname->employment status mappings",
                 len(employee_cache))
    return employee_cache
# end build_employee_cache



def perform_update(db, sysname, filename):
    """Perform all updates to all groups.

    An 'update' in this case entails both member addition and removal. The
    strategy goes like this:

    * build group member caches (A and B) for uio-tils/ans
    * build employment file cache (C) from the XML source (filename)
    * for each entry E in C:
      ** if E should be in A/B:
             if E is not in A/B:                <-- new entry
                 add E to the right group
                 remove E from A/B
             if E is in A/B:                    <-- old entry
                 remove E from A/B
    * Everything left in A/B at this point are members that should no longer
      be there. Remove them.
    """
    
    # Build cached mappings for uio-tils/uio-ans
    # account_name -> account_id
    tils_cache, tils_group = build_cache(db, "uio-tils")
    # account_name -> account_id
    bilag_cache, bilag_group = build_cache(db, "uio-ans")

    # account_name -> (tils?, bilag?)
    employee_cache = build_employee_cache(db, sysname, filename)

    db_account = Factory.get("Account")(db)
    db_const = Factory.get("Constants")(db)
    # All caches are built now, we can proceed with real work
    for uname, (tilsp, bilagp) in employee_cache.iteritems():
        # this account should be in uio-tils
        if tilsp:
            if uname not in tils_cache:
                adjoin_member(uname, tils_group, db_account, db_const)
            else:
                del tils_cache[uname]
            # fi
        # fi

        # this account should be in uio-ans
        if bilagp:
            if uname not in bilag_cache:
                adjoin_member(uname, bilag_group, db_account, db_const)
            else:
                del bilag_cache[uname]
            # fi
        # fi
    # end 

    remove_remaining(tils_cache, tils_group, db_const)
    remove_remaining(bilag_cache, bilag_group, db_const)
# end perform_update



def adjoin_member(uname, db_group, db_account, db_const):
    """Add uname's account_id to db_group."""

    # TBD: Why can't we have an account_id? Ideally this remapping should not
    # be necessary.
    db_account.clear()
    try:
        db_account.find_by_name(uname)
        db_group.add_member(db_account.entity_id,
                            db_const.entity_account,
                            db_const.group_memberop_union)
        logger.debug("adding account %s (%s) to group %s (%s)",
                     uname, db_account.entity_id,
                     db_group.group_name, db_group.entity_id)
    except:
        logger.exception("adding account %s to %s failed",
                         uname, list(db_group.get_names()))
        return
    # yrt
# end adjoin_member



def remove_remaining(cache, db_group, db_const):
    """Remove all entries in cache from db_group."""

    for account_id in cache.itervalues():
        if db_group.has_member(account_id):
            db_group.remove_member(account_id, db_const.group_memberop_union)
            logger.debug("removing account_id %d (union) from %s",
                         account_id, list(db_group.get_names()))
        else:
            logger.debug("%s not a member in group %s" % (account_id, db_group.entity_id))
            continue

    # od
# end remove_remaining



def usage():
    """Display usage information about this script."""

    print """
%s [-d|--dryrun] [-h|--help] [-s|--source-spec sys:file]
... where
-d|--dryrun			Run this script without committing the changes
                                to the database.
-h|--help			Display this message.
-s|--source-spec sys:file	Specify XML input file for this script, where
                                sys  - system to use (e.g. system_lt)
                                file - file with person info (e.g. person.xml)
""" % sys.argv[0]
# end usage



def main():
    """Start method for this script."""

    global logger
    logger = Factory.get_logger("cronjob")
    logger.info("Performing uio-tils/uio-ans group updates")

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "dhs:", ["dryrun",
                                               "help",
                                               "source-spec=",])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    dryrun = False
    for option, value in options:
        if option in ("-d", "--dryrun",):
            dryrun = True
        elif option in ("-h", "--help",):
            usage()
            sys.exit(0)
        elif option in ("-s", "--source-spec"):
            sysname, filename = value.split(":")
        # fi
    # od

    db = Factory.get("Database")()
    db.cl_init(change_program="update_emp_grp")
    perform_update(db, sysname, filename)
    if dryrun:
        logger.info("updates completed. all changes rolled back")
        db.rollback()
    else:
        db.commit()
        logger.info("updates completed. all changes committed")
    # fi
# end main



    

if __name__ == "__main__":
    main()
# fi
