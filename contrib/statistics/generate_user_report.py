#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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
""" Generate a report over persons and user accounts.

This script produces a report over people, their usernames and their
activity statuses.

For each person in the database we report the following:

* fnr[1]
* all user names
* activity status[2]

[1] Should the person have multiple different fnrs, the one listed first in
--fnr-systems is used as the selection basis. If none are specified,
cereconf.SYSTEM_LOOKUP_ORDER is respected.

[2] A *person* with at least one valid affiliation is considered active. All
others are inactive.

This job has been requested for ØFK, but it could be used at any institution
using Cerebrum.
"""
import argparse
import logging
import sys
from collections import defaultdict

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type, get_constant

logger = logging.getLogger(__name__)


def get_account_data(db, id_type, source_systems):
    pe = Factory.get("Person")(db)
    ac = Factory.get("Account")(db)
    co = Factory.get("Constants")(db)

    def _u(db_value):
        if db_value is None:
            return u''
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return db_value

    has_affiliation = set(row['person_id'] for row in pe.list_affiliations())
    logger.debug('cached person_id of %d persons with affs',
                 len(has_affiliation))

    extid_cache = defaultdict(dict)
    for r in pe.list_external_ids(id_type=id_type,
                                  entity_type=co.entity_person):
        if r['source_system'] not in source_systems:
            continue
        extid_cache[r['entity_id']][r['source_system']] = r['external_id']
    logger.debug('cached external id for %d persons', len(extid_cache))

    account_cache = defaultdict(list)
    for row in ac.search(owner_type=co.entity_person,
                         expire_start=None):
        account_cache[row['owner_id']].append(row['name'])
    logger.debug('cached accounts for %d persons', len(account_cache))

    status_map = {True: "aktiv", False: "inaktiv"}

    for row in pe.list_persons():
        pid = row["person_id"]

        ext_id = None
        ext_ids = extid_cache[pid]
        for src in source_systems:
            if src in ext_ids:
                ext_id = ext_ids[src]
                break

        for account_name in account_cache[pid]:
            yield {
                'person_id': pid,
                'external_id': _u(ext_id),
                'account_name': _u(account_name),
                'status': status_map[pid in has_affiliation],
            }


def write_report(stream, codec, iterable):
    output = codec.streamwriter(stream)
    # TODO: This looks CSV-ish, use csv?
    for data in iterable:
        output.write("%(external_id)s:%(account_name)s:%(status)s\n" % data)
    output.write("\n")


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate a report on persons and accounts")

    parser.add_argument(
        '-f', '--file',
        dest='output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='Output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="Output file encoding, defaults to %(default)s")

    id_source_arg = parser.add_argument(
        '-s', '--fnr-systems',
        dest='id_source_systems',
        type=lambda v: [s.strip() for s in v.split(',')],
        help='Ordered, comma-separated list of external id preference,'
             ' defaults to cereconf.SYSTEM_LOOKUP_ORDER')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get("Database")()
    co = Factory.get("Constants")(db)

    source_systems = [
        get_constant(db, parser, co.AuthoritativeSystem, value, id_source_arg)
        for value in (args.id_source_systems or cereconf.SYSTEM_LOOKUP_ORDER)]
    logger.debug("source_systems: %r", source_systems)

    account_iter = get_account_data(db,
                                    co.externalid_fodselsnr,
                                    source_systems)

    write_report(args.output, args.codec, account_iter)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == "__main__":
    main()
