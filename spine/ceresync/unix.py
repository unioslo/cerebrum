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

import Spine

import Account
import Group
import Person
import Quarantine
import File

def unix(tr, const):
    group_lines = []
    passwd_lines = {}
    for key in const.passwd_files:
        passwd_lines[key] = []

    quarantines = Quarantine.get_quarantines(tr, const)

    for account in Account.get_accounts(tr, const):
        if not account['account'].posix_uid_exists:
            continue

        args = {}
        args['username'] = account['account'].name
        args['password'] = account['password'].auth_data or '*'
        args['uid'] = account['account'].posix_uid
        args['gid'] = account['group'].posix_gid
        args['gecos'] = account['account'].gecos or account['full_name'].name
        args['shell'] = account['shell'].shell
        args['home'] = Account.get_home(account)

        # shadow fields
        args['last'] = '' # Days since Jan 1, 1970 that password was last changed
        args['may'] = '' # Days before password may be changed
        args['must'] = '' # Days after which password must be changed
        args['warn'] = '' # Days before password is to expire that user is warned
        args['expire'] = '' # Days after password expires that account is disabled
        args['disable'] = '' # Days since Jan 1, 1970 that account is disabled
        args['reserved'] = '' # A reserved field
    
        # bsd fields
        args['class'] = '' # User's login class
        args['change'] = '' # User's login class

        if account['account'].id in quarantines:
            print 'unhandled qurantine for %(username)s' % args

        for i, lines in passwd_lines.items():
            lines.append(const.passwd_files[i] % args)

    for group, members in Group.get_groups(tr, const):
        if not group['group'].posix_gid_exists:
            continue
        args = {}
        args['groupname'] = group['group'].name
        args['gid'] = group['group'].posix_gid
        args['members'] = ','.join(members)

        group_lines.append(const.group_format % args)

    for name, lines in passwd_lines.items():
        File.writeFile(name, lines)

    File.writeFile('group', group_lines)

if __name__ == '__main__':
    try:
        session = Spine.new_session()
        tr = session.new_transaction()
        const = Spine.config.UnixConstants(tr)
        unix(tr, const)
    finally:
        try:
            session.logout()
        except:
            pass

# arch-tag: 91d40168-47f8-11da-9430-829735ca2622
