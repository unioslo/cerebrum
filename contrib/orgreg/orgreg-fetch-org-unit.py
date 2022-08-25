#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
Fetch and show Orgreg org unit data from the API.

See :py:class:`Cerebrum.modules.orgreg.client.OrgregClientConfig` for
configuration instructions.
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
from Cerebrum.modules.orgreg import datasource
from Cerebrum.modules.orgreg.client import get_client
from Cerebrum.modules.orgreg.mapper import OrgregMapper
from Cerebrum.utils import json

logger = logging.getLogger(__name__)


def pformat(obj):
    """ format dict as json. """
    return json.dumps(obj, sort_keys=True, indent=2)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Fetch and show org unit info from Orgreg",
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help="Orgreg client config (see Cerebrum.modules.orgreg.client)",
    )
    parser.add_argument(
        'id',
        help='Orgreg id of the org unit to show',
    )

    format_grp = parser.add_argument_group('format')
    format_arg = format_grp.add_mutually_exclusive_group()
    format_arg.set_defaults(format="datasource")
    format_arg.add_argument(
        '-r', '--raw',
        action='store_const',
        const='raw',
        dest='format',
        help="Show raw JSON result from Orgreg API",
    )
    format_arg.add_argument(
        '--norm',
        action='store_const',
        const='datasource',
        dest='format',
        help="Show filtered/normalized org unit data (default)",
    )
    format_arg.add_argument(
        '--crb',
        action='store_const',
        const='mapper',
        dest='format',
        help="Show pre-processed data available to Cerebrum-import",
    )

    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'INFO',
    })

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    client = get_client(args.config)

    raw_data = client.get_org_unit(args.id)

    if not raw_data:
        print('invalid org unit id')
        raise SystemExit()

    if args.format == "raw":
        print(pformat(raw_data))
        raise SystemExit()

    org_unit = datasource.parse_org_unit(raw_data)

    if args.format == "datasource":
        print(pformat(org_unit))
        raise SystemExit()

    mapper = OrgregMapper()

    def nest_triplets(iterable):
        """ (a, b, c) -> {a: {b: c}}. """
        d = {}
        for a, b, c in iterable:
            sub = d.setdefault(a, {})
            sub[b] = c
        return d

    crb_info = {
        'addresses': dict(mapper.get_addresses(org_unit)),
        'contacts': dict(mapper.get_contact_info(org_unit)),
        'ids': dict(mapper.get_external_ids(org_unit)),
        'names': nest_triplets(mapper.get_names(org_unit)),
        'tree-info': {
            'location-code': mapper.get_location_code(org_unit),
            'node-id': mapper.get_id(org_unit),
            'node-parent-id': mapper.get_parent_id(org_unit),
            'valid': mapper.is_valid(org_unit),
            'visible': mapper.is_visible(org_unit),
        },
    }

    print(pformat(crb_info))


if __name__ == '__main__':
    main()
