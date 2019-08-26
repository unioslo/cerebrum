#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2019 University of Oslo, Norway
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
#
# This script is based on the deprecated script contrib/generate_nismaps.py.
# It can be viewed in commit 851446bf25a6e69b87db7e7cea6c870a1ab3f0cd.
"""Writes various NIS group files given specific spreads for user and groups

Includes functionality for file groups, net groups, machine net groups. Can
also include person objects. It then picks the primary account of person
objects.

"""
import argparse
import logging

import Cerebrum.logutils
from Cerebrum.utils.argutils import get_constant
from Cerebrum.Utils import Factory
from Cerebrum.modules.NISUtils import FileGroup, UserNetGroup, MachineNetGroup
from Cerebrum.modules.NISUtils import HackUserNetGroupUIO

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Generate a NSS groups file for a given spread',
    )
    parser.add_argument(
        '-g', '--group',
        dest='group',
        default=None,
        help='Write a filegroups file to %(metavar)s',
        metavar='FILE',
    )
    parser.add_argument(
        '-n', '--netgroup',
        dest='netgroup',
        default=None,
        help='Write a netgroups file to %(metavar)s',
        metavar='FILE',
    )
    parser.add_argument(
        '-m', '--mnetgroup',
        dest='mnetgroup',
        default=None,
        help='Write netgroups file with hosts to %(metavar)s',
        metavar='FILE',
    )
    parser.add_argument(
        '--this-is-an-ugly-hack',
        dest='hack',
        default=None,
        help=('Write a netgroups file that includes the primary account '
              'of persons to %(metavar)s'),
        metavar='FILE',
    )

    parser.add_argument(
        '--user_spread',
        dest='user_spread',
        help='Filter by user_spread',
    )
    parser.add_argument(
        '--group_spread',
        dest='group_spread',
        required=True,
        help='Filter by group_spread'
    )
    parser.add_argument(
        '--eof',
        dest='e_o_f',
        action='store_true',
        help='End dump file with E_O_F to mark successful completion'
    )
    parser.add_argument(
        '-Z', '--zone',
        dest='zone',
        help='dns zone postfix (example: .uio.no.)'
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    if args.mnetgroup and not args.zone:
        parser.error('--mnetgroup requires --zone')

    need_user_spread = any(a is not None for a in (args.netgroup, args.hack,
                                                   args.group))
    if need_user_spread and not args.user_spread:
        parser.error('No --user_spread given')

    args.group_spread = get_constant(db, parser, co.Spread, args.group_spread)
    if args.user_spread:
        args.user_spread = get_constant(db, parser, co.Spread,
                                        args.user_spread)
    if args.zone:
        args.zone = get_constant(db, parser, co.DnsZone, args.zone)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    if args.group:
        logger.debug('generating filegroups...')
        fg = FileGroup(args.group_spread, args.user_spread)
        fg.write_filegroup(args.group, args.e_o_f)
        logger.info('filegroups written to %s', args.group)

    if args.netgroup:
        logger.debug('generating netgroups...')
        ung = UserNetGroup(args.group_spread, args.user_spread)
        ung.write_netgroup(args.netgroup, args.e_o_f)
        logger.info('netgroups written to %s', args.netgroup)

    if args.mnetgroup:
        logger.debug('generating host netgroups...')
        ngu = MachineNetGroup(args.group_spread, None, args.zone)
        ngu.write_netgroup(args.mnetgroup, args.e_o_f)
        logger.info('host netgroups written to %s', args.mnetgroup)

    if args.hack:
        logger.debug('generating netgroups that includes persons...')
        ung = HackUserNetGroupUIO(args.group_spread, args.user_spread)
        ung.write_netgroup(args.hack, args.e_o_f)
        logger.info('netgroups written to %s', args.hack)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
