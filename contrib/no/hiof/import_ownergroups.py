#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
This file is a HiOf-specific extension of Cerebrum. It contains code which
imports historical data about file and net groups from HiOf-nis (both 
common and employee-nis). The script will attempt to create the group if it is not already 
registered. 

The files read are formated as:
<gname>

gname - name of the group to be registered/updated
"""
 
import getopt
import sys
import time

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.modules import PosixGroup
from Cerebrum.Utils import Factory

def process_line(infile):
    """
    Traverse infile line for line.
    """
    stream = open(infile, 'r')
    for line in stream:
	 logger.debug5("Processing line: |%s|", line.rstrip())

         gname = line.strip()
	 if gname:
             process_group(gname)


def process_group(name, description = None):
    """
    Check whether a group with name is registered in Cerebrum, if not
    create (as normal group). If necessary assign spread and membership.
    """ 
    try:
        posixgroup.clear()
        posixgroup.find_by_name(name)
        logger.debug5("Group |%s| exists.", name)
    except Errors.NotFoundError:	
        posixgroup.populate(default_creator_id, constants.group_visibility_all,
                            name, description,
                            time.strftime("%Y-%m-%d", time.localtime()))
        posixgroup.write_db()
        if not dryrun:
            db.commit()
            logger.debug3("Created group |%s|.", name)


def usage():
    print """Usage: import_ownergroups.py
    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    """


def main():
    global db, constants, account_init, group, posixgroup
    global default_creator_id
    global dryrun, logger

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:d',
                                   ['file=',
                                    'dryrun'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val

    db = Factory.get('Database')()
    db.cl_init(change_program='import_groups')
    constants = Factory.get('Constants')(db)
    account_init = Factory.get('Account')(db)
    account_init.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account_init.entity_id
    group = Factory.get('Group')(db)
    posixgroup = PosixGroup.PosixGroup(db)

    process_line(infile)



if __name__ == '__main__':
    main()
