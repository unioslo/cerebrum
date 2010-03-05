#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2010 University of Oslo, Norway
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

# Clean out manually registered affiliation if an equivalent affiliation
# has been registered by an authoritative system.


import cerebrum_path
from Cerebrum import Utils, Errors
import cereconf
import string
import mx.DateTime
from string import Template
import smtplib

Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
account = Factory.get("Account")(db)
person = Factory.get("Person")(db)
logger = Factory.get_logger("cronjob")

from Cerebrum.modules import Email
emailtarget = Email.EmailTarget(db)
emailaddress = Email.EmailAddress(db)



def cleanup_email(account_id):
    emailtarget.clear()
    try:
        emailtarget.find_by_target_entity(account_id)
    except Errors.NotFoundError:
        pass
    else:
        for addr in emailtarget.get_addresses():
            emailaddress.find(addr['address_id'])
            logger.info("Deleting emailaddress %s@%s",
                        addr['local_part'], addr['domain'])
            emailaddress.delete()
        logger.info("Deleting emailtarget")
        emailtarget.delete()
    

def cleanup_posix(account_id):
    posixuser.clear()
    try:
        posixuser.find(account_id)
    except Errors.NotFoundError:
        pass
    else:
        logger.info("Demoting account %s from posix",
                    posixuser.account_name)
        posixuser.delete()


def clenup_spreads(account_id):
    account.clear()
    account.find(account_id)
    for s in account.get_spread():
        logger.info("Deleting spread %s from account %s",
                    account.const.spread)
        account.delete_spread(s['spread'])


def main():
    days = getattr(cereconf, 'CLEANUP_EXPIRED_ACCOUNTS_DAYS', 180)
    
    for account in account.search(expire_stop=now-360):
        
    

    

if __name__ == '__main__':
    main()
