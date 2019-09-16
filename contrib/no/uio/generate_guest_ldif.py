#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2014 University of Oslo, Norway
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
"""
import argparse

import guestconfig  # Need guest config for this

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory
from Cerebrum.export.auth import AuthExporter
from Cerebrum.modules.LDIFutils import LDIFWriter
from Cerebrum.modules.LDIFutils import ldapconf


logger = Factory.get_logger('cronjob')


def get_spread(co, value):
    const = co.human2constant(value, co.Spread)
    int(const)
    return const


class GuestLDIF(object):
    """ Generate ldif file with guest accounts. """

    def __init__(self, db, ldif, spread):
        """ Set up object with ldap config.

        :param ldif: The LDIFWriter object that contains our settings
        :param spread: The spread that identifies guests. Default: Fetch spread
                       from guestconfig.LDAP['spread']

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

    def dn_for_entry(self, entry, dn):
        """ Return the dn for a given entry. """
        return

    def generate_guests(self):
        """
        Guest account generator.

        Yields accounts with the configured spread.
        """

        ac = Factory.get('Account')(self.db)
        co = Factory.get('Constants')(self.db)
        for row in ac.search(spread=self.spread):
            # NOTE: Will not consider expired accounts
            ac.clear()
            ac.find(row['account_id'])

            qh = QuarantineHandler(
                self.db,
                [int(row['quarantine_type'])
                 for row in ac.get_entity_quarantine(only_active=True)])

            # No need for quarantined guest accounts in ldap
            # NOTE: We might want to export accounts that is_locked(), but
            #       without passwords.
            if qh.should_skip() or qh.is_locked():
                logger.debug("Skipping %s, quarantined: %r",
                             ac.account_name,
                             [str(co.Quarantine(q))
                              for q in qh.quarantines])
                continue

            entry = self.ac2entry(ac)
            yield entry

    def write_to_file(self, dn, entry):
        """ Write entry to a file descriptor. """
        pass


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
    spread = get_spread(co, args.spread)
    base = args.base

    def entry_to_dn(uid):
        return "uid=%s,%s" % (entry['uid'], base)

    logger.info("Configuring export")

    ldif = LDIFWriter('GUESTS', filename, module=guestconfig)
    try:
        exporter = GuestLDIF(db, ldif, spread=spread)
        logger.info("Starting guest account ldap export.")
        count = 0

        for entry in exporter.generate_guests():
            ldif.write_entry(entry_to_dn(entry), entry)
            count += 1
    except Exception as e:
        logger.error("Unable to export: %s", e, exc_info=True)
        raise
    finally:
        ldif.close()

    logger.info("%d accounts dumped to ldif", count)
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
