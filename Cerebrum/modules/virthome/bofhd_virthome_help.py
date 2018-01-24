#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2009 University of Oslo, Norway
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
Help strings for virthome bofhd.

This module is probably unnecessary, but having it will enable one to use
jbofh as a virthome client (== easier testing).
"""





arg_help = {
    'account_name':
        ['uname', 'Enter accountname'],
    'string':
        ['string', 'Enter value'],
    'email_address':
        ['address', 'Enter e-mail address'],
    'date':
        ['date', 'Enter date (YYYY-MM-DD)',
         "The legal date format is 2003-12-31"],
    'invite_timeout':
        ['timeout', 'Enter timeout (days)',
         'The number of days before the invite times out'],
    'person_name':
        ['name', 'Enter person name'],
    'group_name':
        ['gname', 'Enter groupname'],
    'id':
        ['id', 'Enter id', "Enter a group's internal id"],
    'spread':
        ['spread', 'Enter spread', "'spread list' lists possible values"],
    'quarantine_type':
        ['qtype', 'Enter quarantine type',
         "'quarantine list' lists defined quarantines"],
}
