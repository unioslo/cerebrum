#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2006-2011 University of Oslo, Norway
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
Import person and account info. For migration use only.

Import fnr, uname, and optionally person names if option --set-names
is given. Accounts will either be created or reserved depending on the
option --reserve-unames.

TBD: 

The input format for this job is a file with one line per
person/account. Each line has four fields separated by ':'.

<no_ssn>:<uname>:<lastname>:<firstname>

no_ssn  -- 11-digit Norwegian social security number (personnummer)
uname   -- account name
"""

import getopt
import sys
import string
import mx.DateTime

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr

## Globals
db = Factory.get('Database')()
db.cl_init(change_program='init_import')
constants = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
group = Factory.get('Group')(db)
person = Factory.get('Person')(db)
logger = Factory.get_logger("cronjob")

fnr2person_id = dict()
account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
default_creator_id = account.entity_id
group.find_by_name(cereconf.INITIAL_GROUPNAME)
default_group_id = group.entity_id


def attempt_commit(dryrun=False):
    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")


def process_line(infile, maxlen, reserve_unames, set_names):
    """
    Scan all lines in INFILE and create corresponding person/account
    entries in Cerebrum.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000

    # Iterate over all persons:
    for line in stream:
        commit_count += 1

        fields = [x.strip() for x in line.split(":")]
        if len(fields) == 2:
            fnr, uname = fields
            lname = fname = bewid = ''
        elif len(fields) == 3:
            fnr, uname, bewid = fields
            lname = fname = ''
        elif len(fields) == 4:
            fnr, uname, lname, fname = fields
            bewid = ''
        else:
            logger.error("Bad line: %s. Skipping" % line.strip())
            continue

        if not fnr:
            logger.error("No fnr. Skipping line: %s" % line.strip())
            continue

        person_id = process_person(fnr, lname, fname, bewid, set_names)
        if not person_id:
            continue

        if reserve_unames:
            reserve_user(person_id, uname, maxlen)
        else:
            create_user(person_id, uname, maxlen)
        
        if commit_count % commit_limit == 0:
            attempt_commit()


def process_person(fnr, lname, fname, bewid, set_names):
    """
    Find or create a person; return the person_id corresponding to
    fnr. Set name for new persons if set_name is True.
    """    
    logger.debug("Processing person %s %s (%s)", fname, lname, fnr)
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
    if bewid:
        person.affect_external_id(constants.system_migrate,
                                  constants.externalid_fodselsnr,
                                  constants.externalid_bewatorid)
    else:
        person.affect_external_id(constants.system_migrate,
                                  constants.externalid_fodselsnr)        
    person.populate_external_id(constants.system_migrate,
                                constants.externalid_fodselsnr,
                                fnr)
    person.write_db()
    e_id = person.entity_id
    logger.info("Created new person with id %s and fnr %s", e_id, fnr)

    if bewid:
        person.populate_external_id(constants.system_migrate,
                                    constants.externalid_bewatorid,
                                    bewid)
    person.write_db()
    logger.info("Added BewatorID %s for %s", bewid, fnr)
    
    if set_names:
        if lname and fname:
            person.affect_names(constants.system_migrate,
                                constants.name_first, constants.name_last)
            person.populate_name(constants.name_first, fname)
            person.populate_name(constants.name_last, lname)
            logger.info("Name %s %s set for person %s", fname, lname, fnr)
            person.write_db()
        else:
            logger.warn("Couldn't set name %s %s for person %s",
                        fname, lname, fnr)

    fnr2person_id[fnr] = e_id
    return e_id


def check_uname(uname, maxlen, strict=True):
    """
    Check if uname is acceptable
    """
    legal_chars = string.ascii_letters + string.digits + "."
    if not strict:
        # Allow a few more chars for reserved accounts
        legal_chars += '_-'

    if uname == "":
        logger.warn("No username. Nothing to do here.")
        return None

    if strict:
        if len(uname) < 3 or len(uname) > maxlen:
            logger.error("Uname too short or too long %s", uname)
            return None

    # check uname for special and non-ascii characters 
    if not set(uname).issubset(legal_chars):
        logger.error("Bad uname %s", uname)
        return None 

    if not uname.islower():
        uname = uname.lower()
           
    return uname


def populate_user(uname, owner_type, owner_id, np_type,
                  creator_id=default_creator_id, expire_date=None):
    try:
        account.clear()
        account.find_by_name(uname)
        logger.warn("User %s already exists in Cerebrum", uname)
        return False
    except Errors.NotFoundError:
        account.populate(uname,
                         owner_type,
                         owner_id,
                         np_type,
                         creator_id,
                         expire_date)
        account.write_db()
        return account.entity_id
    
    

def create_user(owner_id, uname, maxlen):
    """
    Locate account_id of account UNAME owned by OWNER_ID.
    """
    owner_type = constants.entity_person
    np_type = None
    uname = check_uname(uname, maxlen)
    if uname and populate_user(uname, owner_type, owner_id, np_type):
        logger.info("User %s created", uname)



def reserve_user(owner_id, uname, maxlen):
    """
    Locate account_id of account UNAME owned by OWNER_ID.
    """
    owner_type = constants.entity_group
    np_type = constants.account_system

    uname = check_uname(uname, maxlen, strict=False)
    if uname and populate_user(uname, owner_type, default_group_id, np_type,
                               expire_date=mx.DateTime.today()):
        logger.info("User %s reserved", uname)
        person.clear()
        person.find(owner_id)
        person.affect_external_id(constants.system_migrate,
                                  constants.externalid_uname)
        person.populate_external_id(constants.system_migrate,
                                    constants.externalid_uname,
                                    uname)
        person.write_db()
        logger.info("Registered %s as external id for %s", uname, owner_id)
    


def usage():
    print """Usage      : import_uname.py
    -d, --dryrun        : Run a fake import. Rollback after run.
    -f, --file          : File to parse.
    -r, --reserve-unames: Just reserve unames
    -m, --maxlen        : Max length of usernames
    -s, --set-names     : Set person names
    """
    sys.exit(0)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'rf:m:ds',
                                   ['file=',
                                    'dryrun',
                                    'reserve-unames',
                                    'maxlen=',
                                    'set-names'])
    except getopt.GetoptError:
        usage()

    # Default behaviour
    reserve_unames = False
    set_names = False
    dryrun = False
    maxlen = 8
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-m', '--maxlen'):
            maxlen = int(val)
        elif opt in ('-r', '--reserve-unames'):
            reserve_unames = True
        elif opt in ('-s', '--set-names'):
            set_names = True

    if infile is None:
        usage()

    # Fetch already existing persons
    for p in person.list_external_ids(id_type=constants.externalid_fodselsnr):
        fnr2person_id[p['external_id']] = p['entity_id']

    process_line(infile, maxlen, reserve_unames, set_names)

    attempt_commit(dryrun)


if __name__ == '__main__':
    main()

