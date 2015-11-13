#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 University of Oslo, Norway
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
Generate a pickle file that contains entitlement traits per each active
primary user account. The entitlement traits per account is a list that is
composed from 'entitlement' group traits collected from every group
the given primary user account is a member of.

Parameters:
    --help : This help
    --picklefile fname : Path to the file where the resulting
pickle should be stored. If omitted, the script will use the path from
LDAP_PERSON['entitlements_pickle_file'] from Cerebrum's configuration.
Manual specification should be used for testing only.
"""

import cerebrum_path
import cereconf

import getopt
import pickle
import os
import sys
from collections import defaultdict

from Cerebrum.Utils import Factory

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
gr = Factory.get('Group')(db)
co = Factory.get('Constants')(db)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


def get_groups_with_entitlement():
    groups_with_entitlement = {}
    for group in gr.list_traits(co.trait_group_entitlement):
        groups_with_entitlement[group['entity_id']] = group['strval']
    return groups_with_entitlement


def map_entitlements_to_persons(groups_entitlement):
    """
    The function gets all primary user accounts that are the members of
    the groups with 'entitlement' trait, determines which persons accounts
    belong to and composes a dictionary of entitlements per person.
    """
    mapped_entitlements = defaultdict(set)
    primary_accounts_dict = {}
    for account in ac.list_accounts_by_type(primary_only=True):
        primary_accounts_dict[account['account_id']] = account['person_id']
    for group_id, group_entitlement in groups_entitlement.iteritems():
        group_members = gr.search_members(group_id=group_id,
                                          member_type=co.entity_account,
                                          member_filter_expired=True,)
        for member in group_members:
            # Non-primary accounts are excluded
            if not member['member_id'] in primary_accounts_dict:
                continue
            # There is only one primary account per person
            person_id = primary_accounts_dict[member['member_id']]
            mapped_entitlements[person_id].add(group_entitlement)
    return mapped_entitlements


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'picklefile='])
    except getopt.GetoptError:
        print "Invalid options provided"
        usage(1)
    picklefile = None
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--picklefile',):
            picklefile = val
    if not(picklefile):
        picklefile = cereconf.LDAP_PERSON.get('entitlements_pickle_file')
    if not (picklefile):
        print "The path to picklefile was neither provided nor found in the configuration"
        usage(1)
    if args:
        print "Unknown arguments provided:",
        print args
        usage(1)

    groups_with_entitlement = get_groups_with_entitlement()
    entitlements_per_person = map_entitlements_to_persons(groups_with_entitlement)
    tmpfname = picklefile + ".tmp"
    pickle.dump(entitlements_per_person, open(tmpfname, "w"))
    os.rename(tmpfname, picklefile)

if __name__ == '__main__':
    main()
