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

This script take the following arguments:

-h, --help : this message
-s, --spread : Which spread to identify guests by.
               Defaults to guestconfig.LDAP_GUESTS['spread']
-f, --filename : LDIF file to write
                 Defaults to guestconfig.LDAP_GEUSTS['file'] in
                 guestconfig.LDAP['dump_dir']
-b, --base : base DN for the objects
             Defaults to guestconfig.LDAP['dn']

"""
import guestconfig  # Need guest config for this

import sys
import getopt

from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import LDIFWriter
from Cerebrum.Errors import CerebrumError
from Cerebrum.QuarantineHandler import QuarantineHandler


logger = Factory.get_logger('cronjob')


def usage(exitcode=0):
    """ Print usage and exit. """
    print __doc__
    sys.exit(exitcode)


class GuestLDIF(object):

    """ Generate ldif file with guest accounts. """

    def __init__(self, ldif, spread=None):
        """ Set up object with ldap config.

        :param ldif: The LDIFWriter object that contains our settings
        :param logger: The logger to use. Default: Create a new logger that
                       logs to console.
        :param spread: The spread that identifies guests. Default: Fetch spread
                       from guestconfig.LDAP['spread']

        """
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self.ac = Factory.get('Account')(self.db)

        self.spread = self.get_const(spread or ldif.getconf('spread'),
                                     self.co.Spread)

        self.object_class = ldif.getconf('objectClass')
        self.auth_attrs = ldif.getconf('auth_attr')

    def get_const(self, const_str, const_type):
        """ Wrap h2c with caching, and raise error if not found. """
        if not hasattr(self, '_co_cache'):
            self._co_cache = dict()
        if (const_str, const_type) in self._co_cache:
            return self._co_cache[(const_str, const_type)]
        const = self.co.human2constant(const_str, const_type)
        if const:
            return self._co_cache.setdefault((const_str, const_type), const)
        raise CerebrumError("No constant '%s' of type '%s'" % (const_str,
                                                               const_type))

    def ac2entry(self, ac):
        """ Turn a populated Account object into an LDAP-entry dict. """
        entry = {'uid': ac.account_name,
                 'objectClass': self.object_class, }

        if self.auth_attrs:
            # Update password attributes
            for (attr, (method, format)) in self.auth_attrs.iteritems():
                method = self.get_const(method, self.co.Authentication)
                passwd = ac.get_account_authentication(method)
                entry[attr] = format % passwd

        return entry

    def dn_for_entry(self, entry, dn):
        """ Return the dn for a given entry. """
        return

    def generate_guests(self):
        """ Guest account generator.

        Yields accounts with the configured spread.

        """
        for row in self.ac.search(spread=self.spread):
            # NOTE: Will not consider expired accounts
            self.ac.clear()
            self.ac.find(row['account_id'])

            qh = QuarantineHandler(
                self.db, map(lambda x: int(x['quarantine_type']),
                             self.ac.get_entity_quarantine(only_active=True)))

            # No need for quarantined guest accounts in ldap
            # NOTE: We might want to export accounts that is_locked(), but
            #       without passwords.
            if qh.should_skip() or qh.is_locked():
                logger.debug("Skipping %s, quarantined: %r",
                             self.ac.account_name,
                             [str(self.co.Quarantine(q)) for q in
                              qh.quarantines])
                continue

            entry = self.ac2entry(self.ac)
            yield entry

    def write_to_file(self, dn, entry):
        """ Write entry to a file descriptor. """


def main():
    filename = spread = base = None
    logger.info("Script start: '%s'" % sys.argv[0])

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hf:b:s:', [
            'help', 'filename=', 'spread=', 'base='])
    except getopt.GetoptError, e:
        print "error:", e
        usage(1)
    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
        elif opt in ('-f', '--filename'):
            filename = val
        elif opt in ('-s', '--spread'):
            spread = val
        elif opt in ('-b', '--base'):
            base = val

    logger.info("Configuring export")

    ldif = LDIFWriter('GUESTS', filename, module=guestconfig)
    try:
        base = base or ldif.getconf('dn')
        spread = spread or ldif.getconf('spread')
        dn = lambda e: "uid=%s,%s" % (e['uid'], base)

        exporter = GuestLDIF(ldif, spread=spread)
        logger.info("Starting guest account ldap export.")
        count = 0

        for entry in exporter.generate_guests():
            ldif.write_entry(dn(entry), entry)
            count += 1
    except Exception, e:
        logger.error("Error: Unable to export: %s" % e, exc_info=1)
        raise
    finally:
        ldif.close()

    logger.info("Done, %d accounts dumped to ldif" % count)


if __name__ == '__main__':
    main()
