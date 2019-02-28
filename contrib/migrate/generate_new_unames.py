#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011 University of Oslo, Norway
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
This script creates new user names for newly imported persons with
unsuitable usernames. We require that the persons names are
registered and that the old usernames are reserved and stored as
external ids with system_migrate as source.

There is an option for writing a mapping with a new and old username
mapping.

NB! This script should only be used during migration.

"""

import getopt
import sys

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

## Globals
db = Factory.get('Database')()
db.cl_init(change_program='fix_unames')
account = Factory.get('Account')(db)
init_account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
constants = Factory.get('Constants')(db)
logger = Factory.get_logger("console")


def attempt_commit(dryrun=False):
    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Committed all changes")


def usage(msg=''):
    if msg:
        print msg
    print """Usage     : generate_new_unames.py
    -w, --write-mapping: write mapping of new -> old usernames
    -m, --maxlen       : Maxlen of usernames must be given
    -d, --dryrun       : Rollback after run.
    """
    sys.exit(0)


def create_accounts(maxlen):
    logger.info("Fetching all account names registered as not aceptable.")

    init_account.clear()
    init_account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)

    # person_id -> {'fnr': <fnr>, 'old': <old uname>, 'new': <new uname>} 
    personinfo = dict() 
    for p in person.search_external_ids(source_system=constants.system_migrate,
                                        id_type=constants.externalid_fodselsnr,
                                        entity_type=constants.entity_person,
                                        fetchall=False):
        personinfo.setdefault(int(p['entity_id']), {'fnr': p['external_id']})

    for p in person.search_external_ids(source_system=constants.system_migrate,
                                        id_type=constants.externalid_uname,
                                        entity_type=constants.entity_person,
                                        fetchall=False):
        person.clear()
        person.find(p['entity_id'])

        try:
            fn = person.get_name(constants.system_migrate, constants.name_first)
            ln = person.get_name(constants.system_migrate, constants.name_last)
        except Errors.NotFoundError:
            logger.warn("Could not find name for %s, skipping.", p['entity_id'])
            continue

        tmp = account.suggest_unames(constants.account_namespace,
                                     fn, ln, maxlen=maxlen)
        
        account.clear()
        account.populate(tmp[0], constants.entity_person,
                         p['entity_id'], None,
                         init_account.entity_id, None)
        account.write_db()

        u = personinfo.setdefault(int(p['entity_id']), {})
        u['old'] = p['external_id']
        u['new'] = tmp[0]
        
        logger.debug("New account: %s -> %s (%s %s)", p['external_id'], tmp[0], fn, ln)

    return personinfo


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'dw:m:',
                                   ['write-mapping=', 'maxlen=', 'dryrun'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    mapping_file = None
    maxlen = 0
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-w', '--write-mapping'):
            mapping_file = val
        elif opt in ('-m', '--maxlen'):
            maxlen = int(val)
        else:
            usage()

    if not maxlen:        
        usage("Max length of usernames not given.")
        
    personinfo = create_accounts(maxlen)

    if mapping_file:
        of = file(mapping_file, 'w')
        for v in personinfo.itervalues():
            of.write('%s;%s;%s\n' % (v.get('fnr',''), v.get('old',''),
                                     v.get('new','')))
        of.close()
        
    attempt_commit(dryrun)


if __name__ == '__main__':
    main()
