#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
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

"""
Generating an ldif to be used by Fronter. Exporting every non-expired user's
password hashes.
"""

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules import LDIFutils
from Cerebrum.QuarantineHandler import QuarantineHandler

class UserLDIF(object):
    def load_quaratines(self):
        self.quarantines = {}
        for row in self.account.list_entity_quarantines(
                entity_types=self.const.entity_account, only_active=True):
            self.quarantines.setdefault(int(row['entity_id']), []).append(
                int(row['quarantine_type']))

    def make_auths(self, auth_type, old=None):
        auth = old or {}
        for row in self.account.list_account_authentication(auth_type,
                                                            filter_expired=True):
            auth[int(row['account_id'])] = (row['entity_name'],
                                            row['auth_data'])
        return auth

    def __init__(self):
        self.user_dn = LDIFutils.ldapconf('USER', 'dn', None)
        self.db = Factory.get('Database')()
        self.const = Factory.get('Constants')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.auth = None
        for auth_type in (self.const.auth_type_crypt3_des,
                          self.const.auth_type_md5_crypt):
            self.auth = self.make_auths(auth_type, self.auth)
        self.load_quaratines()

    def dump(self):
        fd = LDIFutils.ldif_outfile('USER')
        fd.write(LDIFutils.container_entry_string('USER'))
        for row in self.account.search():
            account_id = row['account_id']
            info = self.auth[account_id]
            uname = LDIFutils.iso2utf(str(info[0]))
            auth = info[1]
            if account_id in self.quarantines:
                qh = QuarantineHandler(self.db, self.quarantines[account_id])
                if qh.should_skip():
                    continue
                if qh.is_locked():
                    auth = None
            dn = ','.join(('uid=' + uname, self.user_dn))
            entry = {
                'objectClass': ['account'],
                'uid': (uname,),}
            if auth:
                entry['objectClass'].append('simpleSecurityObject')
                entry['userPassword'] = ('{crypt}' + auth,)
            fd.write(LDIFutils.entry_string(dn, entry, False))
        LDIFutils.end_ldif_outfile('USER', fd)

def main():
    UserLDIF().dump()

if __name__ == '__main__':
    main()
