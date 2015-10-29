#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
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

import string
import os
import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Group

try:
    set()
except NameError:
    from sets import Set as set


def usage():
    print """python export_groups.py [options]
    -s, --spread: choose all groups with given spread
    -o, --outfile: override def. file name (/cerebrum/var/cache/EZPublish/groups.txt)
    -f : flatten out groups (find all account-members of groups and their groupmembers)

    Example: python export_groups.py -s group@ezpublish -o /tmp/testfile -f """

def make_groups_list(flat, grps):
    """

    @type flat: bool
    @param flat:
      Whether to flatten out group memberships.

    @type grps: sequence or generator of db_rows
    @param grps:
      Sequence or generator of rows containing groups we want to scan for
      members. See Group.search() for db_row description.

    @rtype: dict (of basestring to basestring)
    @return:
      A dict-like object from group names to a string with members
      names. Member names are ','-separated within the string.
    """
    entity2name = dict((x["entity_id"], x["entity_name"]) for x in 
                       group.list_names(constants.account_namespace))
    entity2name.update((x["entity_id"], x["entity_name"]) for x in
                       group.list_names(constants.group_namespace))
    members = {}
    if flat:
        for i in grps:
            group.clear()
            group.find(i["group_id"])
            tmp = group.search_members(group_id=group.entity_id,
                                       indirect_members=True,
                                       member_type=constants.entity_account)
            tmp = set([int(x["member_id"]) for x in tmp])
            members[i["name"]] = ','.join(entity2name[x]
                                          for x in tmp
                                          if x in entity2name)
    else:
        for i in grps:
            group.clear()
            group.find(i["group_id"])
            # collect the members of group that have names
            member_names = [entity2name.get(int(x["member_id"])) for x in
                            group.search_members(group_id=group.entity_id)
                            if int(x["member_id"]) in entity2name]
            members[i["name"]] = ','.join(member_names)
    return members
# end make_groups_list
    
def main():
    global group, constants
    
    grps = []
    flat = False
    groups_and_members = {}
    spread_val = ""
    outfile = '/cerebrum/var/cache/EZPublish/groups.txt'

    try:
        opts, args = getopt.getopt(sys.argv[1:], "s:o:f",
                                   ['spread=',
                                    'outfile='])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, val in opts:
        if opt in ('-s', '--spread'):
            spread_val = val
        elif opt in ('-o', '--outfile'):
            outfile = val
        elif opt in ('-f'):
            flat = True

    if not spread_val:
        usage()
        sys.exit(2)

    db = Factory.get('Database')()
    constants = Factory.get('Constants')(db)
    group = Factory.get("Group")(db)
    logger = Factory.get_logger('cronjob')

    spread = int(constants.Spread(spread_val))
    
    logger.info("Getting groups")
    grps = group.search(spread=spread)

    logger.info("Processing groups")
    groups_and_members = make_groups_list(flat, grps)
    
    logger.info("Writing groups file.")
    stream = open(outfile, 'w')

    for k, v in groups_and_members.iteritems():
        stream.write(k + ';' + v)
        stream.write('\n')
    stream.close()
    logger.info("All done.")

    
if __name__ == '__main__':
    main()
