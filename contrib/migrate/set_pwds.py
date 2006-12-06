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
This file is a migration-specific extension to Cerebrum and should
be used with extreme caution as it changes passwords for all accounts
registered in Cerebrum.

"""

import getopt
import sys
import string

import cerebrum_path
import cereconf

from Cerebrum import Errors
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
    """
    sys.exit(0)


def main():
    global db
    global dryrun, logger

    all_accounts = {}

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'd',
                                   ['dryrun'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        else:
            usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='set_pwds')
    account = Factory.get('Account')(db)

    all_accounts = account.list(filter_expired=False)

    for a in all_accounts:
        account.clear()
        account.find(a['account_id'])
        pwd = account.make_passwd(account.account_name)
        account.set_password(pwd)
        account.write_db()
        logger.info("New password for %s", account.account_name)

    attempt_commit()


if __name__ == '__main__':
    main()
