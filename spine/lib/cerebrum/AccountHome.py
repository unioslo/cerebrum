# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import crypt

from SpineLib.Builder import Method
from SpineLib.DatabaseClass import DatabaseClass, DatabaseAttr

from Account import Account
from Disk import Disk
from Types import Spread, HomeStatus

from SpineLib import Registry
registry = Registry.get_registry()

table = 'account_home'
class AccountHome(DatabaseClass):
    primary = [
        DatabaseAttr('account', table, Account),
        DatabaseAttr('spread', table, Spread)
    ]
    slots = [
        DatabaseAttr('home', table, str, write=True),
        DatabaseAttr('disk', table, Disk, write=True),
        DatabaseAttr('status', table, HomeStatus, write=True)
    ]

    db_attr_aliases = {
        table:{
            'account':'account_id',
            'disk':'disk_id'
        }
    }

registry.register_class(AccountHome)

# arch-tag: f1f89d6e-8174-4d53-82ac-c21885a8b574
