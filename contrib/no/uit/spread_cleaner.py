#!/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
Remove expired account spreads (Cerebrum.modules.spread_expire)
"""

import argparse
import datetime
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Constants import _SpreadCode as SpreadCode
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args, get_constant
from Cerebrum.modules.spread_expire import SpreadExpire, SpreadExpireNotify

logger = logging.getLogger(__name__)


def delete_spread(db, spread_expire, spread, cutoff_date):
    try:
        int(spread)
    except Exception:
        logger.error("Invalid spread=%r", spread)
        raise
    logger.info("Cleaning spread %r", spread)
    ac = Factory.get('Account')(db)

    count = 0
    for row in spread_expire.search(spread=spread, before_date=cutoff_date):
        ac.clear()
        try:
            ac.find(row['entity_id'])
        except Errors.NotFoundError:
            # We only delete spreads on accounts for the time being
            continue

        logger.info("Removing spread=%r on account_id=%r (%s)",
                    spread, ac.entity_id, ac.account_name)
        try:
            ac.clear_home(spread)
        except Errors.NotFoundError:
            logger.warning("No homedir for account_id=%r spread=%s",
                           ac.entity_id, spread)
        ac.delete_spread(spread)
        count += 1

    logger.info("Removed %d spreads of type %s, ", count, spread)


def send_notifications(db, spread_expire, spread_expire_notify, cutoff_date):
    ac = Factory.get('Account')(db)

    after_date = cutoff_date - datetime.timedelta(days=1)

    for entity_id in {e['entity_id'] for e in spread_expire_notify.search()}:
        for row in spread_expire.search(entity_id=entity_id,
                                        after_date=after_date):
            expire_date = (row['expire_date'].pydate()
                           if row['expire_date']
                           else None)
            if expire_date:
                ac.notify_spread_expire(row['spread'],
                                        expire_date,
                                        row['entity_id'])


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Remove expired spreads",
    )
    spread_arg = parser.add_argument(
        '-s', '--spread',
        dest='spreads',
        action='append',
        help='Add a spread type to remove (default: all types)',
        metavar='<spread>',
    )
    parser.add_argument(
        '--days',
        dest='days',
        type=int,
        default=0,
        help='Set cutoff date to %(metavar)s days ago (default: %(default)s)',
        metavar='<days>',
    )

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)
    co = Factory.get('Constants')(db)
    spread_expire = SpreadExpire(db)
    spread_expire_notify = SpreadExpireNotify(db)

    if args.spreads:
        spreads = tuple(
            get_constant(db, parser, SpreadCode, value, spread_arg)
            for value in args.spreads)
        # TODO: Throw error if spread.entity_type is wrong?
    else:
        spreads = tuple(s for s in co.fetch_constants(SpreadCode)
                        if s.entity_type == co.entity_account)
    logger.info("Spreads: %r", map(six.text_type, spreads))

    cutoff = datetime.date.today() - datetime.timedelta(days=args.days)
    logger.info("Start date: %r", cutoff)

    for spread in spreads:
        if spread == co.spread_uit_exchange:
            logger.info("Skipping spread=%s", spread)
            continue
        elif spread.entity_type != co.entity_account:
            logger.info("Skipping spread=%s for entity_type=%s",
                        spread, spread.entity_type)
            continue
        else:
            logger.info("Processing spread: %s", spread)
        delete_spread(db, spread_expire, spread, cutoff)

    send_notifications(db, spread_expire, spread_expire_notify, cutoff)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
