#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2007 University of Oslo, Norway
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

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors

try:
    set()
except NameError:
    from sets import Set as set


db = Factory.get("Database")()
db.cl_init(change_program='range_priorities')
person = Factory.get("Person")(db)
account = Factory.get("Account")(db)
const = Factory.get("Constants")(db)
logger = Factory.get_logger("console")
all_accounts = {}

def range_priorities(affiliation=None, add_person_affiliations=False):
    old_account_types = {}
    new_account_types = {}

    logger.info("Getting all accounts")

    if affiliation:
        all_accounts = account.list_accounts_by_type(affiliation=affiliation)
    else:
        all_accounts = account.list(filter_expired=True)

    logger.info("Done getting all accounts")

    for ac in all_accounts:
        account.clear()
        account.find(int(ac['account_id']))
        logger.info("*******************START***********************************")
        logger.info("Found account |%s| for |%s|" % (account.account_name,
        						 account.owner_id))
    
        person.clear()
        try:
            person.find(account.owner_id)
        except Errors.NotFoundError, e:
            continue

        logger.info("Getting account types")

        old_account_types = account.get_account_types()
        old_pri={}
        for a in old_account_types:
            old_pri[int(a['ou_id']), int(a['affiliation'])] = a['priority']

        if add_person_affiliations:
            affiliations = person.get_affiliations()
        else:
            affiliations = old_account_types
        
        logger.info("Rearranging priorities for |%s|.", account.account_name)
        for a in affiliations:
            ou_id=int(a['ou_id'])
            affiliation=int(a['affiliation'])
            priority = old_pri.get((ou_id, affiliation))

            new_pri = account._calculate_account_priority(ou_id, affiliation, priority)
            if new_pri != priority:
                logger.info("Setting new priority for affiliation |%d| and ou |%d|" % 
                            (affiliation, ou_id))
                try:
                    account.set_account_type(ou_id, affiliation, new_pri)
                    account.write_db()
                except Exception,msg:
                    logger.info("Manual intervention required for this user\nReason:%s" % msg)

        new_account_types = account.get_account_types()
        for n in new_account_types:
    	    logger.info("New priority %d for affiliation %d to ou %d" % (int(n['priority']),
                                                                         int(n['affiliation']),
                                                                         int(n['ou_id'])))
        logger.info("*******************END*************************************")
        db.commit()

def usage(e):
    print """Usage: [options]
    --affiliation A   Run only for affiliation A
    --newfromperson   Add new affiliations from owner
    """
    exit(e)

def main():
    import getopt
    import sys
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'a:n',
                                   ['help', 'affiliation=', 'fromperson'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    affiliation = None
    newfromperson = False
    
    for opt, val in opts:
        if opt in ('--help',):
            usage(0)
        elif opt in ('--affiliation','-a'):
            affiliation = int(const.PersonAffiliation(val))
        elif opt in ('--newfromperson','-n'):
            newfromperson = True
    
    print affiliation, newfromperson
    range_priorities(affiliation, newfromperson)

if __name__ == '__main__':
    main()
    
# arch-tag: 42dfa468-b42c-11da-833a-f4a65897359f
