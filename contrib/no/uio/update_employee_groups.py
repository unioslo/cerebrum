#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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


"""This file performs group information update for certain employee
categories.

Specifically,

1) for all active employees with at least one 'tilsetting' registered, their
   respective primary account (user) is subscribed to groups 'uio-tils' and
   'uio-ans'.

2) for all people who have received 'bilagslønn' within the past 180 days,
   subscribe their respective primary account (user) to group 'uio-ans'. Such
   people are referred to as 'temporaries' in this script.

This script can deal with both LT and SAP input. Employment data from LT/SAP
are extracted from the corresponding XML files. The key linking file data to
Cerebrum data is the Norwegian national id (fnr).

This script generates no output. All updates are written back to the Cerebrum
database.

<employee XML data> -----+
                         |
                         +--> update_employee_groups.py ---+
                         |                                 |
<cerebrum db> -----------+ <-------------------------------+
"""

import getopt
import logging
import sys
import time
from mx.DateTime import Date, DateTimeDeltaFromDays

# import cereconf

# import Cerebrum
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.xmlutils.system2parser import system2parser


logger = logging.getLogger(__name__)


def build_cache(db, groupname):
    """Build a mapping of account_names to account_ids.

    :Parameters:
      db : a Database instance
        DB connection to Cerebrum.
      groupname : basestring
        Group name to fetch.

    :Returns:
      (result, db_group) : tuple
      ... where
      result is a dictionary mapping account_names to account_ids
      db_group is a Group instance for group associated with groupname.
    """

    logger.debug("Caching members of %s", groupname)
    try:
        db_group = Factory.get("Group")(db)
        db_group.find_by_name(groupname)
    except Errors.NotFoundError:
        logger.error("Group %s not found in Cerebrum. This script will fail.",
                     groupname)
        # TBD: sys.exit(1) ?
        return None, None

    const = Factory.get("Constants")()
    # FIXME: This is quite expensive
    account2name = dict((x["entity_id"], x["entity_name"]) for x in
                        db_group.list_names(const.account_namespace))

    # account_name->account_id mapping
    result = dict()
    for row in db_group.search_members(group_id=db_group.entity_id,
                                       indirect_members=True,
                                       member_type=const.entity_account):
        account_id = int(row["member_id"])
        if account_id not in account2name:
            continue
        account_name = account2name[account_id]
        result[account_name] = account_id

    logger.debug("Group %s has %d cached entries", groupname, len(result))
    return result, db_group


def build_employee_cache(db, sysname, filename):
    """Build a mapping of primary account names for employees to their
       employment status.

    Employment status in this case is a pair of booleans, that tell whether
    the person with that primary account has tilsettinger and bilag that we
    need.

    :Parameters:
      db : a Database instance
        DB connection to Cerebrum.
      sysname : basestring
        Name of the authoritative system whence the data comes
      filename : basestring
        XML file name (source file)
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
    logger.debug("Fetching all passport-nr->account mappings...")
    pnr2uname = db_person.getdict_external_id2primary_account(
                                      const.externalid_pass_number)
    logger.debug("... done (%d mappings)", len(pnr2uname))
    logger.debug("Fetching all ansatt-nr->account mappings...")
    anr2uname = db_person.getdict_external_id2primary_account(
                                      const.externalid_sap_ansattnr)
    logger.debug("... done (%d mappings)", len(anr2uname))

    # Build mapping for the employees
    parser = system2parser(sysname)(filename, logger, False)
    # mapping from uname to employment status
    employee_cache = dict()
    for xmlperson in parser.iter_person():
        fnr = xmlperson.get_id(xmlperson.NO_SSN)
        passport_nr = xmlperson.get_id(xmlperson.PASSNR)
        ansatt_nr = xmlperson.get_id(xmlperson.SAP_NR)

        # Everyone with bilag more recent than 180 days old is eligible
        bilag = filter(lambda x: ((not x.end) or
                                  (x.end >= (Date(*time.localtime()[:3]) -
                                             DateTimeDeltaFromDays(180)))) and
                       x.kind == x.BILAG,
                       xmlperson.iteremployment())

        # Add to cache, if found in Cerebrum either by fnr, passport-nr or anr.
        # each entry is a pair, telling whether the person has active
        # tilsetting and bilag (in that order). We do not need to know *what*
        # they are, only that they exist.
        username = {anr2uname.get(ansatt_nr),
                    fnr2uname.get(fnr),
                    pnr2uname.get(passport_nr)}
        username = [un for un in username if un is not None]

        if not username:
            logger.info("Cerebrum failed to find primary account for person "
                        "with ansatt-nr: %s.", ansatt_nr)
        elif len(username) == 1:
            employee_cache[username[0]] = (xmlperson.has_active_employments(),
                                           bool(bilag))
        else:
            logger.warn("This should probably not happen, "
                        "different users from the same person. "
                        "usernames: %s", username)

    # IVR 2007-07-13 FIXME: Is this actually useful?
    del fnr2uname
    del pnr2uname
    del anr2uname
    logger.debug("employee_cache has %d uname->employment status mappings",
                 len(employee_cache))
    return employee_cache


def perform_update(db, sysname, filename):
    """Perform all updates to all groups employee groups.

    There are two 'special' employee groups -- 'uio-tils' and 'uio-ans'. An
    'update' in this case entails both member addition and removal. The
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

    :Parameters:
      db : a Database instance
        DB connection to Cerebrum.
      sysname : basestring
        Name of the authoritative system whence the data comes
      filename : basestring
        XML file name (source file)
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

        # this account should be in uio-ans
        if bilagp:
            if uname not in bilag_cache:
                adjoin_member(uname, bilag_group, db_account, db_const)
            else:
                del bilag_cache[uname]

    # Everything left in tils/bilag_cache at this point can be safely removed.
    remove_remaining(tils_cache, tils_group, db_const)
    remove_remaining(bilag_cache, bilag_group, db_const)


def adjoin_member(uname, db_group, db_account, db_const):
    """Add uname's account_id to db_group, if it's not already there.

    :Parameters:
      uname : basestring
        Account name to add to group.
      db_group : Group instance
        Group to which the account is to be added.
      db_account : Account instance
        Used to help locate uname.
      db_const : Constants instance
    """

    try:
        db_account.clear()
        db_account.find_by_name(uname)
        db_group.add_member(db_account.entity_id)
        logger.debug("adding account %s (%s) to group %s (%s)",
                     uname, db_account.entity_id,
                     db_group.group_name, db_group.entity_id)
    except:
        # IVR 2007-07-13 This does not have to be an error, if uname is
        # already a member of db_group.
        logger.exception("adding account %s to %s failed",
                         uname, list(db_group.get_names()))


def remove_remaining(cache, db_group, db_const):
    """Remove all entries in cache from db_group.

    :Parameters:
      cache : dict
        A mapping from account_ids to corresponding unames. This cache has
        been created by build_cache.
      db_group : Group instance
        A group object bound to the proper group (uio-tils or uio-ans)
      db_const : Constants instance
    """

    for account_id in cache.itervalues():
        # IVR 2007-07-13 FIXME: There is a race condition here -- the member
        # may disappear between has_member and remove_member calls outside of
        # this job.
        if db_group.has_member(account_id):
            db_group.remove_member(account_id)
            logger.debug("removing account_id %r from %r",
                         account_id, list(db_group.get_names()))
        else:
            logger.debug("%r not a member in group %r", account_id,
                         db_group.entity_id)
            continue


def usage():
    """Display usage information about this script."""

    print """
%s [-d|--dryrun] [-h|--help] [-s|--source-spec sys:file]
... where
-d|--dryrun                Run this script without committing the changes
                           to the database.
-h|--help                  Display this message.
-s|--source-spec sys:file  Specify XML input file for this script, where
                           sys  - system to use (e.g. system_lt)
                           file - file with person info (e.g. person.xml)
""" % sys.argv[0]


def main():
    """Start method for this script."""
    Factory.get_logger("cronjob")

    logger.info("Performing uio-tils/uio-ans group updates")

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "dhs:", ["dryrun",
                                               "help",
                                               "source-spec="])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    dryrun = False
    for option, value in options:
        if option in ("-d", "--dryrun",):
            dryrun = True
        elif option in ("-h", "--help",):
            usage()
            sys.exit(0)
        elif option in ("-s", "--source-spec"):
            sysname, filename = value.split(":")

    db = Factory.get("Database")()
    db.cl_init(change_program="update_emp_grp")
    perform_update(db, sysname, filename)
    if dryrun:
        logger.info("updates completed. all changes rolled back")
        db.rollback()
    else:
        db.commit()
        logger.info("updates completed. all changes committed")


if __name__ == "__main__":
    main()
