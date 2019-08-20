#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2015-2018 University of Oslo, Norway
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
This script generates a set of events, that will result in provisioning of
users in CIM.
"""

import cereconf
getattr(cereconf, 'linter', '')

from Cerebrum.Utils import Factory

logger = Factory.get_logger('cronjob')


def uname2pid(db, username):
    """Convert a username to a person_id.

    :param Cerebrum.database.Database db: The database connection
    :param basestring username: The username
    """
    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    ac.find_by_name(username)
    pe.find(ac.owner_id)
    return [pe.entity_id]


def collect_candidates(db):
    """Collect candidates for provisioning to CIM.

    :param Cerebrum.database.Database db: The database connection
    """
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)
    return set([x['person_id'] for x in pe.search(
        spread=co.spread_cim_person)])


def generate_events(db, collector=collect_candidates):
    """Generate events that should result in provisioning of users in CIM.

    :param Cerebrum.database.Database db: The database connection
    :param function collector: The collector for selecting candidates
    """
    const = Factory.get('Constants')(db)
    clconst = Factory.get('CLConstants')(db)
    for person_id in collector(db):
        logger.info('Creating faux spread:add for person_id:%d', person_id)
        db.log_change(subject_entity=person_id,
                      change_type_id=clconst.spread_add,
                      change_params={'spread': int(const.spread_cim_person)},
                      destination_entity=None, skip_change=True)


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
    parser.add_argument('--username',
                        dest='username',
                        metavar='<username>',
                        help='Force provisioning of person related to '
                             '<username>')
    args = parser.parse_args(args)

    logger.info("START %s with args: %s", parser.prog, args.__dict__)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog.split('.')[0])

    collector = tuple()
    if args.username:
        import functools
        collector = (
            functools.partial(
                uname2pid, **{'username': args.username}),)

    try:
        generate_events(db, *collector)
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
