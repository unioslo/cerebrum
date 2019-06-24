#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2017-2019 University of Tromso, Norway
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

import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit import legacyusers
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def delete_account(db, account_id, commit=False):
    logger.info("Processing account_id=%r", account_id)
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)
    try:
        ac.find(account_id)
    except Errors.NotFoundError:
        raise SystemExit('Unknown account_id: {}'.format(account_id))
    legacyusers.delete(db, accountname=ac.get_name(co.account_namespace),
                       commit=commit)


def process_account(db, account_id, commit):
    try:
        delete_account(db,
                       account_id=account_id,
                       commit=commit)
    except Exception:
        logger.critical('Unable to delete account_id=%r', account_id)
        raise


def read_integers(filename):
    """Read integers from a file, one value per line."""
    logger.info("Reading integers from %r", filename)
    count = 0
    with open(filename, 'r') as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                field = line.split(',')[0]
                yield int(field)
                count += 1
            except Exception as e:
                logger.error("Invalid value on line %d: %s (%s)",
                             lineno, line, e)
                continue
    logger.info("Found %d integers in %r", count, filename)


def main(inargs=None):
    parser = argparse.ArgumentParser(description="Delete accounts")
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument(
        '-f', '--file',
        dest='filename',
        help="Delete account_ids found in %(metavar)s",
        metavar='filename',
    )
    what.add_argument(
        '-a', '--account',
        dest='account_id',
        type=int,
        help="Delete account with %(metavar)s",
        metavar='account_id',
    )
    add_commit_args(parser, default=False)

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('tee', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()

    if args.filename:
        for account_id in read_integers(args.filename):
            process_account(db, account_id, args.commit)
    else:
        process_account(db, args.account_id, args.commit)

    if args.commit:
        logger.info('Committing changes')
    else:
        logger.info('Rolling back changes')
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
