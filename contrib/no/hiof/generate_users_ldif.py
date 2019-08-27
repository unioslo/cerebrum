#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2019 University of Oslo, Norway
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
LDAP user export

TODO: This export is nearly identical to
``contrib/no/hia/generate_radius_ldif.py``

Configuration
-------------

cereconf.LDAP_USER
    Settings for the users export.

    auth_attr
        Select auth type and formatting for userPassword, ntPassword

    dn
        Sets distinguished name for users tree

    dump_dir
        Default location for LDAP related user export files. dump_dir will
        usually be the same for all LDAP exports.

    file
        Absolute or relative name of the export file. If relative, it will be
        placed in the LDAP_USER['dump_dir'].
"""
import argparse
import logging

import cereconf
import Cerebrum.logutils
from Cerebrum.export.auth import AuthExporter
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (ldapconf,
                                        ldif_outfile,
                                        end_ldif_outfile,
                                        entry_string,
                                        container_entry_string)
from Cerebrum.QuarantineHandler import QuarantineHandler


logger = logging.getLogger(__name__)


class UserLDIF(object):

    def __init__(self):
        self.user_dn = ldapconf('USER', 'dn', None)
        self.db = Factory.get('Database')()
        self.const = Factory.get('Constants')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.auth = None
        self.id2vlan_vpn = {}
        for spread in reversed(cereconf.LDAP_USER['spreads']):
            vlan_vpn = (cereconf.LDAP_USER['spread2vlan'][spread],
                        "OU=%s;" % cereconf.LDAP_USER['spread2vpn'][spread])
            spread = self.const.Spread(spread)
            for row in self.account.search(spread=spread):
                self.id2vlan_vpn[row['account_id']] = vlan_vpn
        # Configure auth
        auth_attr = ldapconf('USER', 'auth_attr', None)
        self.user_password = AuthExporter.make_exporter(
            self.db, auth_attr['userPassword'])
        self.nt_password = AuthExporter.make_exporter(
            self.db, auth_attr['ntPassword'])

    def cache_data(self):
        self.account_names = {}
        logger.info('Caching account names...')
        for row in self.account.search():
            self.account_names[row['account_id']] = row['name']

        logger.info('Caching account authentication...')
        self.user_password.cache.update_all()
        self.nt_password.cache.update_all()

        logger.info('Caching account quarantines...')
        self.quarantines = {}
        for row in self.account.list_entity_quarantines(
                entity_types=self.const.entity_account, only_active=True):
            self.quarantines.setdefault(int(row['entity_id']), []).append(
                int(row['quarantine_type']))

    def dump(self):
        fd = ldif_outfile('USER')
        logger.debug('writing to %s', repr(fd))
        fd.write(container_entry_string('USER'))

        logger.info('Generating export...')
        for account_id, vlan_vpn in self.id2vlan_vpn.iteritems():
            try:
                uname = self.account_names[account_id]
            except KeyError:
                logger.error('No account name for account_id=%r', account_id)
                continue
            try:
                auth = self.user_password.get(account_id)
            except LookupError:
                auth = None
            try:
                ntauth = self.nt_password.get(account_id)
            except LookupError:
                ntauth = None
            if account_id in self.quarantines:
                qh = QuarantineHandler(self.db, self.quarantines[account_id])
                if qh.should_skip():
                    continue
                if qh.is_locked():
                    auth = ntauth = None
            dn = ','.join(('uid=' + uname, self.user_dn))
            entry = {
                'objectClass': ['top', 'account', 'hiofRadiusAccount'],
                'uid': (uname,),
                'radiusTunnelType': ('13',),
                'radiusTunnelMediumType': ('6',),
                'radiusTunnelPrivateGroupId': (vlan_vpn[0],),
                'radiusClass': (vlan_vpn[1],),
            }
            if auth:
                entry['objectClass'].append('simpleSecurityObject')
                entry['userPassword'] = auth
            if ntauth:
                entry['ntPassword'] = (ntauth,)
            fd.write(entry_string(dn, entry, False))
        end_ldif_outfile('USER', fd)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Export ldif file with users',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    ldif = UserLDIF()
    ldif.cache_data()
    ldif.dump()

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
