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

<no_ssn>:<uname>:<keyword>:<e-mail address>

... where

no_ssn  -- 11-digit Norwegian social security number (personnummer)
uname   -- account name
keyword -- 'defaultmail' or 'mail'
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
        logger.debug("Rolled back all changes")
    else:
        db.commit()
        logger.debug("Committed all changes")
    # fi
# end attempt_commit



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
        logger.debug5("Processing line: |%s|", line)

        fields = string.split(line.strip(), ":")
        if len(fields) != 4:
            logger.error("Bad line: %s. Skipping" % l)
            continue
        # fi
        
        fnr, uname, type, addr = fields
        if not fnr == "":
            person_id = process_person(fnr)
            if person_id:
                logger.debug4("Processing user with person: %s", uname)
                account_id = process_user(person_id, uname)
            else:
                logger.error("Bad fnr: %s Skipping", line)
                continue
            # fi
        else:
            logger.debug4("Processing user without person: %s", uname)
            account_id = process_user(None, uname)
        # fi
        
        if account_id:
            process_mail(account_id, type, addr)
        else:
            logger.error("Bad uname: %s Skipping", line)
        # fi

        if commit_count % commit_limit == 0:
            attempt_commit()
        # fi
    # od
# end process_line



def process_person(fnr):
    """
    Find (or create, if necessary) and return the person_id corresponding to
    FNR.
    """

    logger.debug("Processing person %s", fnr)
    
    if not fodselsnr.personnr_ok(fnr):
        logger.warn("Bad no_ssn |%s|", fnr)
        return None
    # fi
    
    if fnr2person_id.has_key(fnr):
        logger.debug("Person with fnr %s exists in Cerebrum", fnr)
        return fnr2person_id[fnr]
    # fi
    
    # ... otherwise, create a new person
    person.clear()
    gender = constants.gender_male
    if fodselsnr.er_kvinne(fnr):
        gender = constants.gender_female
    # fi
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
# end process_person


    
def process_user(owner_id, uname):
    """
    Locate account_id of account UNAME owned by OWNER_ID.
    """
    
    if uname == "":
        return None
    # fi
    
    owner_type = constants.entity_person
    np_type = None
    if owner_id is None:
        owner_type = constants.entity_group
        owner_id = default_group_id
        np_type = int(constants.account_program)
    # fi
    
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
    # yrt

    a_id = account.entity_id
    return a_id
# end process_user



def process_mail(account_id, type, addr):
    et = Email.EmailTarget(db)
    ea = Email.EmailAddress(db)
    edom = Email.EmailDomain(db)
    epat = Email.EmailPrimaryAddressTarget(db)

    fld = addr.split('@')
    if len(fld) != 2:
        logger.error("Bad address: %s. Skipping", addr)
        return None
    # fi
    
    lp, dom = fld
    try:
        edom.find_by_domain(dom)
        logger.debug("Domain found: %s: %d", dom, edom.email_domain_id)
    except Errors.NotFoundError:
        edom.populate(dom, "Generated by import_uname_mail.")
        edom.write_db()
        logger.debug("Domain created: %s: %d", dom, edom.email_domain_id)
    # yrt

    try:
        et.find_by_entity(int(account_id))
        logger.debug("EmailTarget found(accound): %s: %d",
                     account_id, et.email_target_id)
    except Errors.NotFoundError:
        et.populate(constants.email_target_account, entity_id=int(account_id),
                    entity_type=constants.entity_account)
        et.write_db()
        logger.debug("EmailTarget created: %s: %d",
                     account_id, et.email_target_id)
    # yrt

    try:
        ea.find_by_address(addr)
        logger.debug("EmailAddress found: %s: %d", addr, ea.email_addr_id)
    except Errors.NotFoundError:
        ea.populate(lp, edom.email_domain_id, et.email_target_id)
        ea.write_db()
        logger.debug("EmailAddress created: %s: %d", addr, ea.email_addr_id)
    # yrt

    if type == "defaultmail":
        try:
            epat.find(et.email_target_id)
            logger.debug("EmailPrimary found: %s: %d",
                         addr, epat.email_target_id)
        except Errors.NotFoundError:
            if ea.email_addr_target_id == et.email_target_id:
                epat.clear()
                epat.populate(ea.email_addr_id, parent=et)
                epat.write_db()
                logger.debug("EmailPrimary created: %s: %d",
                             addr, epat.email_target_id)
            else:
                logger.error("EmailTarget mismatch: ea: %d, et: %d", 
                             ea.email_addr_target_id, et.email_target_id)
            # fi
        # yrt
    # fi
    
    et.clear()
    ea.clear()
    edom.clear()
    epat.clear()
# end process_mail



def usage():
    print """Usage: import_uname_mail.py
    -v, --verbose : Show extra information. Multiple -v's are allowed
                    (more info).
    -f, --file    : File to parse.
    """
# end usage



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
    db.cl_init(change_program='import_uname_mail')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    person = Factory.get('Person')(db)

    fnr2person_id = dict()
    for p in person.list_external_ids(id_type=constants.externalid_fodselsnr):
        fnr2person_id[p['external_id']] = p['person_id']
    # od

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    group.find_by_name(cereconf.INITIAL_GROUPNAME)
    default_group_id = group.entity_id
    process_line(infile)

    attempt_commit()
# end main





if __name__ == '__main__':
    main()
# fi
