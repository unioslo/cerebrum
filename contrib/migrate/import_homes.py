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

This file contains code which purpose is to import historical account
data into Cerebrum. Normally, it should be run only once (about right
after the database has been created).

The input format for this job is a file with one line per
account. Each line has four fields separated by ':'.

<uname>:x:<uid>:<gid>:<gecos>:<home>:<shell>


Example of use:

./import_homes.py -h brage.hiof.no -f nisdomain-nis.it.ans.hiof.no-pwd-vasket.txt
-s spread_nis_ans_account

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
        logger.debug("Rolled back all changes")
    else:
        db.commit()
        logger.debug("Committed all changes")


def process_line(infile):
    """
    Scan all lines in INFILE and set password for user in Cerebrum.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000

    # Iterate over all users
    for line in stream:
        commit_count += 1
        line.strip()
        logger.debug5("Processing line: |%s|", line)

        fields = string.split(line, ":")
        if len(fields) != 7:
            logger.error("Bad line: %s. Skipping", line)
            continue
        
        uname = fields[0]
        home = fields[5]
        if uname == "":
            logger.warn("No username: %s. Skipping", line)
            continue
        
        account.clear()
        try:
            account.find_by_name(uname)
            logger.debug3("User %s exists in Cerebrum", uname)
        except Errors.NotFoundError:
            logger.warn("User %s does not exists in Cerebrum", uname)
            continue
        disk_id = process_home(home)
        if disk_id == None:
            logger.warn("User %s got strange home %s.", uname, home)
            account.write_db()                
            continue
        
        try:
            disk_id, home, status = account.get_home(spread)
            logger.debug("User %s got home %s, %s, %s.", uname, disk_id,
                         home, status)
        except Errors.NotFoundError:
            homedir_id = account.set_homedir(disk_id=disk_id,
                                             status=co.home_status_not_created)
            account.set_home(spread, homedir_id)
            account.write_db()
            logger.debug3("User %s got new home %s", uname, home)
            
        if commit_count % commit_limit == 0:
            attempt_commit()

    
def process_home(home):
    """
    Get disk from homedir and create disk if it does not exist.
    return disk_id.
    """
    
    fields = string.split(home.strip(), "/")

    path = '/'.join(home.split('/')[:-1])
    try:
        disk.clear()
        disk.find_by_path(path)
        logger.debug3("disk %s exists in Cerebrum", path)
        return disk.entity_id
    except Errors.NotFoundError:
        logger.debug4("Disk %s not found.", path)

    disk.populate(host.entity_id, path, "A disk")
    disk.write_db()
    logger.debug3("Disk %s created in Cerebrum", path)
    return disk.entity_id


def usage():
    print """Usage: import_homes.py
    -h, --help   : Show this
    -f, --file   : File to parse.
    -s, --spread : spread
    -h, --host   : host disks belongs to
    """
    sys.exit(0)



def main():
    global db, co, account, default_creator_id
    global disk, spread, host, dryrun, logger

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:h:s:d',
                                   ['file=',
                                    'host=',
                                    'spread=',
                                    'dryrun'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-h', '--host'):
            given_host = val
        elif opt in ('-s', '--spread'):
            given_spread = val

    if not infile or not given_spread or not given_host:
        usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='import_homes')
    co = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    disk = Factory.get('Disk')(db)
    host = Factory.get('Host')(db)

    # Find host
    try:
        host.find_by_name(given_host)
    except Errors.NotFoundError:
        logger.error("No host %s found" % given_host)
        sys.exit(1)

    # find spread
    try:
        spread = getattr(co, given_spread)
    except AttributeError:
        logger.error("No spread %s defined" % given_spread)
        sys.exit(2)

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    process_line(infile)

    attempt_commit()


if __name__ == '__main__':
    main()
