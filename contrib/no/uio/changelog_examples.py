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

# This is a file showing changelog access in Cerebrum.
# A real example can be viewed in 'process_changes.py'

# Import the basics. Needed for accessing ChangeLog.
import cerebrum_path
import os
import cereconf
from Cerebrum.modules import ChangeLog
from Cerebrum.Utils import Factory

# If you want to link data from ChangeLog against PosixUsers, import:
from Cerebrum.modules import PosixUser

# Set up the basics.
db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)

# The method under returns all new users built. Cutting the search
# with dates are optional.
#
# Attributes returned from get_log_events_date():
#        tstamp, change_id, subject_entity, change_type_id,
#        dest_entity, change_params, change_by, change_program
# Access them with 'evt.foo'.
#
# If one wishes to make other reports, simply get the correct constant
# from cerebrum/Cerebrum/modules/CLConstans.py(or from the database),
# and import the right module for this info.

def list_new_users(after_date=None, before_date=None):
    posix_user = PosixUser.PosixUser(db)
    for evt in db.get_log_events_date(int(const.account_create),
                                      sdate=after_date,
                                      edate=before_date):
        posix_user.clear()
        posix_user.find(evt.subject_entity)
        print "User created: '%s' on %s" % (posix_user.account_name,evt.tstamp)
              


# Examples:
# In this example there are two optional input parameters;
# 'after_date' and 'before_date'. If you use none(don't do that unless
# you want ALL your created users!), after_date or both of those, you
# don't need to specify them in the call, but if you want all users
# created before date X, you have to include 'before_date=' in the
# call.
# Ex:

# Find all users created between 2003-07-01 and 2003-07-22:
list_new_users('2003-07-01', '2003-07-22')

# Same as above, but here we specify which parameter is which:
list_new_users(after_date='2003-07-01',before_date='2003-07-22')

# List users created before 2003-07-25. In this example you have to
# include 'before_date='
list_new_users(before_date='2003-07-25')

# List users created after 2003-07-01
list_new_users('2003-07-01')

# If unsure whether you should include 'before_date=' and
# 'after_date=' in your search, include. 

# arch-tag: e5681235-9e7a-4265-8a2a-7e331e631ac7
