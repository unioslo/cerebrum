#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009, 2010, 2012 University of Oslo, Norway
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
"""This script removes all traces of a given account from the cerebrum
database. Use this script with extreme caution! The process can not be undone!

The script asks you to verify if you really want to delete the accounts at the
end of its run. You have to both specify --commit and answer 'y' to this
before the accounts are terminated.

Improvements: - add some options to allow removal of some
                account attributes only?

"""

import cereconf

import os
import sys
import getopt

from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules import Email

logger = Factory.get_logger("console")

def usage(errorcode = 0, message = None):
    if message:
        print "%s\n" % message
    print """Usage: %(script)s [--accounts ACCOUNTS] [--commit]

    %(doc)s

    -a, --accounts      Accounts to terminate/delete from the db. Could be a
                        comma separated list.

    -f, --file FILE     Add accounts from a given file.

        --commit        Commit the changes, i.e. really delete the accounts.

    -h, --help          Show this information and quit.

    Please note that some of the account data should be removed through bofh,
    e.g. by user_demote_posix. Some instances makes for instance use of
    BofhdRequest for backing up the user's home disk.
    """ % {'script': os.path.basename(sys.argv[0]),
           'doc': __doc__}
    sys.exit(errorcode)

def has_remains(db, entity_id):
    """Check the database for if the entity is still there. This is to double
    check that the termination process actually works.
    """
    for row in db.query('''SELECT * from entity_info 
                           WHERE entity_id = :e_id''',
                        {'e_id': entity_id}):
        logger.error("Entity %d still exists in entity_info" % entity_id)
        return True
    for row in db.query('''SELECT * from change_log
                           WHERE subject_entity = :e_id''',
                        {'e_id': entity_id}):
        logger.error("Entity %d still exists in change_log" % entity_id)
        return True
    return False

def main():
    db = Factory.get("Database")()
    db.cl_init(change_program='terminate_accounts')
    account = Factory.get("Account")(db)
    constants = Factory.get("Constants")(db)

    dryrun = True
    accounts = []
    terminated_entities = []

    try:
        opts, args = getopt.getopt(sys.argv[1:], 
                             'hf:a:',
                            ('help',
                             'file=',
                             'accounts=',
                             'commit'))
    except getopt.GetoptError, e:
        usage(1, e)
    
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-f', '--file'):
            accounts.extend(u.strip() for u in open(val, 'r'))
        elif opt in ('-a', '--accounts'):
            accounts.extend(val.split(','))
        elif opt in ('--commit',):
            dryrun = False
        else:
            usage(1)

    if not accounts:
        usage(1, "No accounts specified")

    logger.info("Accounts to be processed: %d" % len(accounts))
    logger.info("Processing accounts...")
    for a in accounts:
        logger.info("Processing account: %s", a)
        account.clear()
        try:
            account.find_by_name(a)
        except Errors.NotFoundError, e:
            # account_name not found, check if it is an entity_id
            logger.debug("Unkown account_name '%s', trying entity_id" % a)
            if not a.isdigit():
                raise e
            account.find(a)

        logger.info('Terminating account: %s' % account.account_name)
        ent_id = account.entity_id
        name = account.account_name
        account.terminate()
        # Double check that it is actually deleted:
        if has_remains(db, ent_id):
            raise Exception('Found remainings of %s in db, check code' % name)
        terminated_entities.append(ent_id)

    ret = raw_input('Is this correct? Really delete the given accounts? (y/N) ')
    ret = ret in ('y', 'yes')
    if dryrun or not ret:
        db.rollback()
        logger.info("Rolled back changes, use --commit to actually delete them")
    else:
        db.commit()
        logger.info("Changes committed")

        # Double checking after commit:
        for e_id in terminated_entities:
            if has_remains(db, e_id):
                logger.error("Found remainings for entity %d in db" % e_id)

    logger.info("Terminator done")

if __name__ == '__main__':
    main() 
