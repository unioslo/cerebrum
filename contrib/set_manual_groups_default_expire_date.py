#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2019 University of Oslo, Norway
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
This script is used to set a default expire date for perishable manual groups.
"""

from __future__ import unicode_literals

from six import text_type

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.database import DatabaseError
from mx.DateTime import now

logger = Factory.get_logger('console')


def set_default_expire_dates(db, commit):
    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)
    grs = [g for g in gr.search(filter_expired=True, expired_only=False) if (
        g.group_type in {co.group_type_manual, co.group_type_unknown})]
    # Cerebrum.Group.search accepts group_type as an argument, but at the
    # moment, this function is overloaded by
    # Cerebrum.modules.virtualgroup.OUGroup.search which does not.
    k = 0
    for g in grs:
        gr.clear()
        gr.find(int(g[u'group_id']))
        if gr.expire_date is None:
            gr.set_default_expire_date()
            logger.info('group %i is set to expire at %s',
                        gr.entity_id, gr.expire_date)
            if commit:
                try:
                    gr.write_db()
                    k += 1
                except Exception as e:
                    logger.error('write_db for group %i failed with exception '
                                 '%s', gr.entity_id, e)
    logger.info('%i manual groups have been provided an expire_date', k)
    if commit:
        db.commit()
        logger.info('Changes commited')
    else:
        logger.info('Changes not commited')


def main(args=None):
    """
    This script provides all manual groups whose expire_date is None
    with a default value (typically one year into the future)
    """
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--commit',
                        action='store_true',
                        dest='commit',
                        default=False,
                        help='Commit changes')
    logger.info('START %s', parser.prog)
    args = parser.parse_args(args)
    db = Factory.get('Database')()
    db.cl_init(change_program='set_manual_groups_default_expire_date.py')
    set_default_expire_dates(db, args.commit)
    logger.info('DONE %s', parser.prog)


if __name__ == '__main__':
    main()
