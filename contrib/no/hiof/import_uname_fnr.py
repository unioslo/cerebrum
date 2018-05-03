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

This file is a HiOF-specific extension of Cerebrum. It contains code
which import historical account data from HiOf into Cerebrum.
Normally, it should be run only once (about right after the database
has been created).

The input format for this job is files with one line per
account. Each line has the format:

<uname>:<no_ssn>

... where

no_ssn  -- 11-digit Norwegian social security number (personnummer)
uname   -- account name
"""

import getopt
import sys
import string

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr



def attempt_commit():
    if dryrun:
        db.rollback()
        logger.debug("Rolled back all changes")
    else:
        db.commit()
        logger.debug("Committed all changes")


def process_lines(infile):
    """
    Scan all lines in INFILE and create corresponding account entries
    in Cerebrum.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000

    # Iterate over all persons:
    for line in stream:
        commit_count += 1
        logger.debug5("Processing line: |%s|", line.strip())

        fields = string.split(line.strip(), ";")
        if len(fields) != 2:
            logger.error("Bad line: %s. Skipping" % l)
            continue
        
        uname, fnr = fields

        try:
            fnr = fodselsnr.personnr_ok(fnr)
        except fodselsnr.InvalidFnrError:
            logger.error("Bad fnr: %s, uname %s. Skipping!" % (fnr, uname))
            continue

        person_id = process_person(fnr)
        logger.debug4("Processing person with user: %s", uname)
        account_id = process_user(person_id, uname)
        
        if not account_id:
            logger.error("Bad uname: %s Skipping", line)

        if commit_count % commit_limit == 0:
            attempt_commit()


def process_person(fnr):
    """
    Find (or create, if necessary) and return the person_id corresponding to
    FNR.
    """
    # If person already exists, return entity_id
    if fnr2person_id.has_key(fnr):
        return fnr2person_id[fnr]

    try:
        person.clear()
        person.find_by_external_id(constants.externalid_fodselsnr, fnr)
        e_id = person.entity_id
        fnr2person_id[fnr] = e_id
        return e_id
    except Errors.NotFoundError:
        pass
        
    # ... otherwise, create a new person
    person.clear()
    gender = constants.gender_male
    if fodselsnr.er_kvinne(fnr):
        gender = constants.gender_female
    year, mon, day = fodselsnr.fodt_dato(fnr)
    person.populate(db.Date(year, mon, day), gender)
    person.affect_external_id(constants.system_migrate,
                              constants.externalid_fodselsnr)
    person.populate_external_id(constants.system_migrate,
                                constants.externalid_fodselsnr,
                                fnr)
    person.write_db()
    logger.debug("Created new person with fnr %s", fnr)
    e_id = person.entity_id
    fnr2person_id[fnr] = e_id
    return e_id

    
def process_user(owner_id, uname):
    """
    Locate account_id of account UNAME owned by OWNER_ID.
    """
    
    if uname == "":
        return None
    
    owner_type = constants.entity_person
    np_type = None
    if owner_id is None:
        owner_type = constants.entity_group
        owner_id = default_group_id
        np_type = int(constants.account_program)
    
    try:
        account.clear()
        account.find_by_name(uname)
        logger.debug3("User %s exists in Cerebrum", uname)
    except Errors.NotFoundError:
        account.populate(uname,
                         owner_type,
                         owner_id,
                         np_type,
                         default_creator_id,
                         None)
        account.write_db()
        logger.debug3("User %s created", uname)

    a_id = account.entity_id
    return a_id




def usage():
    print """Usage: import_uname_fnr.py
    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    """
    sys.exit(0)



def main():
    global db, constants, account, person, fnr2person_id
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
    infiles = []
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infiles.append(val)

    if not infiles:
        usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='import_uname')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    person = Factory.get('Person')(db)

    fnr2person_id = dict()

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    group.find_by_name(cereconf.INITIAL_GROUPNAME)
    default_group_id = group.entity_id

    for infile in infiles:
        process_lines(infile)

    attempt_commit()



if __name__ == '__main__':
    main()
