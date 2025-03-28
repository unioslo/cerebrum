#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2025 University of Oslo, Norway
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
Write user and group information to an LDIF file.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules import LDIFutils

logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Write user and groups to an LDIF file",
    )
    parser.add_argument(
        '--user-spread',
        type=six.text_type,
        action='append',
        dest='user_spread',
        metavar='NAME',
        help='selection spread(s) for users',
    )
    parser.add_argument(
        '--filegroup-spread',
        type=six.text_type,
        action='append',
        dest='filegroup_spread',
        metavar='NAME',
        help='selection spread(s) for file groups',
    )
    parser.add_argument(
        '--netgroup-spread',
        type=six.text_type,
        action='append',
        dest='netgroup_spread',
        metavar='NAME',
        help='selection spread(s) for net groups',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        dest='all',
        help='deprecated arg - has no effect',
    )
    parser.add_argument(
        "-o", "--output-file",
        type=six.text_type,
        help="Write file to %(metavar)s (default: LDAP_POSIX['file'])",
        metavar="FILE",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('Start of script %s', parser.prog)
    logger.debug('args: %r', args)

    fd = LDIFutils.ldif_outfile('POSIX', filename=args.output_file)
    posix_config = LDIFutils.get_ldap_config(["LDAP", "LDAP_POSIX"])
    try:
        dn = posix_config.get_dn()
    except LookupError:
        # No LDAP_POSIX['dn'] means no entry string
        pass
    else:
        # Write a container entry for the POSIX tree dn
        entry = posix_config.get_container_entry()
        fd.write(LDIFutils.entry_string(dn, entry))

    db = Factory.get('Database')()
    posixldif = Factory.get('PosixLDIF')(
        db=db,
        fd=fd,
        # Setting spreads from cli args isn't all that useful.
        #
        # Would be better to build and pass in LdapConfig objects here, and
        # maybe let the config objects control if we want to make the given
        # part of the LDIF?
        u_sprd=args.user_spread,
        g_sprd=args.filegroup_spread,
        n_sprd=args.netgroup_spread,
    )

    for config_key, write_ldif in (
            ("LDAP_USER", posixldif.user_ldif),
            ("LDAP_FILEGROUP", posixldif.filegroup_ldif),
            ("LDAP_NETGROUP", posixldif.netgroup_ldif)):
        # Should this config maybe "inherit" from LDAP_POSIX?
        config = LDIFutils.get_ldap_config(["LDAP", config_key])
        config.get_dn()
        write_ldif()

    LDIFutils.end_ldif_outfile('POSIX', fd)

    logger.info('End of script %s', parser.prog)


if __name__ == '__main__':
    main()
