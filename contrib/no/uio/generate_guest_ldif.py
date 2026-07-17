#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2025 University of Oslo, Norway
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
Generates simple account objects in LDIF format, for guest accounts.

The LDIF file created by this script will not contain any metadata or tree
structure. It will only contain each account object in LDAP format.

The result is typically combined with another LDAP tree outside of Cerebrum.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import contextlib
import logging

import six

import guestconfig  # Need guest config for this
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory
from Cerebrum.export.auth import AuthExporter
from Cerebrum.modules.LDIFutils import LDIFWriter
from Cerebrum.modules.LDIFutils import ldapconf


logger = logging.getLogger(__name__)


def get_account(db, entity_id):
    ac = Factory.get("Account")(db)
    ac.find(int(entity_id))
    return ac


class GuestLDIF(object):
    """ Generate ldif file with guest accounts. """

    def __init__(self, db, ldif, spread):
        """ Set up object with ldap config.

        :param ldif: An LDIFWriter object for our ldif file
        :param spread: A spread that identifies guests

        """
        self.db = db
        self.spread = spread
        self.object_class = ldif.getconf('objectClass')
        auth_attrs = ldif.getconf('auth_attr')
        self.auth = dict()
        for attr in auth_attrs:
            logger.debug('Configuring auth attr %r: %r',
                         attr, auth_attrs[attr])
            self.auth[attr] = AuthExporter.make_exporter(db, auth_attrs[attr])

    def ac2entry(self, ac):
        """ Turn a populated Account object into an LDAP-entry dict. """
        entry = {
            'uid': ac.account_name,
            'objectClass': self.object_class,
        }

        for attr in self.auth:
            auth = self.auth[attr]
            try:
                entry[attr] = auth.get(ac.entity_id)
            except LookupError:
                continue

        return entry

    def generate_guests(self):
        """
        Guest account generator.

        Yields accounts with the configured spread.
        """
        qdb = EntityQuarantine(self.db)
        ac = Factory.get('Account')(self.db)
        co = Factory.get('Constants')(self.db)
        for row in ac.search(spread=self.spread):
            account_id = row['account_id']
            account_name = row['name']
            account_repr = "%s (%d)" % (account_name, account_id)

            quarantines = [
                int(row['quarantine_type'])
                for row in
                qdb.list_entity_quarantines(entity_ids=int(account_id),
                                            only_active=True)
            ]

            qh = QuarantineHandler(self.db, quarantines)
            if qh.should_skip() or qh.is_locked():
                logger.debug("Skipping %s, quarantined: %r",
                             account_repr,
                             [six.text_type(co.Quarantine(q))
                              for q in quarantines])
                continue

            account = get_account(self.db, account_id)
            entry = self.ac2entry(account)
            yield entry


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Generate a guest accounts ldif',
    )
    default_filename = ldapconf('GUESTS', 'file', None, guestconfig)
    default_spread = ldapconf('GUESTS', 'spread', None, guestconfig)
    default_base = ldapconf('GUESTS', 'dn', None, guestconfig)

    parser.add_argument(
        '-f', '--filename',
        default=default_filename,
        required=not default_filename,
        help='Destination file (default: %(default)s)',
        metavar='<filename>',
    )
    parser.add_argument(
        '-s', '--spread',
        default=default_spread,
        required=not default_spread,
        help='Guest spread (default: %(default)s)',
        metavar='<spread>',
    )
    parser.add_argument(
        '-b', '--base',
        default=default_base,
        required=not default_base,
        help='DN for guest user objects (default: %(default)s)',
        metavar='<dn>',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    filename = args.filename
    spread = co.get_constant(co.Spread, args.spread)
    base = args.base

    def entry_to_dn(entry_dict):
        return "uid=%s,%s" % (entry_dict['uid'], base)

    with contextlib.closing(
            LDIFWriter('GUESTS', filename, module=guestconfig)) as ldif:
        logger.debug("Writing guests to %s", repr(ldif.f))
        exporter = GuestLDIF(db, ldif, spread=spread)
        count = 0

        for entry in sorted(exporter.generate_guests(), key=entry_to_dn):
            ldif.write_entry(entry_to_dn(entry), entry)
            count += 1

    logger.info("%d accounts written to %s", count, repr(ldif.f))
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
