#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
Update Cerebrum.modules.stillingskoder from a CSV file.

This program reads a csv file with employment codes, and syncs the Cerebrum
database with that information.

Each CSV row should contain three fields:
    Stillingskode,Stillingsbetegnelse;UiT Stillingskategori
"""
from __future__ import unicode_literals

import argparse
import csv
import logging
import operator

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.stillingskoder import Stillingskoder
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args


logger = logging.getLogger(__name__)

default_encoding = 'utf-8'
default_charsep = ';'


def read_csv_file(filename,
                  encoding=default_encoding,
                  charsep=default_charsep):
    logger.info("reading csv file=%r (encoding=%r, charsep=%r)",
                filename, encoding, charsep)
    with open(filename, mode='rb') as f:
        for data in csv.DictReader(f, delimiter=charsep.encode(encoding)):
            yield {k.decode(encoding): v.decode(encoding)
                   for k, v in data.items()}


tuple_map = (
    operator.itemgetter('Stillingskode'),
    operator.itemgetter('Stillingsbetegnelse'),
    operator.itemgetter('UiT Stillingskategori'),
)


def generate_tuples(items):
    for item in items:
        yield tuple((getter(item) for getter in tuple_map))


def sync_stillingskoder(db, tuples):
    """
    :param tuples:
        An iterable with employment code tuples. Each tuple should consist of
        (code, title, category).
    """
    skos = Stillingskoder(db)
    old_codes = {r['code']: (r['title'], r['category']) for r in skos.search()}
    new_codes = {int(code): (title, cat) for code, title, cat in tuples}

    old_set = set(old_codes.keys())
    new_set = set(new_codes.keys())

    logger.info("Before sync: %d employment codes in db", len(old_set))

    to_add = new_set.difference(old_set)
    to_delete = old_set.difference(new_set)
    to_update = new_set.intersection(old_set)

    # add new
    for skode in to_add:
        sben, skat = new_codes[skode]
        skos.set(skode, sben, skat)
        logger.info("Added code=%04d, title=%r, category=%r",
                    skode, sben, skat)
    logger.info("Added %d codes", len(to_add))

    # remove old
    for skode in to_delete:
        sben, skat = old_codes[skode]
        skos.delete(skode)
        logger.info("Removed code=%04d, title=%r, category=%r",
                    skode, sben, skat)
    logger.info("Removed %d codes", len(to_delete))

    # update remaining
    updated = False
    for skode in to_update:
        if old_codes[skode] != new_codes[skode]:
            skos.set(skode, new_codes[skode][0], new_codes[skode][1])
            updated += 1
            logger.info("Updated code=%04d, old=%r, new=%r",
                        skode, old_codes[skode], new_codes[skode])
    logger.info("Updated %d codes", updated)
    logger.info("After sync: %d employment codes in db", len(new_set))


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Import employment codes",
    )
    parser.add_argument(
        'filename',
        dest='filename',
        help="Import employment codes from %(metavar)s",
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    sync_stillingskoder(db, generate_tuples(read_csv_file(args.filename)))

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
