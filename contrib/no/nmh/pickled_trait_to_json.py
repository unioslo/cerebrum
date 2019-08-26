#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway
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
"""This script migrates the fagfelt trait at NMH from pickle to JSON."""

def collect(person, trait):
    return [row for row in person.list_traits(trait)]


def alter(person, trait, row):
        import pickle
        import json
        new = json.dumps([unicode(x, 'latin1') for
                          x in pickle.loads(row['strval'])])

        person.clear()
        person.find(row['entity_id'])
        person.populate_trait(
            code=trait,
            date=row['date'],
            strval=new)
        person.write_db()
        return ('{!r}'.format(row['strval']), new)


if __name__ == '__main__':
    from Cerebrum.Utils import Factory
    logger = Factory.get_logger('cronjob')
    database = Factory.get('Database')()
    person = Factory.get('Person')(database)
    constants = Factory.get('Constants')(database)

    import argparse
    parser = argparse.ArgumentParser(
        description='Convert pickled fagfelt trait values to JSON')
    parser.add_argument('--commit',
                        action='store_true',
                        help='Run in commit mode (default: false)')
    args = parser.parse_args()
    database.cl_init(change_program=parser.prog)


    logger.info('%s started in %s mode',
                parser.prog,
                'commit' if args.commit else 'rollback')
    for row in collect(person, constants.trait_fagomrade_fagfelt):
        try:
            (old, new) = alter(person,
                               constants.trait_fagomrade_fagfelt,
                               row)
            logger.info('Converted %s to %s for person_id %s',
                        old,
                        new,
                        row['entity_id'])
        except Exception, exc:
            logger.warn(
                'Could not convert pickle to JSON for person_id:%s, %s',
                row['entity_id'],
                exc)
    if args.commit:
        database.commit()
    logger.info('%s done', parser.prog)
