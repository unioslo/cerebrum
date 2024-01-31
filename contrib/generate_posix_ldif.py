#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2023 University of Oslo, Norway
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

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import (ldif_outfile,
                                        end_ldif_outfile,
                                        container_entry_string)

logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--user-file',
        type=six.text_type,
        dest='user_file',
        metavar='PATH',
        help='output file for users')
    parser.add_argument(
        '--user-spread',
        type=six.text_type,
        action='append',
        dest='user_spread',
        metavar='NAME',
        help='selection spread(s) for users')
    parser.add_argument(
        '--filegroup-file',
        type=six.text_type,
        dest='filegroup_file',
        metavar='PATH',
        help='output file for file groups')
    parser.add_argument(
        '--filegroup-spread',
        type=six.text_type,
        action='append',
        dest='filegroup_spread',
        metavar='NAME',
        help='selection spread(s) for file groups')
    parser.add_argument(
        '--netgroup-file',
        type=six.text_type,
        dest='netgroup_file',
        metavar='PATH',
        help='output file for net groups')
    parser.add_argument(
        '--netgroup-spread',
        type=six.text_type,
        action='append',
        dest='netgroup_spread',
        metavar='NAME',
        help='selection spread(s) for net groups')
    parser.add_argument(
        '--all',
        action='store_true',
        dest='all',
        help='write everything as configured in cereconf')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    got_file = args.user_file or args.filegroup_file or args.netgroup_file
    if args.all and got_file:
        parser.error('Cannot specify --all with --*-file')
    elif not args.all and not got_file:
        parser.error('Need one of --all or --*-file')

    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('Start of script %s', parser.prog)
    logger.debug('args: %r', args)

    fd = None
    if args.all:
        fd = ldif_outfile('POSIX')
        if cereconf.LDAP_POSIX.get('dn'):
            fd.write(container_entry_string('POSIX'))

    db = Factory.get('Database')()
    posixldif = Factory.get('PosixLDIF')(
        db=db,
        logger=logger,
        u_sprd=args.user_spread,
        g_sprd=args.filegroup_spread,
        n_sprd=args.netgroup_spread,
        fd=fd)

    for var, func, filepath in (
            ('LDAP_USER', posixldif.user_ldif, args.user_file),
            ('LDAP_FILEGROUP', posixldif.filegroup_ldif, args.filegroup_file),
            ('LDAP_NETGROUP', posixldif.netgroup_ldif, args.netgroup_file)):
        if (args.all or filepath) and getattr(cereconf, var).get('dn'):
            func(filepath)
        elif filepath:
            parser.error("Missing 'dn' in cereconf.{}".format(var))

    if fd:
        end_ldif_outfile('POSIX', fd)

    logger.info('End of script %s', parser.prog)


if __name__ == '__main__':
    main()
