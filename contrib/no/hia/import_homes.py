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
This file is a HiA-specific extension of Cerebrum. It contains code which
import historical account and e-mail data from HiA into Cerebrum. Normally,
it should be run only once (about right after the database has been
created).

The input format for this job is a file with one line per
account/e-mail. Each line has four fields separated by ':'.

<no_ssn>:<uname>:<uname>:<uid>:<gid>:<gecos>:<home>:<shell>
"""

import getopt
import sys
import string
import re

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.no import fodselsnr





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
    Scan all lines in INFILE and set password for user in Cerebrum.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000

    # Iterate over all persons:
    for line in stream:
        commit_count += 1
        logger.debug5("Processing line: |%s|", line)

        fields = string.split(line.strip(), ":")
        if len(fields) != 8:
            logger.error("Bad line: %s. Skipping", line)
            continue
        # fi
        
        uname = fields[1]
        home = fields[6]
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
            account.set_home(co.spread_nis_user, home=home,
                             status=co.home_status_on_disk)
            logger.debug("User %s got home %s.", uname, home)
            account.write_db()                
            continue
        try:
            disk_id, home, status = account.get_home(co.spread_nis_user)
            logger.debug("User %s got home %s, %s, %s.", uname, disk_id,
                         home, status)
        except Errors.NotFoundError:
            account.set_home(co.spread_nis_user, disk_id=disk_id,
                             status=co.home_status_on_disk)
            account.write_db()
            logger.debug3("User %s got new home %s", uname, home)
            
        if commit_count % commit_limit == 0:
            attempt_commit()
        # fi
    # od
# end process_line

    
def process_home(home):
    """
    Return a disk_id..
    """

    # /adh/ugle/u2/knutaa
    
    if rm_str:
        home = re.sub(rm_str, '', home)

    fields = string.split(home.strip(), "/")
    if len(fields) != 4:
        return None
    # fi

    machine = fields[1]
    disk_name = fields[2]
    path = "/hia/%s/%s" % (machine, disk_name)
    try:
        disk.clear()
        disk.find_by_path(path)
        logger.debug3("disk %s exists in Cerebrum", path)
        return disk.entity_id
    except Errors.NotFoundError:
        logger.debug4("Disk %s not found.", path)
    #yrt

    # If we get here. Disk isn't found. Try machine first.
    try:
        host.clear()
        host.find_by_name(machine)
        logger.debug3("Host %s exists in Cerebrum", machine)
    except Errors.NotFoundError:
        host.populate(machine, "A machine")
        host.write_db()
        logger.debug3("Host %s created in Cerebrum", machine)
    # yrt

    disk.populate(host.entity_id, path, "A disk")
    disk.write_db()
    logger.debug3("Disk %s created in Cerebrum", path)
    return disk.entity_id
    
# end process_home



def usage():
    print """Usage: import_crypt.py
    -v, --verbose : Show extra information. Multiple -v's are allowed
                    (more info).
    -f, --file    : File to parse.
    -r, --remove  : <string> to remove in front of path.
    """
    sys.exit(0)
# end usage



def main():
    global db, co, account, default_creator_id
    global rm_str, disk, host, dryrun, logger

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:dr:',
                                   ['file=',
                                    'remove=',
                                    'dryrun'])
    except getopt.GetoptError:
        usage()
    # yrt

    dryrun = False
    rm_str = None
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-r', '--remove'):
            rm_str = val
        # fi
    # od

    if infile is None:
        usage()
    # fi

    db = Factory.get('Database')()
    db.cl_init(change_program='import_homes')
    co = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    disk = Factory.get('Disk')(db)
    host = Factory.get('Host')(db)

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    process_line(infile)

    attempt_commit()
# end main





if __name__ == '__main__':
    main()
# fi

# arch-tag: dbceb7e4-7766-4852-8e32-d081bb9979da
