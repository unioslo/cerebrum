#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2017-2019 University of Oslo, Norway
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
Remove CIM-spreads for multiple persons.

Reads a file of person_id values (one per line), and removes CIM spread for
those persons.
"""
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)


def update_entity_spreads(entity, to_add, to_remove):
    """
    Update spreads for a single entity

    :type entity: Cerebrum.Entity.EntitySpread
    :type to_add: tuple
    :type to_remove: tuple
    """
    spreads = [r['spread'] for r in entity.get_spread()]

    for spread in (s for s in to_add if int(s) not in spreads):
        logger.info("Adding spread=%s to entity_id=%r",
                    spread, entity.entity_id)
        entity.add_spread(spread)

    for spread in (s for s in to_remove if int(s) in spreads):
        logger.info("Removing spread=%s from entity_id=%r",
                    spread, entity.entity_id)
        entity.delete_spread(spread)


def update_spreads(db, person_ids, to_add=None, to_remove=None):
    """
    Update spreads for a list of persons.

    :type db: Cerebrum.database.Database
    :param person_ids:
        An iterable of person_id integers to process.
    :param to_add:
        An iterable of SpreadCode values to add to each person.
    :type to_remove:
        An iterable of SpreadCode values to remove from each person.
    """
    to_add = tuple(to_add or ())
    to_remove = tuple(to_remove or ())
    if any(to_add + to_remove):
        logger.info("Updating spreads, to_add=%r, to_remove=%r",
                    to_add, to_remove)
    else:
        logger.warning("No spreads to update, to_add=%r, to_remove=%r",
                       to_add, to_remove)
        return

    pe = Factory.get('Person')(db)

    for person_id in person_ids:
        pe.clear()
        try:
            pe.find(person_id)
        except Errors.NotFoundError:
            logger.error("No person with person_id=%r", person_id)
            continue

        update_entity_spreads(pe, to_add, to_remove)


def read_integers(filename):
    """Read integers from a file, one value per line."""
    logger.info("Reading integers from %r", filename)
    count = 0
    with open(filename, 'r') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                yield int(line)
                count += 1
            except Exception as e:
                logger.error("Invalid value on line %d: %s (%s)",
                             lineno, line, e)
                continue
    logger.info("Found %d integers in %r", count, filename)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Remove CIM-spread from a list of persons",
    )
    parser.add_argument(
        'filename',
        help="Remove spread from person_ids in %(metavar)s",
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('tee', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program='add_cim_spread')
    co = Factory.get('Constants')(db)

    update_spreads(
        db,
        read_integers(args.filename),
        to_add=None,
        to_remove=(co.spread_cim_person, ),
    )

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        db.rollback()
        logger.info('Rolling back changes')
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
