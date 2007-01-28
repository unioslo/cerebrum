#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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
The input format for this job is a file with one line per
person/account. Each line has four fields separated by ':'.

<no_ssn>:<uname>:<lastname>:<firstname>

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
from Cerebrum.modules import Email
from Cerebrum.modules.no import fodselsnr


def attempt_commit():
    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")

def process_line(infile):
    """
    Scan all lines in INFILE and create corresponding account/e-mail entries
    in Cerebrum.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000

    # Iterate over all persons:
    for line in stream:
        commit_count += 1

        fields = string.split(line.strip(), ":")
        if len(fields) != 4:
            logger.error("Bad line: %s. Skipping" % line.strip())
            continue
        fnr, uname, lname, fname = fields
        if not fnr == "":
            uname = check_uname(uname)
            if uname:
                person_id = process_person(fnr)
                if person_id:
                    logger.debug("Processing user with person: %s", uname)
                    account_id = process_user(person_id, uname)
                else:
                    logger.error("Bad fnr: %s Skipping", line.strip())
                    continue
        else:
            logger.debug("Processing user without person: %s", uname)
            account_id = process_user(None, uname)
        
        if commit_count % commit_limit == 0:
            attempt_commit()

def process_person(fnr):
    """
    Find or create a person; return the person_id corresponding to
    fnr.
    """

    logger.debug("Processing person %s", fnr)
    try:
        fodselsnr.personnr_ok(fnr)
    except fodselsnr.InvalidFnrError:
        logger.warn("Bad no_ssn |%s|", fnr)
        return None
    
    if fnr2person_id.has_key(fnr):
        logger.debug("Person with fnr %s exists in Cerebrum", fnr)
        return fnr2person_id[fnr]
    
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


def check_uname(uname):
    legal_chars = string.ascii_letters + string.digits    
    if uname == "":
        logger.warn("Nothing to do here.")
        return None

    if not uname.islower():
        uname = uname.lower()
    if len(uname) > 12 or len(uname) < 3:
        logger.error("Uname too short or too long %s.", uname)
        return None

    # check uname for special and non-ascii characters 
    for u in uname:
        if u not in legal_chars:
            logger.error("Bad uname %s.", uname)
            return None
    return uname
        
    
def process_user(owner_id, uname):
    """
    Locate account_id of account UNAME owned by OWNER_ID.
    """
    owner_type = constants.entity_person
    np_type = None
    try:
        account.clear()
        account.find_by_name(uname)
        logger.debug("User %s exists in Cerebrum", uname)
    except Errors.NotFoundError:
        account.populate(uname,
                         owner_type,
                         owner_id,
                         np_type,
                         default_creator_id,
                         None)
        account.write_db()
        logger.debug("User %s created", uname)

    a_id = account.entity_id
    return a_id

def usage():
    print """Usage: import_uname_mail.py
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
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val

    if infile is None:
        usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='init_import')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    person = Factory.get('Person')(db)

    fnr2person_id = dict()
    for p in person.list_external_ids(id_type=constants.externalid_fodselsnr):
        fnr2person_id[p['external_id']] = p['entity_id']

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    group.find_by_name(cereconf.INITIAL_GROUPNAME)
    default_group_id = group.entity_id
    process_line(infile)

    attempt_commit()


if __name__ == '__main__':
    main()

