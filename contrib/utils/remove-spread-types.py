#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017-2026 University of Oslo, Norway
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
This script removes unwanted spreads from entities.
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

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Entity import EntitySpread
from Cerebrum.Utils import Factory
from Cerebrum.utils import aggregate
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def _get_entity(db, entity_type):
    type_str = six.text_type(entity_type)
    if type_str in Factory.type_component_map:
        return Factory.get(Factory.type_component_map[type_str])(db)
    else:
        return Factory.get("Entity")(db)


def select_entities(db, spreads):
    spread_map = {int(s): s for s in spreads}
    entity = EntitySpread(db)
    for row in entity.list_all_with_spread(spreads=spreads):
        yield row['entity_id'], spread_map[row['spread']]


def remove_spread(db, spreads, limit=0):
    """Remove spread(s) from a entity_type"""
    pretty_spreads = ", ".join(six.text_type(s) for s in spreads)
    entity_spread_map = aggregate.dict_collect_sets(
        select_entities(db, spreads))
    logger.info("Found %d entities with spreads %s",
                len(entity_spread_map), pretty_spreads)

    processed_entities = 0
    removed_spreads = 0
    for entity_id in sorted(entity_spread_map):
        entity_spreads = entity_spread_map[entity_id]
        entity_type = set(s.entity_type for s in entity_spreads)
        if len(entity_type) > 1:
            raise RuntimeError("Got multiple entity types for id: "
                               + repr(entity_id))
        entity_type = entity_type.pop()

        entity = _get_entity(db, entity_type)
        entity.find(entity_id)

        for spread in entity_spreads:
            if entity.has_spread(spread):
                entity.delete_spread(spread)
                logger.info("Removed spread %s from %s %d",
                            spread, entity_type, entity_id)
                removed_spreads += 1

        processed_entities += 1

        if limit and len(processed_entities >= limit):
            logger.info("Limit reached (%d)", processed_entities)
            break

    logger.info("Removed %d spreads from %d entities",
                removed_spreads, processed_entities)
    return removed_spreads


def main(argv=None):
    """Main script runtime.

    This parses arguments and handles the database transaction.
    """
    parser = argparse.ArgumentParser(
        description="Remove all spreads of the given type(s)",
    )

    parser.add_argument(
        "spread",
        nargs="+",
        help="Remove spread %(metavar)s",
        metavar="SPREAD",
    )

    spread_arg = parser.add_argument(
        "-l", "--limit",
        type=int,
        help="Limit to %(metavar)s entities",
        metavar="N",
    )
    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf_interactive(args)

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    spreads = []
    with argutils.ParserContext(parser, spread_arg):
        for raw_value in args.spread:
            spreads.append(const.get_constant(const.Spread, raw_value))

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))
    db.cl_init(change_program='remove_old_spreads')

    n = remove_spread(db, spreads)

    logger.info("Finalizing %d changes (commit=%s)", n, args.commit)
    if args.commit:
        db.commit()
        logger.info("Commited changes")
    else:
        db.rollback()
        logger.info("Rolled back changes")

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
