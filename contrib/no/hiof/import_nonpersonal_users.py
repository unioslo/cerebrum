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
import historical account data from HiOf into Cerebrum. Normally,
it should be run only once (about right after the database has been
created).

The input format for this job is a file with one line per
account. Each line has four fields separated by ';'.

<uname>;<group>
"""

import getopt
import sys

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory



def attempt_commit():
    if dryrun:
        db.rollback()
        logger.debug("Rolled back all changes")
    else:
        db.commit()
        logger.debug("Committed all changes")


def process_line(infile):
    """
    Scan all lines in INFILE and create corresponding account/group entries
    in Cerebrum.
    """

    stream = open(infile, 'r')

    for line in stream:
        logger.debug5("Processing line: |%s|", line.strip())

        fields = line.strip().split(";")
        if len(fields) != 2:
            logger.error("Bad line: %s. Skipping" % l)
            continue
        
        uname, gname = fields

        # Check group
        group_id = process_group(gname.strip())
        if group_id:
            # Group exists, check uname
            account_id = process_account(group_id, uname.strip())
        else:
            logger.warn("Group |%s| not found!", gname)
            logger.error("Trying to assign membership to a non-existing group |%s|", gname)
            
    stream.close()


def process_group(gname):
    """
    Find group if it exists and return id. If not return None
    """

    if gname.strip() == "":
        return None
    
    try:
        group.clear()
        group.find_by_name(gname)
        return group.entity_id
    except Errors.NotFoundError:
        return None


def process_account(owner_group_id, uname):
    """
    Create non-personal account with name uname. 
    """
    
    if uname == "":
        return None

    owner_type = constants.entity_group
    np_type = int(constants.account_program)
    
    try:
        account.clear()
        account.find_by_name(uname)
        logger.debug3("User %s exists in Cerebrum", uname)
        return None
    except Errors.NotFoundError:
        if account.illegal_name(uname):
            return None
        account.populate(uname,
                         owner_type,
                         owner_group_id,
                         np_type,
                         default_creator_id,
                         None)
        account.write_db()
        logger.debug3("User %s created", uname)

    a_id = account.entity_id
    return a_id


def usage():
    print """Usage: import_nonpersonal_users.py
    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    """


def main():
    global db, constants, account, group
    global default_creator_id, default_group_id
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

    if infile is None:
        usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='import_nonpers')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id

    process_line(infile)

    attempt_commit()


if __name__ == '__main__':
    main()

