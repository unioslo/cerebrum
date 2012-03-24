#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2012 University of Oslo, Norway
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
"""This script produces a dump of all new accounts' usernames and their
plaintext passwords, and another dump with those who have changed their
password. This is not a recommended way of "syncing" passwords for an instance,
but it is unfortunately necessary if some systems doesn't handle automatic syncs
yet.

The format for both the dump files are:

    username;full_name;password

Note that passwords could contain semi colons themselves. You can expect that
usernames do not contain semi colons, but if a name contains a semi colon, it
will be substituted by a colon (:). TODO: what's the best solution for semi
colons in names?
"""

import sys
import getopt
from mx.DateTime import now, DateTimeDeltaFromSeconds

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
logger = Factory.get_logger("cronjob")

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)


def usage(exitcode=0):
    print """Usage: dump_usernames_passwords.py [options]

    %(doc)s

    --spreads SPREAD        If set, accounts without any of the given spreads
                            are ignored. Can be a comma separated list.

    --create_file FILE      Where to put the CSV file with all new accounts.

    --pwd_file FILE         Where to put the CSV file with accounts that has
                            changed their passwords.

    --hours HOURS           The number of hours back we should check for
                            changes. Default: 24

    -h --help               Show this and quit.
    """ % {'doc': __doc__}
    sys.exit(exitcode)

def process_accounts(event_types, stream, since, spreads):
    """Go through the change log for new events of the given type, and dump out
    the affected accounts to the stream."""
    entities = set(row['subject_entity'] for row in db.get_log_events(types=event_types, sdate=since))
    logger.debug("Fond %d entities in change_log", len(entities))
    for e_id in entities:
        ac.clear()
        try:
            ac.find(e_id)
        except Errors.NotFoundError, e:
            logger.info("Unknown account for entity_id: %s", e_id)
            continue
        if spreads and not any(ac.has_spread(s) for s in spreads):
            logger.debug("Ignoring %s due to missing spreads", ac.account_name)
            continue
        logger.debug("Processing: %s", ac.account_name)
        output(stream, ac)
    stream.close()

def output(stream, ac):
    """Get the needed data and put it into the stream."""
    out = [ac.account_name, get_name(ac)]
    try:
        out.append(ac.get_account_authentication(co.auth_type_plaintext))
    except Errors.NotFoundError, e:
        logger.warn("Could not find plaintext password for %s", ac.account_name)
        return False
    stream.write("%s\n" % ';'.join(out))
    return True

def get_name(ac):
    """Return the full name of an account. If the account is non-personal, its
    username is simply returned. Note that if the name contains semicolons,
    these will be substituted with colons."""
    if ac.owner_type != co.entity_person:
        return ac.account_name
    pe.clear()
    try:
        pe.find(ac.owner_id)
        name = pe.get_name(co.system_cached, co.name_full)
    except Errors.NotFoundError:
        logger.warn("%s: personal account, but no name?", ac.account_name)
        return ac.account_name
    if name.find(';') != -1:
        logger.info("%s: name '%s' contains semicolon, switch to colon",
                    ac.account_name, name)
        return name.replace(';', ':')
    return name

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h",
                                   ["help",
                                    "hours=",
                                    "spreads=",
                                    "create_file=",
                                    "pwd_file="])
    except getopt.GetoptError, e:
        print e
        usage(1)

    create_file = pwd_file = None
    since = now() - 1
    spreads = []

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
        elif opt in ('--create_file',):
            create_file = val
        elif opt in ('--pwd_file',):
            pwd_file = val
        elif opt in ('--hours',):
            since = now() - DateTimeDeltaFromSeconds(3600 * int(val))
        elif opt in ('--spreads',):
            spreads.extend(int(co.Spread(s)) for s in val.split(','))
        else:
            print "Unknown arg: %s" % opt
            usage(1)

    if create_file:
        logger.info("Start processing new accounts")
        process_accounts(co.account_create, open(create_file, 'w'), since,
                         spreads)
        logger.info("Processing of new accounts done")
    if pwd_file:
        logger.info("Start processing accounts with new passwords")
        process_accounts(co.account_password, open(pwd_file, 'w'), since,
                         spreads)
        logger.info("Processing of accounts with new passwords done")
    logger.info("All done")

if __name__ == "__main__":
    main()
