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
import historical account and e-mail data from HiA into Cerebrum. Normally,
it should be run only once (about right after the database has been
created).

The input format for this job is a file with one line per
account/e-mail. Each line has four fields separated by ':'.

<fnr>:<uname>:<fname>:<lname>
"""

import getopt
import sys
import string
import re

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.no import fodselsnr





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
        if len(fields) != 4:
            logger.error("Bad line: %s. Skipping", line)
            continue
        # fi
        fnr = fields[0]
        fname = fields[2]
        lname = fields[3]
        if (not fname == "") or (not lname == ""):
            person.clear()
            try:
                person.find_by_external_id(co.externalid_fodselsnr,
                                           fnr)
                logger.debug3("Person %s exists in Cerebrum", fnr)
            except Errors.NotFoundError:
                logger.warn("Person %s does not exists in Cerebrum", fnr)
                continue
            
            person.affect_names(co.system_migrate, co.name_first, co.name_last)
            person.populate_name(co.name_first, fname)
            person.populate_name(co.name_last, lname)
            logger.debug3("PErson %s got name %s, %s.", fnr, fname,
                          lname)
            person.write_db()
        else:
            logger.warn("Nameproblem: %s. Skipping", line)
        # fi
        if commit_count % commit_limit == 0:
            attempt_commit()
        # fi
    # od
# end process_line


def usage():
    print """Usage: import_ext_names.py
    -d, --dryrun  : Dryrun. No commit to database.
    -f, --file    : File to parse.
    """
    sys.exit(0)
# end usage



def main():
    global db, co, default_creator_id
    global person, dryrun, logger

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
    rm_str = None
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
    db.cl_init(change_program='import_homes')
    co = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    process_line(infile)

    attempt_commit()
# end main





if __name__ == '__main__':
    main()
# fi
