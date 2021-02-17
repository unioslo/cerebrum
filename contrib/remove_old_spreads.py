#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017 University of Oslo, Norway
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

import cereconf

from Cerebrum.Utils import Factory
import Cerebrum.logutils
import Cerebrum.logutils.options



def remove_spread(args):
    """Remove spread(s) from a entity_type"""

    db = Factory.get('Database')()
    const = Factory.get('Constants')(db)

    if args.accounts:
        entity_type = const.entity_account
        entity = Factory.get('Account')(db)
    if args.groups:
        entity_type = const.entity_group
        entity = Factory.get('Group')(db)
    if args.persons:
        entity_type = const.entity_person
        entity = Factory.get('Person')(db)

    for spread in args.spreads:
        res = entity.list_all_with_spread(spreads=spread,
                                          entity_types=entity_type)
        logger.info('Found {} {}s with the spread {}'.format(len(res),
                                                             str(entity_type),
                                                             str(spread)))

        j = 0
        for i in res:
            j += 1
            entity.clear()
            entity.find(i['entity_id'])
            entity.delete_spread(spread)
            if j % 1000 == 0:
                logger.info('...{}'.format(j))
            if j == args.limit:
                break
        logger.info('Removed {} from {} {}s'.format(str(spread), j,
                                                    str(entity_type)))


def main(args=None):
    """Main script runtime.

    This parses arguments and handles the database transaction.
    """

    import argparse
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-s', '--spread',
                        dest='spreads_human',
                        metavar='spread',
                        required=True,
                        action='append',
                        help='Spread to remove')

    parser.add_argument('-a', '--accounts',
                        action='store_true',
                        help='Remove from accounts')
    parser.add_argument('-g', '--groups',
                        action='store_true',
                        help='Remove from groups')
    parser.add_argument('-p', '--persons',
                        action='store_true',
                        help='Remove from persons')
    parser.add_argument('-l', '--limit',
                        type=int,
                        help='maximum entities to remove from')

    parser.add_argument('--commit',
                        default=False,
                        action='store_true',
                        help='Commit changes.')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(args)
    Cerebrum.logutils.autoconf('cronjob', args)

    if not (args.accounts or args.groups or args.persons):
        print('Must specify -a, -g or -p')
        raise SystemExit()

    args.spreads = []
    for s in args.spreads_human:
        spread = const.human2constant(s, const.Spread)
        if spread is None:
            raise SystemExit('{} is not a valid spread'.format(s))
        args.spreads.append(spread)

    logger.info("START %s", parser.prog)
    db.cl_init(change_program='remove_old_spreads')

    try:
        remove_spread(args)
    except Exception:
        logger.error("Unexpected exception", exc_info=1)
        db.rollback()
        raise

    if args.commit:
        logger.info("Commiting changes")
        db.commit()
    else:
        logger.info("Rolled back changes")
        db.rollback()

    logger.info("DONE %s", parser.prog)


if __name__ == '__main__':
    main()
