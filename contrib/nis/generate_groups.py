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
# It can be viewed in commit fa5d2d10bcd.

import argparse
import logging

import Cerebrum.logutils
from Cerebrum.utils.argutils import get_constant
from Cerebrum.Utils import Factory
from Cerebrum.modules.NISUtils import FileGroup, UserNetGroup, MachineNetGroup
from Cerebrum.modules.NISUtils import HackUserNetGroupUIO

logger = logging.getLogger(__name__)


def verify_args(args, parser):
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    args.group_spread = get_constant(db, parser, co.Spread, args.group_spread)
    if args.user_spread:
        args.user_spread = get_constant(db, parser, co.Spread, args.user_spread)
    if args.zone:
        args.zone = get_constant(db, parser, co.DnsZone, args.zone)
    return args


def parse_args():
    parser = argparse.ArgumentParser(
        'Generates a nismap file for the requested spreads'
    )
    parser.add_argument(
        '-g', '--group',
        dest='group',
        default=None,
        help='Write posix group map to outfile'
    )
    parser.add_argument(
        '-n', '--netgroup',
        dest='netgroup',
        default=None,
        help='Write netgroup map to outfile'
    )
    parser.add_argument(
        '-m', '--mnetgroup',
        dest='mnetgroup',
        default=None,
        help='Write netgroup.host map to outfile'
    )
    parser.add_argument(
        '--this-is-an-ugly-hack',
        dest='hack',
        default=None,
        help='Write hack netgroup map to outfile'
    )

    args, _rest = parser.parse_known_args()
    # Conditionally required arguments
    zone_required = args.mnetgroup is not None
    user_spread_required = any(a is not None for a in (args.netgroup,
                                                       args.hack,
                                                       args.group))

    parser.add_argument(
        '--user_spread',
        dest='user_spread',
        required=user_spread_required,
        help='Filter by user_spread'
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
        required=zone_required,
        help='dns zone postfix (example: .uio.no.)'
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    args = verify_args(args, parser)
    return args


def main():
    args = parse_args()

    if args.group:
        fg = FileGroup(args.group_spread, args.user_spread)
        fg.write_filegroup(args.group, args.e_o_f)

    if args.netgroup:
        ung = UserNetGroup(args.group_spread, args.user_spread)
        ung.write_netgroup(args.netgroup, args.e_o_f)

    if args.mnetgroup:
        ngu = MachineNetGroup(args.group_spread, None, args.zone)
        ngu.write_netgroup(args.mnetgroup, args.e_o_f)

    if args.hack:
        ung = HackUserNetGroupUIO(args.group_spread, args.user_spread)
        ung.write_netgroup(args.hack, args.e_o_f)


if __name__ == '__main__':
    main()
