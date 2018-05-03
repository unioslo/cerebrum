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
import os

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
        line = line.strip()
        logger.debug5("Processing line: |%s|", line)

        fields = line.split(":")
        if len(fields) != 7:
            logger.error("Bad line: %s. Skipping", line)
            continue
        
        uname = fields[0]
        path = fields[5]
        if uname == "":
            logger.warn("No username: %s. Skipping", line)
            continue
        
        account.clear()
        try:
            account.find_by_name(uname)
            logger.debug3("User %s exists in Cerebrum", uname)
        except Errors.NotFoundError:
            logger.warn("User %s does not exist in Cerebrum", uname)
            continue

        odisk_id = ohome = ohomedir_id = None
        try:
            tmp = account.get_home(spread)
        except Errors.NotFoundError:
            pass
        else:
            odisk_id = tmp['disk_id']
            ohome = tmp['home']
            ohomedir_id = tmp['homedir_id']
            
        (disk_id, home) = process_home(path, uname)
        if odisk_id != disk_id or ohome != home:
            try:
                homedir_id = find_home(account, disk_id, home)
            except Errors.NotFoundError:
                homedir_id = account.set_homedir(disk_id=disk_id, home=home,
                                                 status=co.home_status_not_created)
                logger.debug("Creating new homedir %s on %s:%s",
                             path, disk_id, home)
                
            account.set_home(spread, homedir_id)
            account.write_db()
            logger.info("User %s got new home %s on %s:%s", uname, path,
                        disk_id, home)
        
        # Handle spread
        if not account.has_spread(spread):
            account.add_spread(spread)
            account.write_db()
            logger.info("Added spread %s for user %s", spread, uname)

        if commit_count % commit_limit == 0:
            attempt_commit()


def set_home(account, disk_id, home):
    try:
        homedir_id = find_home(account.disk_id, home)
    except Errors.NotFoundError:
        homedir_id = account.set_homedir(disk_id=disk_id, home=home,
                                         status=co.home_status_not_created)
    account.set_home(spread, homedir_id)
    

def find_home(account, disk_id, home):
    for h in account.get_homes():
        if h['home'] == home and h['disk_id'] == disk_id:
            return h['homedir_id']
    raise Errors.NotFoundError

def split_disk_home(opath):
    """Suggest a (disk_id, home) for this path"""
    disk.clear()
    end = []
    path = opath
    while True:
        (path, dir) = os.path.split(path)
        end.insert(0, dir)
        if path == "/":
            return (None, opath)
        try:
            disk.find_by_path(path)
            return (disk.entity_id, os.path.join(*end))
        except Errors.NotFoundError:
            pass

def create_disk(opath):
    """Create a directory at the most likely place"""
    (path, dir) = os.path.split(opath)
    disk.clear()
    disk.populate(host.entity_id, path, "A disk")
    disk.write_db()
    logger.info("Disk %s created in Cerebrum", path)
    

def process_home(path, uname):
    """Find (or create) a disk for path. Return (disk_id, home)"""
    (disk_id, home) = split_disk_home(path)
    if disk_id is None and make_disk:
        create_disk(path)
        (disk_id, home) = split_disk_home(path)
    if home == uname:
        home = None
    return (disk_id, home)

    
def usage():
    print """Usage: import_homes.py
    -h, --help   : Show this
    -d, --dryrun : Fake run
    -f, --file   : File to parse.
    -s, --spread : spread
    -h, --host   : create new disks on this host
    """
    sys.exit(0)



def main():
    global db, co, account, default_creator_id
    global disk, spread, host, dryrun, logger, make_disk

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
    make_disk = False
    infile = given_host = given_spread = None
    
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-h', '--host'):
            given_host = val
        elif opt in ('-s', '--spread'):
            given_spread = val

    if not infile or not given_spread:
        usage()

    db = Factory.get('Database')()
    db.cl_init(change_program='import_homes')
    co = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    disk = Factory.get('Disk')(db)
    host = Factory.get('Host')(db)

    # Find host
    if given_host:
        make_disk = True
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
