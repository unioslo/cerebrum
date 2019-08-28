#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010-2019 University of Oslo, Norway
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
Generate a host netgroup ldif file.
"""
from __future__ import unicode_literals

import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.posix.host_ng_export import HostGroupExport
from Cerebrum.utils.argutils import get_constant


logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Generate host netgroup ldif',
    )
    parser.add_argument(
        "-l", "--ldif",
        dest="filename",
        required=True,
        help="Write ldif data to %(metavar)s",
        metavar="<file>",
    )
    spread_arg = parser.add_argument(
        "-H", "--host-netgroup-spread",
        dest="spread",
        required=True,
        help="Filter host netgroups by %(metavar)s",
        metavar="<spread>",
    )
    zone_arg = parser.add_argument(
        "-z", "--zone",
        dest="zone",
        required=True,
        help="Zone to use for host netgroups.",
        metavar="<zone>",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    spread = get_constant(db, parser, co.Spread, args.spread, spread_arg)
    zone = get_constant(db, parser, co.DnsZone, args.zone, zone_arg)

    export = HostGroupExport(db)
    export.main(args.filename, spread, zone)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
