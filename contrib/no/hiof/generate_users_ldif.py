#!/usr/bin/env python
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
LDAP radius user export for HiØ

Configuration
-------------
Fetches settings from ``cereconf.LDAP_USER``.  See
:mod:`Cerebrum.modules.radius_ldif` for details.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules import LDIFutils
from Cerebrum.modules import radius_ldif

logger = logging.getLogger(__name__)


class HiofRadiusLdif(radius_ldif.RadiusAccountLdif):
    """ Radius tunnel attribute export for HiØ """

    radius_object_class = "hiofRadiusAccount"
    radius_tunnel_type = "13"
    radius_tunnel_medium_type = "6"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Export ldif file with users",
    )
    parser.add_argument(
        "--output",
        help="Write ldif to %(metavar)s (default: LDAP_USER['file'])",
        metavar="FILE",
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("cronjob", args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %s', repr(args))

    db = Factory.get('Database')()
    # We may want to move this hiof config to cereconf.LDAP_RADIUS?
    config = LDIFutils.get_ldap_config(["LDAP", "LDAP_USER"])
    ldif = HiofRadiusLdif(db, config)
    ldif.dump(args.output)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
