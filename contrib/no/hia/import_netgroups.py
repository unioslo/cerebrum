#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

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
This file is a HiA-specific extension of Cerebrum. It contains code which
imports historical data about file and net groups from HiA-nis (both 
common and employee-nis). The script will attempt to assign the given
(option) spread to a group, creating the group if it is not already 
registered. The groups registered may be assigned one or more of the
spreads (single spread per read file): spread_nis_ng, spread_ans_nis_ng.
Has to be run twice in order to create all groups and assign memberships
correctly :/.
The files read are formated as:
<gname>:<desc>:<mgroup*|maccount*>

gname - name of the group to be registered/updated
desc - description of the group (usually what it is used for)
mgroup - name(s) of group(s) that are members 
maccount - user names of the groups account members

* - zero or more 
"""
 
import string
import os
import getopt
import sys
import time

import cerebrum_path
import cereconf

from Cerebrum import Group
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.modules import PosixGroup
from Cerebrum.Utils import Factory

def process_line(infile, spread):
    """
    Traverse infile line for line.
    """
    sp = spread
    print sp
    stream = open(infile, 'r')
    for line in stream:
	 logger.debug5("Processing line: |%s|", line)

         fields = string.split(line.strip(), ":")
         if len(fields) < 3:
             logger.error("Bad line: %s. Skipping", line)
             continue

	 gname, desc, mem = fields
	 if not gname == "":
		 process_group(sp, gname, desc, mem)

def process_group(sp, name, description = None, members = None):
    """
    Check whether a group with name is registered in Cerebrum, if not
    create (as normal group). If necessary assign spread and membership.
    """ 
    try:
   	 group.clear()
   	 group.find_by_name(name)
	 logger.debug5("Group |%s| exists.", name)
    except Errors.NotFoundError:	
	 group.populate(default_creator_id, constants.group_visibility_all,
		        name, description, time.strftime("%Y-%m-%d", time.localtime()))
	 group.write_db()
	 if not dryrun:
	     db.commit()
	     logger.debug3("Created group |%s|.", name)
    if members != "":
	process_members(name,members)
    if not group.has_spread(int(sp)):
	group.add_spread(int(sp))
	group.write_db()
	if not dryrun:
	    db.commit()
	    logger.debug5("Added spread |%s| to group |%s|.", sp, name)

def process_members(gname,mem):
    """
    Assign membership for groups and users.
    """
    mem_list = string.split(mem.strip(),",")
    group.clear()
    group.find_by_name(gname)
    for member in mem_list:
	try:
	    account_member.clear()
	    account_member.find_by_name(member)
	    if not group.has_member(account_member.entity_id, constants.entity_account,
				    constants.group_memberop_union):
		group.add_member(account_member.entity_id, constants.entity_account,
				 constants.group_memberop_union)
		group.write_db()
		if not dryrun:
		    db.commit()
		    logger.debug3("Added account |%s| to group |%s|.", member, gname)
	except Errors.NotFoundError:
	    logger.warn("User |%s| not found!", member)
	    try:
		group_member.clear()
		group_member.find_by_name(member)
		if not group.has_member(group_member.entity_id, constants.entity_group,
					constants.group_memberop_union):
		    group.add_member(group_member.entity_id, constants.entity_group,
				     constants.group_memberop_union)
		    group.write_db()
		    if not dryrun:
			db.commit()
			logger.debug3("Added group |%s| to group |%s|.", member, gname)
	    except Errors.NotFoundError:
		logger.warn("Group |%s| not found!", member)
	    logger.error("Trying to assign membership to a non-existing entity |%s|", member)
	    continue 

def usage():
    print """Usage: import_uname_mail.py
    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    -s, --spread (spread_nis_ng|spread_ans_nis_ng)
    """
# end usage

def main():
    global db, constants, account_init, account_member, group, spread, posixgroup
    global default_creator_id, group_member
    global dryrun, logger

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:d:s',
                                   ['file=',
                                    'dryrun',
				    'spread='])
    except getopt.GetoptError:
        usage()
    # yrt

    dryrun = False
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
	elif opt in ('-s','--spread'):
	    spread = val
	    if (spread not in ['spread_nis_ng','spread_ans_nis_ng']):
		usage()
        # fi
    # od

    db = Factory.get('Database')()
    db.cl_init(change_program='import_uname')
    constants = Factory.get('Constants')(db)
    account_init = Factory.get('Account')(db)
    account_init.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account_init.entity_id
    account_member = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    group_member = Factory.get('Group')(db)
    posixgroup = PosixGroup.PosixGroup(db)
    db.cl_init(change_program='import_groups')
    if spread == "spread_nis_ng":
	spread = constants.spread_nis_ng
    elif spread == "spread_ans_nis_ng":
	spread = constants.spread_ans_nis_ng
    else:
	usage()
    process_line(infile,spread)

# end main	

if __name__ == '__main__':
    main()
# fi




