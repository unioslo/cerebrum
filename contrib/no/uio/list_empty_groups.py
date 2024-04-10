#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2024 University of Oslo, Norway
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
List empty groups.

This script lists groups that either do not have assigned members or contain
only expired members, and thus may probably be eligible to removal.  The
information returned is ID, name, description (if available), group's admin (if
available).
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
from Cerebrum.group.GroupRoles import GroupRoles
from Cerebrum.Utils import Factory, make_timer
from Cerebrum.Entity import EntityName
from Cerebrum.utils import file_stream

logger = logging.getLogger(__name__)


def list_all_groups(db):
    """ List all groups to check. """
    group = Factory.get('Group')(db)
    count = 0
    for count, row in enumerate(group.search(), 1):
        yield {
            'group_id': row['group_id'],
            'group_name': row['name'],
            'group_desc': row['description'],
        }
    logger.info("found %d groups", count)


def select_empty_groups(db, items):
    group = Factory.get('Group')(db)
    logger.debug("caching non-empty groups...")
    non_empty = set(r['group_id']
                    for r in group.search_members(member_filter_expired=True))

    empty = 0
    logger.debug("filtering empty groups...")
    for item in items:
        if item['group_id'] in non_empty:
            continue
        empty += 1
        yield item

    logger.info("found %d empty groups", empty)


def update_group_roles(db, items):
    co = Factory.get('Constants')(db)

    logger.debug('caching names...')
    type_to_domain = {
        int(co.get_constant(co.EntityType, k)):
        int(co.get_constant(co.ValueDomain, v))
        for k, v in cereconf.ENTITY_TYPE_NAMESPACE.items()}

    names = {
        (int(r['entity_id']), int(r['value_domain'])): r['entity_name']
        for r in EntityName(db).list_names(
            value_domain=list(type_to_domain.values()),
        )}

    type_to_text = {
        int(c): six.text_type(c)
        for c in co.fetch_constants(co.EntityType)}

    logger.debug('caching roles...')
    roles = GroupRoles(db)
    roles_by_group = {}

    for row in roles.search_admins():
        if row['group_id'] not in roles_by_group:
            roles_by_group[row['group_id']] = []
        roles_by_group[row['group_id']].append((
            int(row['admin_id']),
            int(row['admin_type']),
        ))

    logger.debug('updating roles...')
    for item in items:
        item_roles = item['group_roles'] = []
        raw_roles = roles_by_group.get(item['group_id']) or ()
        for (admin_id, admin_type) in raw_roles:
            admin_name = None
            domain = type_to_domain.get(admin_type)
            if domain:
                admin_name = names.get((admin_id, domain))
            item_roles.append(
                " ".join([
                    type_to_text.get(admin_type),
                    admin_name or ("#%d" % (admin_id,)),
                    "Group-admin"
                ])
            )


def print_report(items, output_stream):
    # TODO: Would probably be more useful as a formatted yaml export.
    def write(*args):
        print(*args, file=output_stream)

    for item in items:
        write("ID:", six.text_type(item['group_id']))
        write("Name:", six.text_type(item['group_name']))
        if item.get('group_desc'):
            write("Description:", six.text_type(item['group_desc']))
        if item.get('group_roles'):
            for role in item['group_roles']:
                write("Admin:", six.text_type(role))
        write("")


STDOUT_NAME = "-"


def main(argv=None):
    parser = argparse.ArgumentParser(description="List empty groups")
    parser.add_argument(
        "-f",
        dest="output_filename",
        default=STDOUT_NAME,
        help="write output to %(metavar)s (default: stdout)",
        metavar="FILE",
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)

    Cerebrum.logutils.autoconf("console", args)
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get("Database")()

    timer = make_timer(logger)

    logger.debug("searching groups...")
    all_groups = list(list_all_groups(db))
    timer("listed groups")

    logger.debug("filtering empty groups...")
    empty_groups = list(select_empty_groups(db, all_groups))
    timer("filtered groups")

    logger.debug("finding group owners...")
    update_group_roles(db, empty_groups)
    timer("found group owners")

    with file_stream.get_output_context(
            filename=args.output_filename,
            encoding="utf-8",
            stdout=STDOUT_NAME,
            stderr=None,
    ) as fd:
        logger.debug("writing results to %s", repr(fd))
        print_report(empty_groups, fd)

    logger.info("wrote results to %s", args.output_filename)
    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
