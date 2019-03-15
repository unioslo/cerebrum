#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

#
# This script reads data exported from our HR system PAGA.
# It is a simple CSV file.
#

#
# Generic imports
#
import os
import getopt
import sys

#
# Cerebrum imports
#
import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit.account_bridge import AccountBridge

#
# global variables
#
progname =__file__.split(os.sep)[-1]
logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
db.cl_init(change_program='sync_passwords')
ac = Factory.get('Account')(db)
co = Factory.get('Constants')(db)


#
# __doc__ (usage)
#
__doc__ = """
This script checks if password hashes are the same in the old and new 
Cerebrum databases (old on Caesar, new on Clavius). 
If they differ the hashes on Caesar are copied to Clavius.

usage: %s <-a | -n username | -f filename>

options:
    -h | --help             - this text
    -a | --all              - sync passwords for all accounts
    -f | --file filename    - read usernames from file and sync passwords for them
    -n username | --name username 
                            - sync passwords for one account, identified with username
    -d | --dryrun           - do not change DB
""" % progname

def sync_one_account(bridge, uname):
    auth_data = bridge.get_auth_data(uname)
    if auth_data == None:
        logger.warning("Couldn't find account with username '%s' in Caesar database, ignoring it." % uname)
        return

    # get auth data from new database
    ac.clear()
    ac.find_by_name(uname)

    # logger.debug("############ %s ############" % uname)

    first = True
    equal = True
    # compare auth data from the two databases, logg if differences
    for ad in auth_data:
        auth_method, caesar_data = ad

        # don't compare auth_data for auth methods that aren't in use
        if str(co.Authentication(auth_method)) not in cereconf.AUTH_CRYPT_METHODS:
            continue

        try:
            clavius_data = ac.get_account_authentication(auth_method)
        except Errors.NotFoundError:
            # this authentication method is not in clavius db for this account,
            # ignore it
            continue

        if not caesar_data == clavius_data:
            if first == True:
                logger.debug("############ %s has auth_data that differs ############" % uname)
                first = False
                equal = False

            logger.debug("type: %s" % auth_method)
            logger.debug("hash from Caesar: %s" % caesar_data)
            logger.debug("hash from Clavius: %s" % clavius_data)
            logger.debug("#####")
    if not equal:
        logger.debug("######################################################")

    # Note: all auth_data from Caesar is written to Clavius, regardless of what type it is.

    # update auth_data in Clavius database with auth_data from Caesar
    ac.set_auth_data(auth_data)
    ac.write_db()

def sync_from_file(bridge, filename):
    # read usernames from file
    with open(filename, "r") as fh:
        unames = fh.readlines()

    # sync passwords for these usernames
    for uname in unames:
        if uname[0] != '\n':
            # line is not empty
            sync_one_account(bridge, uname.rstrip())

def sync_all(bridge):
    all_accounts = ac.list_all(filter_expired=False)
    for acc in all_accounts:
        sync_one_account(bridge, acc['entity_name'])

def main():
    do_all = False
    filename = None
    uname = None
    dryrun = False

    try:
        opts,args=getopt.getopt(sys.argv[1:],'haf:n:d',['help','all','file=','name=','dryrun'])
    except getopt.GetoptError,m:
        logger.error("Unknown option: %s" % (m))
        usage(m)

    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        if opt in ('-a','--all'):
            do_all = True
        if opt in ('-f','--file'):
            filename = val
        if opt in ('-n','--name'):
            uname = val
        if opt in ('-d','--dryrun'):
            dryrun = True

    with AccountBridge() as bridge:
        if uname:
            sync_one_account(bridge, uname)
        elif filename:
            if (os.path.exists(filename) != True):
                msg = "File %s seems to be missing" % filename
                usage(msg)
            sync_from_file(bridge, filename)
        elif do_all:
            sync_all(bridge)
        else:
            usage()

    if dryrun:
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")

def usage(message=None):
    if message:
        print message
    print __doc__
    sys.exit(1)

if __name__ == '__main__':
    main()
