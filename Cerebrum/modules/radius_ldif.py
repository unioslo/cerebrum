# -*- coding: utf-8 -*-
#
# Copyright 2007-2025 University of Oslo, Norway
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
LDAP Radius user export

This LDAP export contains RADIUS attributes for Tunnel Protocol support.  It
should not be confused with RADIUS attributes that may or may not be included
in the PosixLDIF export.

Configuration
-------------
Settings for this export is typically fetched from ``cereconf.LDAP_RADIUS``,
and is typically set up to inherit settings from ``cereconf.LDAP``.

Note that HiØ uses ``cereconf.LDAP_USER`` for legacy reasons (this should
probably be fixed, as LDAP_USER is typically used for the posix.ldif).

Typical settings are:

auth_attr
    Select auth type and formatting for userPassword, ntPassword

dn
    Set DN for the container object and account objects.

dump_dir
    Default location for LDAP related export files. dump_dir will
    usually be the same for all LDAP exports.

file
    Absolute or relative name of the export file. If relative, it will be
    placed in `dump_dir`.

spreads
    Account spreads for this export - only accounts with one of these spreads
    will be included.  The spread order defines the priority for the spread
    mappings (`spread2vlan`, `spread2vpn`).

spread2vlan
    Maps spread to ``radiusTunnelPrivateGroupId`` value for matching accounts.

spread2vpn
    Maps spread to ``radiusClass`` OU for matching accounts
    (``radiusClass: OU=<value>;``).

If an account has multiple matching spreads (i.e. two or more of the spreads in
`spreads`), then the first spread listed in `spreads` will take priority.  This
decides which spread to use when fetching values in `spread2vlan` and
`spread2vpn` for the account.

History
-------
This class was built by combining the *very* similar scripts:

 - contrib/no/hiof/generate_users_ldif.py
 - contrib/no/hia/generate_radius_ldif.py
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import six

from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory
from Cerebrum.export.auth import AuthExporter
from Cerebrum.modules import LDIFutils
from Cerebrum.utils import aggregate

logger = logging.getLogger(__name__)


class RadiusAccountSelector(object):
    """ Select accounts for radius export.  """

    def __init__(self, db, config):
        self.db = db
        const = Factory.get("Constants")(db)
        self.spreads = spreads = [
            const.get_constant(const.Spread, value)
            for value in config.get("spreads")
        ]
        raw_vlans = config.get("spread2vlan")
        self.spread_to_vlan = {
            spread: raw_vlans[six.text_type(spread)]
            for spread in spreads
        }
        raw_vpns = config.get("spread2vpn")
        self.spread_to_vpn = {
            spread: "OU={};".format(raw_vpns[six.text_type(spread)])
            for spread in spreads
        }

    def get_cache(self):
        """
        Fetch and return all radius users and radius attributes.

        :returns dict:
            A mapping for all account candidates with:

                <account-id>: {
                    'name': <account name>,
                    'vlan': <radiusTunnelPrivateGroupId value>,
                    'vpn': <radiusClass value>,
                }
        """
        def _iter_accounts():
            ac = Factory.get("Account")(self.db)
            for spread in self.spreads:
                vlan = self.spread_to_vlan[spread]
                vpn = self.spread_to_vpn[spread]
                for row in ac.search(spread=int(spread)):
                    yield (
                        row['account_id'],
                        {
                            'name': row['name'],
                            'vlan': vlan,
                            'vpn': vpn,
                        },
                    )

        # _iter_accounts yields account data for accounts with multiple spreads
        # in the same order as the spreads from config - this means the first
        # account-id we encounter also contains the highest prioritized account
        # values.
        return aggregate.dict_collect_first(_iter_accounts())


def _get_account_quarantines(db):
    ac = Factory.get("Account")(db)
    for row in ac.list_entity_quarantines(entity_types=ac.const.entity_account,
                                          only_active=True):
        yield (row['entity_id'], int(row['quarantine_type']))


class RadiusAccountLdif(object):
    """
    Generate a radius account ldif file.

    This class is typically subclassed in order to set the correct
    object classes and attribute values.

    Typical use:
    ::
        db = Factory.get('Database')()
        config = LDIFutils.get_ldap_config(["LDAP", "LDAP_RADIUS"])
        ldif = RadiusAccountLdif(db, config)
        ldif.dump("/path/to/radius-users.ldif")
    """
    radius_object_class = "crbRadiusAccount"
    radius_tunnel_type = "VLAN"
    radius_tunnel_medium_type = "IEEE-802"

    def __init__(self, db, config):
        self.db = db
        self.config = config
        self._cached = False

        self.dn = config.get_dn()
        self.selector = RadiusAccountSelector(db, config)
        auth_attr = config.get('auth_attr')
        self.user_password = AuthExporter.make_exporter(
            db, auth_attr['userPassword'])
        self.nt_password = AuthExporter.make_exporter(
            db, auth_attr['ntPassword'])

    def cache_data(self):
        logger.debug("Caching radius accounts...")
        self.accounts = self.selector.get_cache()
        logger.info("Found %d candidate accounts", len(self.accounts))

        logger.debug('Caching account authentication...')
        self.user_password.cache.update_all()
        self.nt_password.cache.update_all()
        logger.info("Found %d userPassword, %d ntPassword",
                    len(self.user_password.cache.found),
                    len(self.nt_password.cache.found))

        logger.debug("Caching account quarantines...")
        self.quarantines = aggregate.dict_collect_lists(
            _get_account_quarantines(self.db))
        logger.info("Found %d quarantined accounts", len(self.quarantines))
        self._cached = True

    def dump(self, filename=None):
        if not self._cached:
            self.cache_data()
        fd = self.config.start_outfile(filename=filename)
        logger.debug('writing to %s', repr(fd))
        container = self.config.get_container_entry()
        fd.write(LDIFutils.entry_string(self.dn, container))

        logger.info('Generating export...')
        for account_id in sorted(self.accounts,
                                 key=lambda i: self.accounts[i]['name']):
            account_data = self.accounts[account_id]
            vlan = account_data['vlan']
            vpn = account_data['vpn']
            uname = account_data['name']

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
            dn = ','.join(('uid=' + uname, self.dn))
            entry = {
                'objectClass': ['top', 'account', self.radius_object_class],
                'uid': (uname,),
                'radiusTunnelType': (self.radius_tunnel_type,),
                'radiusTunnelMediumType': (self.radius_tunnel_medium_type,),
                'radiusTunnelPrivateGroupId': (vlan,),
                'radiusClass': (vpn,),
            }
            if auth:
                entry['objectClass'].append('simpleSecurityObject')
                entry['userPassword'] = auth
            if ntauth:
                entry['ntPassword'] = (ntauth,)
            fd.write(LDIFutils.entry_string(dn, entry, False))

        self.config.end_outfile(fd)
        logger.info("wrote ldif to %s", repr(fd))
