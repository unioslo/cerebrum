#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2007-2018 University of Oslo, Norway
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

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (ldapconf,
                                        ldif_outfile,
                                        end_ldif_outfile,
                                        entry_string,
                                        container_entry_string)
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
        for row in self.account.list_account_authentication(
                auth_type, filter_expired=False):
            auth[int(row['account_id'])] = (row['entity_name'],
                                            row['auth_data'])
        return auth

    def __init__(self):
        self.user_dn = ldapconf('USER', 'dn', None)
        self.db = Factory.get('Database')()
        self.const = Factory.get('Constants')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.md4_auth = self.make_auths(self.const.auth_type_md4_nt)
        self.auth = None
        for auth_type in (self.const.auth_type_crypt3_des,
                          self.const.auth_type_md5_crypt):
            self.auth = self.make_auths(auth_type, self.auth)
        self.load_quaratines()
        self.id2vlan_vpn = {}
        for spread in reversed(cereconf.LDAP_USER['spreads']):
            vlan_vpn = (cereconf.LDAP_USER['spread2vlan'][spread],
                        "OU=%s;" % cereconf.LDAP_USER['spread2vpn'][spread])
            spread = self.const.Spread(spread)
            for row in self.account.search(spread=spread):
                self.id2vlan_vpn[row['account_id']] = vlan_vpn

    def dump(self):
        fd = ldif_outfile('USER')
        fd.write(container_entry_string('USER'))
        noAuth = (None, None)
        for account_id, vlan_vpn in self.id2vlan_vpn.iteritems():
            info = self.auth[account_id]
            uname = info[0]
            auth = info[1]
            ntAuth = self.md4_auth.get(account_id, noAuth)[1]
            if account_id in self.quarantines:
                qh = QuarantineHandler(self.db, self.quarantines[account_id])
                if qh.should_skip():
                    continue
                if qh.is_locked():
                    auth = ntAuth = None
            dn = ','.join(('uid=' + uname, self.user_dn))
            entry = {
                'objectClass': ['top', 'account', 'hiofRadiusAccount'],
                'uid': (uname,),
                'radiusTunnelType': ('13',),
                'radiusTunnelMediumType': ('6',),
                'radiusTunnelPrivateGroupId': (vlan_vpn[0],),
                'radiusClass': (vlan_vpn[1],)}
            if auth:
                entry['objectClass'].append('simpleSecurityObject')
                entry['userPassword'] = ('{crypt}' + auth,)
            if ntAuth:
                entry['ntPassword'] = (ntAuth,)
            fd.write(entry_string(dn, entry, False))
        end_ldif_outfile('USER', fd)


def main():
    UserLDIF().dump()


if __name__ == '__main__':
    main()
