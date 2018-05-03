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
This file is a HiOf-specific extension of Cerebrum. It contains code which
import historical account data from HiOf into Cerebrum. Normally,
it should be run only once (about right after the database has been
created).

The input format for this job is a file with one line per
account on the format:

<uname>:<homedir>;OU=<OU>,...,DC=<domain>,...

Eksempel:

peraalve:\\olivia\peraalve$;OU=Ansatte Olivia,DC=adm,DC=hiof,DC=no
haraldh:\\fag.hiof.no\home\IT\haraldh;OU=IT,OU=Halden,OU=Ansatte,DC=fag,DC=hiof,DC=no


Tasks:

* check that the user found is known in Cerebrum
* set user <-> ou trait
* set user <-> profile-path trait
* set user <-> homedir trait

"""

## Note that the script don't care about earlier imported data.
## Previous data for the users imported will be overridden. Thus all
## AD users should be imported in the same session.

import getopt
import sys
import cPickle

import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory


# Globals
SPREAD_PREFIX = 'spread_ad_account_' 
USER_OU = {}
USER_HOME = {}
USER_PROFILE_PATH = {}


def attempt_commit():
    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")


def process_line(infile):
    """
    Scan all lines in INFILE, check the format and extract the
    relevant information.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000

    for line in stream:
        commit_count += 1
        line = line.strip()
        logger.debug5("Processing line: |%s|", line)

        try:
            uname, homedir, ou_dc = [x.strip() for x in line.split(';')]
            ou, domain = process_ou_dc(ou_dc)
            spread = SPREAD_PREFIX + domain
        except:
            logger.warn("Suspicious line: %s" % line)
            continue

        if not homedir:
            # Warn about missing homedir, but try to process user
            logger.warn("No homedir given for user " + uname)

        process_user(uname, homedir, spread, ou, domain)

        if commit_count % commit_limit == 0:
            attempt_commit()

    stream.close()


def process_ou_dc(ou_dc):
    """
    Return the relevant OU and domain information. 
    """
    ou = []
    dc = []
    for x in ou_dc.split(','):
        if x.startswith('OU='):
            ou.append(x)
        elif x.startswith('DC='):
            # We don't need DC=hiof,DC=no
            dc.append(x.split('=')[1])
        else:
            logger.warn("OU_DC data has wrong format: %s", ou_dc)
    return ','.join(ou), dc[0]


def process_user(uname, homedir, spread, ou, domain):
    """
    Check if given user exists in Cerebrum, and warn if not.
    If user exist register homedir. Set OU and profile path traits.
    """

    ## Note that we do not check if users have homedir, ou or profile
    ## path before setting them. This is an import script, so the data
    ## imported will override previous data.
    
    account.clear()
    try:
        account.find_by_name(uname)
    except Errors.NotFoundError:
        logger.warn("User %s not in Cerebrum" % uname)
        return

    try:
        spread = getattr(constants, spread)
    except AttributeError:
        logger.error("No spread %s defined" % spread)
        return
    
    # For each user store a dict of spread<->ou mappings. Pickle that
    # dict and set as trait.
    if not uname in USER_OU:
        USER_OU[uname] = {}
    USER_OU[uname][int(spread)] = ou
    account.populate_trait(constants.trait_ad_account_ou,
                           strval=cPickle.dumps(USER_OU[uname]))
    account.write_db()
    logger.debug("Set OU trait (%s:%s) for account %s." % (spread, ou, uname))

    ## Handle homedir.
    # PS! Homedir might not be given, i.e. homedir == ''
    if not uname in USER_HOME:
        USER_HOME[uname] = {}
    # We want the substring \\home of homedir to be lowercase, other
    # parts of the string should be allowed to be uppercase. Thus use
    # replace() instead of lower()
    if homedir:
        homedir = homedir.replace('\\Home', '\\home')
    USER_HOME[uname][int(spread)] = homedir
    account.populate_trait(constants.trait_ad_homedir,
                           strval=cPickle.dumps(USER_HOME[uname]))
    account.write_db()
    logger.debug("Set homedir trait (%s:%s) for account %s." % (spread, homedir, uname))

    ## Handle spread
    if not account.has_spread(spread):
        account.add_spread(spread)
        account.write_db()
        logger.debug("Added spread %s for user %s", spread, uname)

    ## Handle Profile path 
    # Homedir might not exist. In those cases set profile path to ''
    profile_path = ''
    if homedir:
        if domain == 'adm':
            profile_path = homedir + '\\profile'
        else:
            profile_path = homedir.replace('\\home\\', '\\profile\\')

    # Set trait of pickled spread<->profile_path mappings
    if not uname in USER_PROFILE_PATH:
        USER_PROFILE_PATH[uname] = {}
    USER_PROFILE_PATH[uname][int(spread)] = profile_path
    account.populate_trait(constants.trait_ad_profile_path,
                           strval=cPickle.dumps(USER_PROFILE_PATH[uname]))
    account.write_db()
    logger.debug("profile path (%s:%s) trait for account %s is set" % (
        spread, profile_path, uname))


def usage():
    print """Usage: import_ad_users.py
    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    """



def main():
    global db, constants, account, disk, host
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

    if not infile:
        usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='import_ad')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    disk = Factory.get('Disk')(db)
    host = Factory.get('Host')(db)
    
    process_line(infile)

    attempt_commit()



if __name__ == '__main__':
    main()
