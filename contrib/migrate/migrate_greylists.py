#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

db = Factory.get('Database')()
db.cl_init(change_program="migrate")
co = Factory.get('Constants')(db)

all_spam_setting = {}
existing_greylist_target_ids = []

et = Email.EmailTarget(db)
esf = Email.EmailSpamFilter(db)
etf = Email.EmailTargetFilter(db)

et.clear()
esf.clear()

#
# we need to move all registered spam_filter where
# action == greylist to the new email_target_filter table
#
# find all email_spam_filter entries where action == greylist

for a in esf.list_email_spam_filters_ext():
    if 'greylist' in a:
        existing_greylist_target_ids.append(a[0])

for e_id in existing_greylist_target_ids:
    # find targets whith spam_action == greylist
    et.clear()
    et.find(int(e_id))
    etf.clear()
    # check whether the target already has greylist defined as tool
    try:
        etf.find(int(e_id), co.email_target_filter_greylist)
    except Errors.NotFoundError:
        # if not greylist is registered in email_target_filter,
        # register now
        etf.clear()
        etf.populate(co.email_target_filter_greylist, parent=et)
        etf.write_db()
        esf.clear()
        esf.find(int(e_id))
        esf.email_spam_action = co.email_spam_action_delete
        esf.write_db()
db.commit()
