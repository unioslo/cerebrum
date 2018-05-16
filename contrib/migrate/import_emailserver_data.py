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
This file contains code which imports historical e-mail data into Cerebrum.
Normally, it should be run only once (about right after the database has been
created).

The input format for this job is a file with one line per
account/e-mail. Each line has four fields separated by ';'.

<uname>;<uname@server>

... where

uname   -- account name
server  -- email server account is registered at
"""

import getopt
import sys
import string

import cerebrum_path
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
    # fi
# end attempt_commit



def process_line(infile):
    """
    Scan all lines in INFILE and create corresponding account/e-mail entries
    in Cerebrum.
    """

    stream = open(infile, 'r')
    commit_count = 0
    commit_limit = 1000

    # Iterate over all persons:
    for line in stream:
        commit_count += 1
        logger.debug5("Processing: %s", line.strip())

        fields = string.split(line.strip(), ";")
        foo, server = string.split(fields[1], '@')
        if len(fields) != 2:
            logger.error("Bad line: %s" % line)
            continue
        # fi
        
        uname, bar = fields
	account_id = process_user(uname)
        if account_id:
            process_email_srv_data(uname, account_id, server)
        else:
            logger.error("Bad uname: %s", line)
        # fi

        if commit_count % commit_limit == 0:
            attempt_commit()
        # fi
    # od
# end process_line


def process_user(uname):
    """
    Locate account_id of account UNAME owned by OWNER_ID.
    """
    if uname == "":
        return None
    # fi
    
    try:
        account.clear()
        account.find_by_name(uname)
    except Errors.NotFoundError:
	return
    a_id = account.entity_id
    return a_id
# end process_user


def process_email_srv_data(uname, account_id, email_srv):
    if email_srv in ['NOMAIL', 'NOLOCAL']:
        logger.error("Bad email server %s for %s", email_srv, uname)
        return None
    email_server = Email.EmailServer(db)
    email_server_target = Email.EmailServerTarget(db)
    email_target = Email.EmailTarget(db)
    email_server.find_by_name(email_srv)
    email_server_id = email_server.entity_id
    try:
        email_target.find_by_email_target_attrs(target_entity_id=int(account_id))
    except Errors.NotFoundError:
        logger.error("No email target for %s", uname)
        return None
    try:
        email_server_target.find(email_target.entity_id)
        logger.debug("Email-server is registered %s for %s", email_srv, uname)
    except Errors.NotFoundError:
        email_server_target.clear()
        email_server_target.populate(email_server_id, parent=email_target)
        email_server_target.write_db()
        logger.debug("Populated email-server %s for %s", email_srv, uname)

    email_server.clear()
    email_server_target.clear()
    email_target.clear()
    

def usage():
    print """Usage: import_uname_mail.py
    -d, --dryrun  : Run a fake import. Rollback after run.
    -f, --file    : File to parse.
    """
    sys.exit(0)
# end usage


def main():
    global db, constants, account, person, fnr2person_id
    global default_creator_id, default_group_id
    global dryrun, logger

    logger = Factory.get_logger("console")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:d',
                                   ['file=',
                                    'dryrun'])
    except getopt.GetoptError:
        usage()
    # yrt

    dryrun = False
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-f', '--file'):
            infile = val
        # fi
    # od

    if infile is None:
        usage()
    # fi

    db = Factory.get('Database')()
    db.cl_init(change_program='import_uname')
    constants = Factory.get('Constants')(db)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    person = Factory.get('Person')(db)

    fnr2person_id = dict()
    for p in person.list_external_ids(id_type=constants.externalid_fodselsnr):
        fnr2person_id[p['external_id']] = p['entity_id']
    # od

    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    group.find_by_name(cereconf.INITIAL_GROUPNAME)
    default_group_id = group.entity_id
    process_line(infile)

    attempt_commit()
# end main


if __name__ == '__main__':
    main()
# fi
