#!/usr/bin/env python2.2
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

# arch-tag: 99857f39-ea5b-471d-9cae-e3ddd2dd525c
