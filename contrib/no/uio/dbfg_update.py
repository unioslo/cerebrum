#! /usr/bin/env python2.2
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

Thie file performs group membership synchronization between several external
databases and cerebrum.

The updates are performed for the following sources/groups:

External db	table/source				Cerebrum group
----------------------------------------------------------------------
OFPROD		select user_name FROM applsys.fnd_user	ofprod
FSPROD		select username FROM all_users		fsprod
AJPROD		select username FROM all_users		ajprod
LTPROD		select username FROM all_users		ltprod
OAPRD		select user_name FROM applsys.fnd_user	oaprd

After the update, each group in cerebrum contains only the members listed in
the corresponding external database. That is, if

A -- usernames in the external db but not in cerebrum
B -- usernames in the external db AND cerebrum
C -- usernames NOT in the external db but IN cerebrum

... then only A+B shall be in cerebrum (that is, in the corresponding
cerebrum group from the table above) after the update.

This script produces no output (apart from debug/error messages). All update
information is written back to cerebrum:

<ofprod db> ---+
<fsprod db> ---+
<ajprod db> ---+---> dbfg_update.py ---+
<ltprod db> ---+                       |
<oaprd db> ----+                       |
               |                       |
<cerebrum db> -+ <---------------------+

Each of the updates can be turned on/off from the command line.

"""

import sys
import string
import getopt

import cerebrum_path
import cereconf
import traceback

import Cerebrum
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_LT import LT
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no.uio.access_OF import OF
from Cerebrum.modules.no.uio.access_AJ import AJ
from Cerebrum.modules.no.uio.access_OA import OA

# FIXME: As of python 2.3, this module is part of the standard distribution
if sys.version >= (2, 3):
    import logging
else:
    from Cerebrum.extlib import logging
# fi



def sanitize_group(cerebrum_group, constants):
    """
    This helper function removes 'unwanted' members of CEREBRUM_GROUP.

    The groups handled by this script are flat and should contain only union
    members. That is:

    * all group members (of CEREBRUM_GROUP) are deleted (union or not)
    * all intersection members are deleted.
    * all difference members are deleted.
    """

    union, intersection, difference = cerebrum_group.list_members()
    removed_count = 0

    # First, let's get rid of group union members
    for entity_type, entity_id in union:
        if int(entity_type) == int(constants.entity_group):
            logger.error("Aiee! Group id %s is a member of group %s",
                         entity_id, cerebrum_group.group_name)
            cerebrum_group.remove_member(int(entity_id),
                                         constants.group_memberop_union)
            removed_count += 1
        # fi
    # od

    # ... then all intersection members
    for entity_type, entity_id in intersection:
        logger.error("Aiee! %s is an intersection member of %s",
                     entity_id, cerebrum_group.group_name)
        cerebrum_group.remove_member(int(entity_id),
                                     constants.group_memberop_intersection)
        removed_count += 1
    # od
    
    # ... and at last all difference members
    for entity_type, entity_id in difference:
        logger.error("Aiee! %s is a difference member of %s",
                     entity_id, cerebrum_group.group_name)
        cerebrum_group.remove_member(int(entity_id),
                                     constants.group_memberop_difference)
        removed_count += 1
    # od

    logger.info("%d entity(ies) was(were) sanitized from %s",
                removed_count, cerebrum_group.group_name)
# end sanitize_group



def synchronize_group(external_group, cerebrum_group_name):
    """
    This is where all the work is done.

    This function implements direct/immediate (rather then transitive)
    membership only.

    The synchronization is carried out in the following fashion:

    * Construct a set G_c of all members of CEREBRUM_GROUP_NAME
    * for each m in <external_group>:
          if <m does not exist in cerebrum>:
              # Here, an account exists in the external source, but not in
              # Cerebrum. We simply ignore these cases.
              <complain>
          elif <m does not exist in G_c>:
              # Here, the account exists in Cerebrum, but it is not a member
              # of the required group. Therefore we add it.
              <add m to the group>
          # fi

          # This marks m as processed
          <remove m from G_c>
      # od

    * At this step, everything still in G_c exists in Cerebrum, but not in
      the external source. Such entries must be removed from Cerebrum.
      for each n in G_c:
          <remove n from group>
      # od

    Adding an account to a group means:
      1. adding it as a direct 'union'-member.
      2. removing it as a direct 'difference'-member.

    Removing an account from a group means:
      1. removing it as a direct 'union'-member.
      2. removing it as a direct 'intersection'-member.

    NB! All the groups 'touched' by this script are flat. That is, only user
    accounts are members of these groups (not other groups). Furthermore,
    only union-membership is permitted.

    All group-, intersect- and difference members are removed
    automatically. This is intentional.
    """

    try:
        cerebrum_db = Factory.get("Database")()
        cerebrum_db.cl_init(change_program="dbfg_update")
        cerebrum_group = Factory.get("Group")(cerebrum_db)
        cerebrum_account = Factory.get("Account")(cerebrum_db)
        constants = Factory.get("Constants")

        cerebrum_group.find_by_name(cerebrum_group_name)
    except Cerebrum.Errors.NotFoundError:
        logger.error("Aiee! Group %s not found in cerebrum. " +
                     "We will not be able to synchronize it")
        return
    # yrt

    sanitize_group(cerebrum_group, constants)

    new_count = 0
    external_count = 0

    current = construct_group(cerebrum_group)
    for row in external_group.list_dbfg_usernames():
        external_count += 1

        # FIXME: Ugh! Username cases are different here and there. This
        # assumes that there are no two different accounts whose name
        # differs only in the case. However, there are also accounts with
        # mixed cased in cerebrum. Basically, this means that such accounts
        # would be left out of group synchronization.
        #
        # External sources hand us usernames in uppercase.
        account_name = string.lower(row.username)

        # Find it in cerebrum
        try:
            cerebrum_account.clear()
            cerebrum_account.find_by_name(account_name)
        except Cerebrum.Errors.NotFoundError:
            logger.info("%s exists in the external source, but not in Cerebrum",
                        account_name)
        else:
            # Here we now that the account exists in Cerebrum.
            # Is it a member of CEREBRUM_GROUP_NAME already?
            if not current.has_key(account_name):
                # New member for the group! Add it to Cerebrum
                add_to_cerebrum_group(cerebrum_account, cerebrum_group, constants)
                new_count += 1
            else:
                # Mark this account as processed
                del current[account_name]
            # fi
        # yrt
    # od

    # Now, all that is left in CURRENT does NOT exist in EXTERNAL_GROUP.
    logger.info("Added %d new account(s) to %s",
                new_count, cerebrum_group.group_name)
    logger.info("%d account(s) from %s need to be removed",
                len(current), cerebrum_group.group_name)
    logger.info("%d account(s) in the external source", external_count)
    for account_name, account_id in current.items():
        try:
            cerebrum_account.clear()
            cerebrum_account.find_by_name(account_name)
        except Cerebrum.Errors.NotFoundError:
            logger.error("Aiee! account (%s, %s) spontaneously disappeared " + 
                         "from (%s, %s)?",
                         account_name, account_id,
                         cerebrum_group.group_name, cerebrum_group.entity_id)
        else:
            remove_from_cerebrum_group(cerebrum_account, cerebrum_group, constants)
        # yrt
    # od

    if dryrun:
        cerebrum_db.rollback()
        logger.info("All changes rolled back")
    else:
        cerebrum_db.commit()
        logger.info("Commited all changes")
    # fi
# end synchronize_group



def remove_from_cerebrum_group(account, group, constants):
    """
    Removes ACCOUNT.ENTITY_ID as a union/intersection member of
    GROUP.ENTITY_ID
    """

    try:
        # Since GROUP is 'sanitized' prior to calling this method, is there
        # any point in remove the intersection members? (there are none)
        for operation in [ constants.group_memberop_union,
                           constants.group_memberop_intersection ]:
            group.remove_member(int(account.entity_id),
                                int(operation))
        # od
    except:
        # FIXME: How safe is it to do any updates if this happens?
        type, value, tb = sys.exc_info()
        logger.error("Aiee! Removing %s from %s failed: %s, %s, %s",
                     account.account_name,
                     group.group_name,
                     str(type), str(value),
                     string.join(traceback.format_tb(tb)))
    # yrt
# end remove_from_cerebrum_group
        


def add_to_cerebrum_group(account, group, constants):
    """
    Adds the ACCOUNT.ENTITY_ID as a (union) member of GROUP.ENTITY_ID.

    Also, removes difference member ACCOUNT from GROUP, should such a member
    exist (it should not, really, but this is just a precaution).
    """

    logger.debug("Adding 'union' account member %s (%s) to group %s (%s)",
                 account.entity_id, account.account_name,
                 group.entity_id, group.group_name)

    try:
        # Add a new union member

        # NB! Removal has to be done before addition in this case.
        # Otherwise the changelog displays the changes as a removal of
        # ACCOUNT from GROUP (changelog is not aware of the various group
        # operations))
        group.remove_member(int(account.entity_id),
                            int(constants.group_memberop_difference))
        
        group.add_member(int(account.entity_id),
                         int(constants.entity_account),
                         int(constants.group_memberop_union))
    except:
        # FIXME: How safe is it to do any updates if this happens?
        type, value, tb = sys.exc_info()
        logger.error("Aiee! Adding %s to %s failed: %s, %s, %s",
                     account.account_name,
                     group.group_name,
                     str(type), str(value),
                     string.join(traceback.format_tb(tb)))
    # yrt
# end 



def construct_group(cerebrum_group):
    """
    This is a helper function that produces a suitable data structure for
    group synchronization.

    Specifically, it returns a dictionary mapping account names to account
    ids
    """

    result = {}

    # Although get_members() performes a recursive lookup, this gives the
    # right answer nonetheless, since the groups touched by this script are
    # "flat". Also, we call this function _after_ CEREBRUM_GROUP has been
    # "sanitized", and thus get_members() and list_members()[0] produce
    # similar answers. get_members() is just a little bit more convenient to
    # use.
    for row in cerebrum_group.get_members(get_entity_name=True):
        # <username -> account_id>
        result[row[1]] = int(row[0])
    # od

    logger.info("Fetched %d entries for group %s",
                len(result), cerebrum_group.group_name)
    
    return result
# end
    


def perform_synchronization(user, services):
    """
    Synchronize cerebrum groups with all external SERVICES.
    """

    for service, accessor_class, cerebrum_group in services:
        logger.debug("Synchronizing against source %s", service)

        try:
            db = Database.connect(user = user, service = service,
                                  DB_driver = "Oracle")
            accessor = accessor_class(db)
        except:
            type, value, tb = sys.exc_info()
            logger.error("Aiee! Failed to connect to %s: %s, %s, %s",
                         service,
                         type, value,
                         string.join(traceback.format_tb(tb)))
            
        else:
            synchronize_group(accessor, cerebrum_group)
        # yrt
    # od
# end perform_synchronization





def main(argv):
    """
    Start method for this script. 
    """
    global logger
    logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
    logger = logging.getLogger("console")
    logger.setLevel(logging.INFO)
    logger.info("Performing group synchronization")
    
    try:
        options, rest = getopt.getopt(argv,
                                      "dvhoflap", ["dryrun",
                                                   "verbose",
                                                   "help",
                                                   "ofprod",
                                                   "fsprod",
                                                   "ltprod",
                                                   "ajprod",
                                                   "oaprd",
                                                   ])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    # yrt

    user = "ureg2000"
    services = []
    global dryrun
    dryrun = False
    for option, value in options:
        if option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-v", "--verbose"):
            logger.setLevel(logging.DEBUG)
        elif option in ("-h", "--help"):
            usage()
            sys.exit(2)
        # Ugh, ugly code
        elif option in ("-o", "--ofprod"):
            services.append(("OFPROD.uio.no", OF, "ofprod"))
        elif option in ("-f", "--fsprod"):
            services.append(("FSPROD.uio.no", FS, "fsprod"))
        elif option in ("-l", "--ltprod"):
            services.append(("LTPROD.uio.no", LT, "ltprod"))
        elif option in ("-a", "--ajprod"):
            services.append(("AJPROD.uio.no", AJ, "ajprod"))
        elif option in ("-p", "--oaprd"):
            services.append(("OAPRD.uio.no", OA, "oaprd"))
        # fi
    # od

    perform_synchronization(user, services)
# end main





if __name__ == "__main__":
    main(sys.argv[1:])
# fi

