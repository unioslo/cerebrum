#!/usr/bin/env python
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
This file contains code which imports historical account and
e-mail data into Cerebrum. Normally, it should be run only
once (about right after the database has been created).

The input format for this job is a file with one line per
account/e-mail. Each line has three fields separated by ';'.

<uname>;<keyword>;<e-mail address>

... where

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
        logger.debug5("Processing %s", line)

        fields = string.split(line.strip(), ";")
        if len(fields) < 2:
            logger.error("Bad line: %s." % line)
            continue
        
        # if no type is given assume that the address should be registered
        # as default/primary address for account
        if len(fields) == 2:
            type = 'defaultmail'
            uname, addr = fields

        if len(fields) == 3:
            uname, type, addr = fields
        # fi
	account_id = process_user(uname)
        
        if account_id:
            process_mail(account_id, type, addr)
        else:
            logger.error("Bad uname: %s", uname)
        # fi

        if commit_count % commit_limit == 0:
            attempt_commit()
        # fi
    # od
# end process_line

def process_user(uname):
    """
    Locate account_id of account UNAME.
    """
    
    if uname == "":
        return None
    # fi
    
    try:
        account.clear()
        account.find_by_name(uname)
        logger.debug3("User %s exists in Cerebrum", uname)
    except Errors.NotFoundError:
	return
    a_id = account.entity_id
    return a_id
# end process_user



def process_mail(account_id, type, addr):
    et = Email.EmailTarget(db)
    ea = Email.EmailAddress(db)
    edom = Email.EmailDomain(db)
    epat = Email.EmailPrimaryAddressTarget(db)

    addr = string.lower(addr)    

    fld = addr.split('@')
    if len(fld) != 2:
        logger.error("Bad address: %s. Skipping", addr)
        return None
    # fi
    
    lp, dom = fld
    try:
        edom.find_by_domain(dom)
    except Errors.NotFoundError:
        logger.error("Domain non-existent: %s", lp + '@' + dom)
        return None
    # yrt

    try:
        et.find_by_entity(int(account_id))
    except Errors.NotFoundError:
        et.populate(constants.email_target_account, entity_id=int(account_id),
                    entity_type=constants.entity_account)
        et.write_db()
        logger.debug("EmailTarget created: %s: %d", account_id, et.email_target_id)
    # yrt

    try:
        ea.find_by_address(addr)
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
    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    """
    sys.exit(0)
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
    db.cl_init(change_program='import_uname')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    person = Factory.get('Person')(db)

    fnr2person_id = dict()
    for p in person.list_external_ids(id_type=constants.externalid_fodselsnr):
        fnr2person_id[p['external_id']] = p['entity_id']
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
