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

import SpineClient

def get_accounts(tr, const):
    search = SpineClient.Search(tr)

    entityspreads = search.get_entity_spread_searcher('spread', spread=const.account_spread, entity_type=const.account_type)
    passwords = search.get_account_authentication_searcher('password', method=const.password_type)
    names = search.get_person_name_searcher('full_name', name_variant=const.full_name, source_system=const.source_system)
    groups = search.get_group_searcher('group')
    shells = search.get_posix_shell_searcher('shell')
    accounts = search.get_account_searcher('account')
    homedirs = search.get_home_directory_searcher('homedir')
    account_homes = search.get_account_home_searcher('account_home', spread=const.account_spread)
    disks = search.get_disk_searcher('disk')

    account_homes.add_join('homedir', homedirs, '')
    homedirs.add_left_join('disk', disks, '')
    accounts.add_left_join('', passwords, 'account')
    accounts.add_left_join('owner', names, 'person')
    accounts.add_left_join('primary_group', groups, '')
    accounts.add_left_join('shell', shells, '')
    accounts.add_left_join('', account_homes, 'account')
    accounts.add_join('', entityspreads, 'entity')

    accounts.order_by(accounts, 'posix_uid')

    return search.dump(accounts)

def get_home(account):
    if account['homedir'].home:
        return account['homedir'].home
    elif account['homedir'].disk:
        return '%s/%s' % (account['disk'].path, account['account'].name)

# arch-tag: 8f3cee88-47f8-11da-9e42-973abb4a50a5
