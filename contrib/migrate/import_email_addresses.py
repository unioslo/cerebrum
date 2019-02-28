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

##
## TODO: This script only works for import file with old usernames
## stored as external_id. Fix this!
## 


import getopt
import sys

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


def process_line(infile, spread, sepchar, homemdb):
    """
    Scan all lines in INFILE and create corresponding account/e-mail entries
    in Cerebrum.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000
    mdb = None

    # Iterate over all persons:
    for line in stream:
        commit_count += 1
        logger.debug5("Processing %s", line.strip())

        fields = [l.strip() for l in line.split(sepchar)]
        if len(fields) < 2:
            logger.error("Bad line, less than two values: %s." % line)
            continue

        if homemdb and len(fields) != 4:
            logger.error("Bad line, mdb and not 4 values: %s." % line)
            continue
        
        # if no mtype is given assume that the address should be registered
        # as default/primary address for account
        if len(fields) == 2:
            mtype = 'defaultmail'
            uname, addr = fields

        if len(fields) == 3:
            uname, mtype, addr = fields

        if len(fields) == 4:
            uname, mdb, mtype, addr = fields

        if uname == "":
            logger.error("No uname given. Skipping!")
            continue

        account = get_account(uname, external_id=extid)
        if account:
            if mdb:
                process_mail(account, mtype, addr, spread=spread, homemdb=mdb)
            else:
                process_mail(account, mtype, addr, spread=spread)

        if commit_count % commit_limit == 0:
            attempt_commit()


def get_account(uname, external_id=False):
    if external_id:
        try:
            person.clear()
            person.find_by_external_id(constants.externalid_uname, uname)
            # this is not the most robust code, but it should work for all
            # person objects available at this point
            tmp = person.get_accounts()
            if len(tmp) == 0:
                logger.warn("Skipping, no valid accounts found for '%s'" % uname)
                return
            account_id = int(tmp[0]['account_id'])
            account.clear()
            account.find(account_id)
            logger.info("Found account '%s' for user with external name '%s'",
                        account.account_name, uname)
            return account
        except Errors.NotFoundError:
            logger.warn("Didn't find user with external name '%s'" % uname)
            return
    account.clear()
    try:
        account.find_by_name(uname)
    except Errors.NotFoundError:
        logger.error("Didn't find account '%s'!", uname)
        return
    logger.debug("found account %s", uname)
    return account

def process_mail(account, mtype, addr, spread=None, homemdb=None):
    et = Email.EmailTarget(db)
    ea = Email.EmailAddress(db)
    edom = Email.EmailDomain(db)
    epat = Email.EmailPrimaryAddressTarget(db)

    addr = addr.lower()
    account_id = account.entity_id

    fld = addr.split('@')
    if len(fld) != 2:
        logger.error("Bad address: %s. Skipping", addr)
        return None
    
    lp, dom = fld
    try:
        edom.find_by_domain(dom)
    except Errors.NotFoundError:
        logger.error("Domain non-existent: %s", lp + '@' + dom)
        return None

    try:
        et.find_by_target_entity(int(account_id))
    except Errors.NotFoundError:
        et.populate(constants.email_target_account,
                    target_entity_id=int(account_id),
                    target_entity_type=constants.entity_account)
        et.write_db()
        logger.debug("EmailTarget created: %s: %d", account_id, et.entity_id)

    try:
        ea.find_by_address(addr)
    except Errors.NotFoundError:
        ea.populate(lp, edom.entity_id, et.entity_id)
        ea.write_db()
        logger.debug("EmailAddress created: %s: %d", addr, ea.entity_id)
        # if specified, add an email spread for users with email address
        if spread and not account.has_spread(spread):
            account.add_spread(spread)
            logger.debug("Added spread %s for account %s", spread, account_id)

    if mtype == "defaultmail":
        try:
            epat.find(et.entity_id)
            logger.debug("EmailPrimary found: %s: %d",
                         addr, epat.entity_id)
        except Errors.NotFoundError:
            if ea.email_addr_target_id == et.entity_id:
                epat.clear()
                epat.populate(ea.entity_id, parent=et)
                epat.write_db()
                logger.debug("EmailPrimary created: %s: %d",
                             addr, epat.entity_id)
            else:
                logger.error("EmailTarget mismatch: ea: %d, et: %d", 
                             ea.email_addr_target_id, et.entity_id)
        if homemdb:
            logger.info("Added exchange-mbd %s\n", homemdb)
            account.populate_trait(constants.trait_exchange_mdb, strval=homemdb)
            account.write_db()

    
    et.clear()
    ea.clear()
    edom.clear()
    epat.clear()


def usage():
    print """Usage: import_uname_mail.py
    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    -s, --spread  : add spread to account (optional)
    -m, --homemdb : add homeMDB as trait
    -e, --extid  : check for account by external_id 
    """
    sys.exit(0)


def main():
    global db, constants, account, person, fnr2person_id
    global default_creator_id, default_group_id
    global dryrun, logger, extid

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:s:c:edm',
                                   ['file=',
                                    'spread=',
                                    'sepchar=',
                                    'homemdb',
                                    'extid'
                                    'dryrun'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    spread = None
    sepchar = ":"
    homemdb = False
    extid = False
    
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-s', '--spread'):
            spread = val
        elif opt in ('-c', '--sepchar'):
            sepchar = val
        elif opt in ('-m', '--homemdb'):
            homemdb = True
        elif opt in ('-e', '--extid'):
            extid = True

    if infile is None:
        usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='import_mail')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    person = Factory.get('Person')(db)

    fnr2person_id = dict()
    for p in person.search_external_ids(id_type=constants.externalid_fodselsnr,
                                        fetchall=False):
        fnr2person_id[p['external_id']] = p['entity_id']

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    group.find_by_name(cereconf.INITIAL_GROUPNAME)
    default_group_id = group.entity_id

    if spread:
        try:
            spread = getattr(constants, spread)
        except AttributeError:
            logger.error("No spread %s defined", spread)

    process_line(infile, spread, sepchar, homemdb)

    attempt_commit()





if __name__ == '__main__':
    main()
