# -*- coding: utf-8 -*-
#
# Copyright 2014-2024 University of Oslo, Norway
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
The guest account module.

This is the guest account module for Cerebrum.  It is used to issue
(relatively) short-lived user accounts to users that *doesn't* exist in any
source system.  Because we don't have any *person* object to tie these accounts
to, they are created as non-personal accounts.

We still need some metadata for the account:

Guest account type
    These guest accounts have their own ``Account.np_type``

Guest owner trait
    A person (typically an employee) registers the guest.  On registration, the
    guest account gets a trait that links to this person as the *guest owner*.

Guest name trait
    The guest name is also stored as a trait.

Guest quarantine
    Guests get a quarantine set on registration, with a future start date.
"""
