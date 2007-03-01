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

import cerebrum_path, cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules import LDIFutils

class UserLDIF(object):
    def make_auths(self, auth_type, old=None):
        auth = old or {}
        for row in self.account.list_account_authentication(auth_type):
            auth[int(row['account_id'])] = (row['entity_name'],
                                            row['auth_data'])
        return auth

    def __init__(self, db):
        self.user_dn = LDIFutils.ldapconf('USER', 'dn', None)
        self.db = db
        self.const = Factory.get('Constants')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.md4_auth = self.make_auths(self.const.auth_type_md4_nt)
        self.auth = None
        for auth_type in (self.const.auth_type_crypt3_des,
                          self.const.auth_type_md5_crypt):
            self.auth = self.make_auths(auth_type, self.auth)

    def run(self):
        fd = LDIFutils.ldif_outfile('USER')
        fd.write(LDIFutils.container_entry_string('USER'))
        ids = {}
        for spread in cereconf.LDAP_USER['spreads']:
            spread = self.const.Spread(spread)
            for row in self.account.list_all_with_spread(spread):
                ids[row['entity_id']] = None
        for id in ids:
            info = self.auth[id]
            uname = LDIFutils.iso2utf(str(info[0]))
            dn = ','.join(('uid=' + uname, self.user_dn))
            entry = {
                'objectClass':  ['top', 'account'],
                'uid':          (uname,)}
            auth = info[1]
            if auth:
                entry['objectClass'].append('simpleSecurityObject')
                entry['userPassword'] = ('{crypt}' + auth,)
            info = self.md4_auth.get(id)
            if info and info[1]:
                entry['objectClass'].append('sambaSamAccount')
                entry['sambaNTPassword'] = (info[1],)
                entry['sambaSID'] =        (str(id),)
            try:
                fd.write(LDIFutils.entry_string(dn, entry, False))
            except:
                print entry
                raise
        LDIFutils.end_ldif_outfile('USER', fd)

def main():
    db = Factory.get('Database')()
    ldif = UserLDIF(db)
    ldif.run()

if __name__ == '__main__':
    main()
