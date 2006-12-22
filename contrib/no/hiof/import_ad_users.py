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
* set homedir?
* Check (and set) affiliation? 

"""

import getopt
import sys

import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory


# Globals
SPREAD_PREFIX = 'spread_ad_account_' 



def attempt_commit():
    if dryrun:
        db.rollback()
        logger.debug("Rolled back all changes")
    else:
        db.commit()
        logger.debug("Committed all changes")



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
            tmp = line.split(';')
            uname, homedir = [x.strip() for x in tmp[0].split(':')]
            ou, domain = process_ou_dc(tmp[1].split(','))
            spread = SPREAD_PREFIX + domain
        except:
            logger.warn("Suspicious line: %s" % line)
            continue

        if not homedir:
            logger.warn("No homedir given")
            continue

        # søppel som må strippes vekk
        if homedir.endswith('$'):
            homedir = homedir[:-1]

        process_user(uname, homedir, spread, ou, domain)

        if commit_count % commit_limit == 0:
            attempt_commit()

    stream.close()


def process_ou_dc(ou_dc_list):
    """
    Return the relevant OU and domain information. 
    """
    ou = []
    dc = []
    for x in ou_dc_list:
        if x.startswith('OU='):
            ou.append(x.split('=')[1])
        if x.startswith('DC='):
            dc.append(x.split('=')[1])
    # Most significant OU is last in the list. Reverse before joining
    # to string.
    ou.reverse()
    return '/'.join(ou), dc[0]


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

    ## TBD: What to to with OU for users in adm domain? It is not defined
    account.populate_trait(constants.trait_ad_account_ou, strval=ou)
    logger.debug("OU trait (%s) for account %s is set" % (ou, uname))

    try:
        spread = getattr(constants, spread)
    except AttributeError:
        logger.error("No spread %s defined" % spread)
        return
    
    disk_id = process_home(homedir)
    if not disk_id:
        return

    homedir_id = account.set_homedir(disk_id=disk_id,
                                     status=constants.home_status_not_created)
    account.set_home(spread, homedir_id)
    account.write_db()
    logger.debug3("User %s got new home %s", uname, homedir)

    # Create Profile path and set trait
    if domain == 'adm':
        profile_path = homedir + '\\profile'
    else:
        profile_path = homedir.replace('\\home\\', '\\profile\\')
    account.populate_trait(constants.trait_ad_profile_path, strval=profile_path)


def process_home(homedir):
    """
    Get disk from homedir and create disk if it does not exist.
    return disk_id.
    """

    path = '\\'.join(homedir.split('\\')[:-1])
    try:
        disk.clear()
        disk.find_by_path(path)
        logger.debug3("disk %s exists in Cerebrum", path)
        return disk.entity_id
    except Errors.NotFoundError:
        logger.debug4("Disk %s not found.", path)

    # get host
    host_name = homedir.lstrip('\\').split('\\')[0]
    if not host_name.endswith('.hiof.no'):
        host_name += '.hiof.no'
    host.clear()
    try:
        host.find_by_name(host_name)
    except Errors.NotFoundError:
        logger.error("Couldn't find host %s" % host_name)
        return None
    
    disk.populate(host.entity_id, path, "A disk")
    disk.write_db()
    logger.debug3("Disk %s created in Cerebrum", path)
    return disk.entity_id


def usage():
    print """Usage: import_uname_mail.py
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

    if infile is None:
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

