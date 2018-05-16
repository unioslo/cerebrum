#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
This file is a migration-specific extension to Cerebrum and should
be used with extreme caution as it changes passwords for all accounts
registered in Cerebrum.

"""

import getopt
import sys

import cerebrum_path
from Cerebrum.Utils import Factory


def attempt_commit():
    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")

def usage():
    print """Usage: set_pwds.py
    -d, --dryrun  : Rollback after run.
    -a, --active  : don't set password for accounts with active password
    """
    sys.exit(0)


def main():
    global db
    global dryrun, logger

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'ad',
                                   ['active', 'dryrun'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    active = False
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-a', '--active'):
            active = True
        else:
            usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='set_pwds')
    account = Factory.get('Account')(db)

    # Register accounts with an active password
    active_accounts = {}
    if active:
        for row in account.list_account_authentication():
            if not row['auth_data'] == None:
                active_accounts[int(row['account_id'])] = True

    for a in account.list(filter_expired=False):
        if active_accounts.has_key(a['account_id']):
            continue        
        account.clear()
        account.find(a['account_id'])
        pwd = account.make_passwd(account.account_name)
        account.set_password(pwd)
        account.write_db()
        logger.info("New password for %s", account.account_name)

    attempt_commit()


if __name__ == '__main__':
    main()
