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
import historical account data from HiA into Cerebrum. Normally,
it should be run only once (about right after the database has been
created).

The input format for this job is a file with one line per
account. Each line has four fields separated by ':'.

<uname>:<password-hash>:::::
"""

import getopt
import sys
import string

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup




def attempt_commit():
    if dryrun:
        db.rollback()
        logger.debug("Rolled back all changes")
    else:
        db.commit()
        logger.debug("Committed all changes")
    # fi
# end attempt_commit



def process_line(infile):
    """
    Scan all lines in INFILE and set password for user in Cerebrum.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000

    # Iterate over all persons:
    for line in stream:
        commit_count += 1
        logger.debug5("Processing line: |%s|", line)

        fields = string.split(line.strip(), ":")
        if len(fields) != 8:
            logger.error("Bad line: %s. Skipping" % line)
            continue
        # fi
        
        uname = fields[1]
        uid = fields[3]
        gid = fields[4]
        if not uname == "":
            user_id = process_user(uname, uid, gid)
        else:
            logger.warn("No username: %s. Skipping", line)
        # fi
        if commit_count % commit_limit == 0:
            attempt_commit()
        # fi
    # od
# end process_line

    
def process_user(uname, uid, gid):
    """
    Set uid/gid for user.
    """

    try:
        pg.clear()
        pg.find_by_gid(gid)
        logger.debug3("Found group with gid: %s", gid)
    except Errors.NotFoundError:
        pg.clear()
        logger.warn("Group not found: %s continue with gid: %s", gid, 1000)
        pg.find_by_gid(1000)
    # yrt
    
    try:
        account.clear()
        account.find_by_name(uname)
        logger.debug3("User %s exists in Cerebrum", uname)
    except Errors.NotFoundError:
        logger.warn("User %s not found. Skipping.", uname)
        return
    # yrt

    try:
        pu.clear()
        pu.find_by_uid(int(uid))
        if pu.account_name == uname:
            logger.debug3("User %s exists as PosixUser in Cerebrum", uname)
        else:
            logger.warn("User %s exists with uid: %s. We have: %s.",
                        pu.account_name, pu.posix_uid, uid)
        return
    except Errors.NotFoundError:
        pass

    try:
        pu.clear()
        pu.find(account.entity_id)
        if int(pu.posix_uid) == int(uid):
            logger.debug3("User %s exists as PosixUser in Cerebrum", uname)
        else:
            logger.warn("User %s exists with uid: %s. Will leave alone.", uname,
                        pu.posix_uid)
        return
    except Errors.NotFoundError:
        pu.clear()
        pu.populate(uid, pg.entity_id, None, co.posix_shell_tcsh, parent=account)
        pu.write_db()
        logger.debug3("User %s promoted with uid: %s", uname, uid)
    # yrt
# end process_user



def usage():
    print """Usage: import_crypt.py
    -v, --verbose : Show extra information. Multiple -v's are allowed
                    (more info).
    -f, --file    : File to parse.
    """
    sys.exit(0)
# end usage



def main():
    global db, co, account, default_creator_id
    global dryrun, logger, pu, pg

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:d',
                                   ['file=',
                                    'dryrun'])
    except getopt.GetoptError:
        usage()
    # yrt

    dryrun = False
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        # fi
    # od

    if infile is None:
        usage()
    # fi

    db = Factory.get('Database')()
    db.cl_init(change_program='import_uid_gid')
    co = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)

    pu = PosixUser.PosixUser(db)
    pg = PosixGroup.PosixGroup(db)

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    process_line(infile)

    attempt_commit()
# end main





if __name__ == '__main__':
    main()
# fi
