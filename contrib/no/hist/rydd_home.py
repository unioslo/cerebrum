#!/usr/bin/env python2.2
# Script to clear all home entries in account_home if user does not have 
# the spread anymore
#

import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum.modules.no.hia import Constants


db = Utils.Factory.get("Database")()
person = Utils.Factory.get("Person")(db)
# logger = Utils.Factory.get_logger("console")
account = Utils.Factory.get("Account")(db)
const = Utils.Factory.get("Constants")(db)
db.cl_init(change_program='rydd_home')
for row in account.list_account_home():
    account.clear()
    account.find(row['account_id'])
    active_spreads = [int(x['spread']) for x in account.get_spread()]
    if not int(row['home_spread']) in active_spreads:
        account.clear_home(int(row['home_spread']))
        print "Home %s for account %s purged from db because account does not have spread %s" % (
               row['home'], account.get_name(const.account_namespace), row['home_spread'])
        account.write_db()
db.commit()
