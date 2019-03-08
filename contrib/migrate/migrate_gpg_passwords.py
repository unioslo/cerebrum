#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2016 University of Oslo, Norway
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
This script migrates GPG encrypted passwords currently residing in the change
parameters for password change events to the entity_gpg_data table.

It does not modify the changelog in the process.
"""

import pickle
import base64
from collections import defaultdict

from Cerebrum.Utils import Factory

logger = Factory.get_logger('cronjob')


def migrate_passwords(db):
    """Migrates GPG messages saved in the change_log to the entity_gpg_data
    table."""
    clconst = Factory.get('CLConstants')(db)
    ac = Factory.get('Account')(db)

    stats = defaultdict(int)
    recipient = ac._tag_to_recipients['password'][0]
    logger.info("GPG recipient ID: {}".format(recipient))

    logger.info("Fetching password events...")
    for e in db.get_log_events(types=(clconst.account_password, )):
        stats['events'] += 1
        if stats['events'] % 1000 == 0:
            logger.info('{} events and counting...'.format(stats['events']))
        if not e['change_params']:
            stats['no-params'] += 1
            continue
        params = pickle.loads(e['change_params'])
        if not params:
            stats['no-params'] += 1
            continue
        stats['with-params'] += 1
        password_str = params.get('password', '')
        if password_str.startswith('GPG:'):
            stats['gpg-password'] += 1
            gpg_message = password_str[4:]
        else:
            stats['non-gpg-password'] = 1
            continue
        subject = e['subject_entity']
        tstamp = e['tstamp']
        ac.clear()
        ac.find(subject)
        message_id = ac.add_gpg_message(
            tag='password',
            recipient=recipient,
            message=gpg_message)
        db.execute(
            "UPDATE [:table schema=cerebrum name=entity_gpg_data] "
            "SET created=:created WHERE message_id=:message_id", {
                "created": tstamp,
                "message_id": message_id
            })

    logger.info("Statistics: {}".format(dict(stats)))


def main(args=None):
    """Main script runtime.

    This parses arguments and handles the database transaction.
    """
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('--commit',
                        default=False,
                        action='store_true',
                        help='Commit changes.')
    args = parser.parse_args(args)

    logger.info("START %s with args: %s", parser.prog, args.__dict__)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog.split('.')[0])

    try:
        migrate_passwords(db)
    except Exception:
        logger.error("Unexpected exception", exc_info=1)
        db.rollback()
        raise

    if args.commit:
        logger.info("Committing changes")
        db.commit()
    else:
        logger.info("Rolled back changes")
        db.rollback()

    logger.info("DONE %s", parser.prog)


if __name__ == '__main__':
    main()
