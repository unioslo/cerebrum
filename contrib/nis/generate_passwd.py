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

import argparse
import logging

import Cerebrum.logutils
from Cerebrum import Utils
from Cerebrum.utils.argutils import get_constant
from Cerebrum.modules.NISUtils import Passwd

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        'Generates a password file for the requested spreads'
    )
    parser.add_argument(
        '--user_spread',
        dest='user_spread',
        required=True,
    )
    parser.add_argument(
        '-p', '--passwd',
        dest='passwd_file',
        required=True,
        help='Path to file where passwords should be written',
    )
    parser.add_argument(
        '-s', '--shadow',
        dest='shadow_file',
        default=None,
        help='Path to shadow file',
    )
    parser.add_argument(
        '-a', '--auth_method',
        dest='auth_method',
        default=None,
        help="""If not given, passwords are replaced with 'x' in the password 
             file"""
    )
    parser.add_argument(
        '--eof',
        dest='e_o_f',
        action='store_true',
        help='End dump file with E_O_F to mark successful completion'
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    Factory = Utils.Factory
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    if args.auth_method:
        args.auth_method = get_constant(db, parser, co.Authentication,
                                        args.auth_method)
    args.user_spread = get_constant(db, parser, co.Spread, args.user_spread)

    p = Passwd(args.auth_method, args.user_spread)
    p.write_passwd(args.passwd_file, args.shadow_file, args.e_o_f)


if __name__ == '__main__':
    main()
