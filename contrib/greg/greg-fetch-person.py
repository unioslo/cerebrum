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
Fetch and show Greg person data from the API.

See :py:class:`Cerebrum.modules.greg.client.GregClientConfig` for
configuration instructions.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import io
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.greg import datasource
from Cerebrum.modules.greg.client import get_client
from Cerebrum.modules.greg.importer import get_import_class
from Cerebrum.utils import json

logger = logging.getLogger(__name__)


def pformat(obj):
    """ format dict as json. """
    return json.dumps(obj, sort_keys=True, indent=2)


def pretty_kv(d, indent='  ', _level=0):
    """ format dict as indented key/value pairs. """
    buf = io.StringIO()
    for key in sorted(d):
        value = d[key]
        print(indent * _level, six.text_type(key), sep='', end=':', file=buf)
        if isinstance(value, dict):
            print('', file=buf)
            print(pretty_kv(value, indent=indent, _level=_level + 1), file=buf)
        else:
            print('', six.text_type(repr(value)), file=buf)
    return buf.getvalue()


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Fetch and show person info from Greg',
    )
    parser.add_argument(
        '-c', '--config',
        required=True,
        help="Greg client config (see Cerebrum.modules.greg.client)",
    )
    parser.add_argument(
        '-r', '--raw',
        action='store_true',
        default=False,
        help="Show raw JSON data from the API",
    )
    parser.add_argument(
        'reference',
        help='Greg person id to show',
    )

    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'INFO',
    })

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    client = get_client(args.config)

    raw_person = client.get_person(args.reference)
    mapper = get_import_class().mapper

    if args.raw:
        print(pformat(raw_person))
        raise SystemExit()

    if not raw_person:
        print('invalid person id')
        raise SystemExit()

    greg_person = datasource.parse_person(raw_person)
    crb_info = {
        'is_active': mapper.is_active(greg_person),
        'name': dict(mapper.get_names(greg_person)),
        'contact_info': dict(mapper.get_contact_info(greg_person)),
        'external_id': dict(mapper.get_person_ids(greg_person)),
        'affiliation': {
            aff: {'at-ou': ou, 'aff-begin': str(start), 'aff-end': str(end)}
            for aff, ou, start, end
            in mapper.get_affiliations(greg_person)
        },
    }

    print('Person object:')
    print(pformat(greg_person))
    print()
    print(pretty_kv(crb_info))


if __name__ == '__main__':
    main()
