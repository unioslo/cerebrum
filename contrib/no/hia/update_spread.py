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
from Cerebrum.Constants import _SpreadCode



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

        fnr = fields[0]
        uname = fields[1]
        if fnr == "":
            logger.warn("User: %s got no fnr. Skipping", uname)
            continue
        if not uname == "":
            user_id = process_user(uname, fnr)
        else:
            logger.warn("No username: %s. Skipping", line)
        # fi
        if commit_count % commit_limit == 0:
            attempt_commit()
        # fi
    # od
# end process_line

    
def process_user(uname, fnr):
    """
    Set uid/gid for user.
    """
    try:
        person.clear()
        person.find_by_external_id(co.externalid_fodselsnr, fnr)
    except Errors.NotFoundError:
        logger.warn("Person with fnr: %s doesn't exists in Cerebrum.", fnr)
        return
    # yrt

    try:
        pu.clear()
        pu.find_by_name(uname)
        if pu.owner_id == person.entity_id:
            logger.debug3("User %s exists in Cerebrum with person: %s",
                          uname, fnr)
            pu.add_spread(spread)
            pu.write_db()
            logger.debug3("User %s got spread %s", uname, spread)
        else:
            logger.warn("User %s exists with owner: %s. We have: %s.",
                        pu.account_name, pu.owner_id, person.entity_id)
        return
    except Errors.NotFoundError:
        logger.warn("POSIX-user not found: %s.", uname)
        return
    # yrt
# end process_user

def map_spread(id):
    try:
        return int(_SpreadCode(id))
    except Errors.NotFoundError:
        print "Error mapping %s" % id
        raise
# end map_spread


def usage():
    print """Usage: update_spread.py
    -v, --verbose : Show extra information. Multiple -v's are allowed
                    (more info).
    -f, --file    : File to parse.
    -s, --spread  : Give spread to users.
    """
    sys.exit(0)
# end usage



def main():
    global db, co, spread, dryrun, logger, pu, person

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:ds:',
                                   ['file=',
                                    'dryrun',
                                    'spread'])
    except getopt.GetoptError:
        usage()
    # yrt


    db = Factory.get('Database')()
    db.cl_init(change_program='update_spread')
    co = Factory.get('Constants')(db)
    pu = PosixUser.PosixUser(db)
    person = Factory.get('Person')(db)


    dryrun = False
    spread = None
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-s', '--spread'):
            spread = map_spread(val)
        # fi
    # od

    if infile is None:
        usage()
    # fi
    if spread is None:
        print "ERROR: Must supply a spread!\n"
        usage()
    # fi

    pu = PosixUser.PosixUser(db)
    pg = PosixGroup.PosixGroup(db)

    process_line(infile)

    attempt_commit()
# end main





if __name__ == '__main__':
    main()
# fi
