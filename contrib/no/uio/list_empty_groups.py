#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
This script lists groups that either do not have assigned members or contain
only expired members, and thus may probably be eligible to removal. 
The information returned is ID, name, description (if available), group's
moderator (if available).
"""

import getopt
import sys
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Utils
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet, \
     AuthConstants, BofhdAuthOpTarget, BofhdAuthRole

db = Factory.get('Database')()
gr = Factory.get('Group')(db)

def select_empty_groups(groups):
    empty_groups = []
    for group in groups:
        gr.clear()
        members = gr.search_members(group_id = group['group_id'], 
                                    member_filter_expired = True)
        try:
            has_members = members.next()
        except StopIteration:
            empty_groups.append([group['group_id'], group['name'], 
                                 group['description']])

    return empty_groups


def get_groups_moderators(groups):
    co = Factory.get('Constants')(db)
    en = Factory.get('Entity')(db)

    for group in groups:
        for row in group.search_moderators(group[0]):
            id = int(row['moderator_id'])
            en.clear()
            en.find(id)
            entity_id = int(en.entity_id)
            en.clear()
            ent = en.get_subclassed_object(entity_id)
            if ent.entity_type == co.entity_account:
                owner = ent.account_name
            elif ent.entity_type == co.entity_group:
                owner = ent.group_name
            else:
                owner = '#%d' % id
            group.append(" ".join([str(co.EntityType(ent.entity_type)),
                                   owner, "Group-moderator"]))

def print_empty_groups_info(groups, output_stream):
    for group in groups:
        output_stream.write("ID: %s\n" % group[0])
        output_stream.write("Name: %s\n" % group[1])
        if(group[2]):
            output_stream.write("Description: %s\n" % group[2])
        if len(group) > 3:
            for moderator in group[3:]:
                output_stream.write("Moderator: %s\n" % moderator)
        output_stream.write("\n")

def usage():
    print "***********************************"
    print "Usage: python list_empty_groups.py [-f path_to_output_file]",  
    print "[-h, --help]"
    exit(0)

def main():
    try:
        options, remainder = getopt.getopt(sys.argv[1:], 'f:h', ['help'])
    except getopt.GetoptError:
        usage()
   
    output_filename = "stdout" 
    for opt, arg in options:
        if opt == '-h' or opt == '--help':
            print __doc__
            usage()
        elif opt == '-f':
            output_filename = arg
    if(output_filename != "stdout"):
        output_stream = open(output_filename, 'w')
    else:
        output_stream = sys.stdout
        output_stream.write("WARNING! The output will be written to stdout! "
                            "Use -f switch to redirect it to a file\n")
    # Get all groups
    allgroups = gr.search()
    output_stream.write("%d groups total in the database\n" % len(allgroups))
    empty_groups = select_empty_groups(allgroups)
    output_stream.write("%d groups are empty\n" % len(empty_groups))
    get_groups_moderators(empty_groups)
    print_empty_groups_info(empty_groups, output_stream)
    if(output_filename != "stdout"):
        output_stream.close()

if __name__ == '__main__':
    main()
