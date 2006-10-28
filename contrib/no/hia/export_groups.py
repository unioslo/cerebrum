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

def usage():
    print """python export_groups.py [options]
    -s, --spread: choose all groups with given spread
    -o, --outfile: override def. file name (/cerebrum/dumps/EZPublish/groups.txt)
    -f : flatten out groups (find all account-members of groups and their groupmembers)

    Example: python export_groups.py -s group@ezpublish -o /tmp/testfile -f """

def make_groups_list(flat, grps):
    members = {}
    tmp = []
    if flat:
        for i in grps:
            group.clear()
            group.find_by_name(i[1])
            tmp = group.get_members(get_entity_name=True)
            members[i[1]] = string.join([x[1] for x in tmp], ',')
    else:
        for i in grps:
            group.clear()
            group.find_by_name(i[1])
            tmp = group.list_members(get_entity_name=True)
            # TODO: fix this!!
            members[i[1]] = string.join([x[2] for x in tmp[0]], ',')
    return members
    
def main():
    global group
    
    grps = []
    flat = False
    groups_and_members = {}
    outfile = '/cerebrum/dumps/EZPublish/groups.txt'

    try:
        opts, args = getopt.getopt(sys.argv[1:], "s:o:f",
                                   ['spread=',
                                    'outfile='])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, val in opts:
        if opt in ('-s', '--spread'):
            spread = val
        elif opt in ('-o', '--outfile'):
            outfile = val
        elif opt in ('-f'):
            flat = True

    if not spread:
        usage()
        sys.exit(2)

    db = Factory.get('Database')()
    constants = Factory.get('Constants')(db)
    group = Group.Group(db)
    logger = Factory.get_logger('console')
    
    logger.info("Getting groups")
    grps = group.search(spread)

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

# arch-tag: 8bf2de8c-7259-11da-9e75-4c8bb0c5d55b
