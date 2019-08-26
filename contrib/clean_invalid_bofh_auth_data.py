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
"""Remove invalid bofh auth data.

The auth_op_target and auth_op_roles tables can contain entries that refers
to deleted entities. This script find and removed these entries.

Some parts of Cerebrum (see dns/Subnet.py) removes the BofhAuth data on delete.
We do not want Cerebrum to touch BofhdAuth butt removing it might brake stuff..
See CRB-2616.
"""

import argparse
import logging

import Cerebrum.logutils
from Cerebrum.Utils import Factory
from Cerebrum.database import DatabaseError
from Cerebrum.modules.bofhd.auth import BofhdAuthRole, BofhdAuthOpTarget

logger = logging.getLogger(__name__)


def main():
    """Remove invalid auth data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-c', '--commit',
        action='store_true',
        dest='commit',
        default=False,
        help='Actually remove the invalid auth data.'
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('START {0}'.format(parser.prog))
    db = Factory.get('Database')()
    db.cl_init(change_program='clean_invalid_bofh_auth_data.py')

    baot = BofhdAuthOpTarget(db)
    bar = BofhdAuthRole(db)
    bar_count = bar.count_invalid()
    baot_count = baot.count_invalid()

    try:
        bar.remove_invalid()
        baot.remove_invalid()

    except DatabaseError as e:
        db.rollback()
        logger.error(
            'Error removing invalid auth data {0}. Rolling back any changes'
            .format(e))
        raise

    bar_count_after = bar.count_invalid()
    baot_count_after = baot.count_invalid()

    logger.info('Removing {0} invalid entries in auth_roles'.format(
        bar_count - bar_count_after))
    logger.info('Removing {0} invalid entries in auth_op_targets'.format(
        baot_count - baot_count_after))

    if args.commit:
        logger.info('Committing changes.')
        db.commit()
    else:
        logger.info('Rolling back changes.')
        db.rollback()

    logger.info('DONE {0}'.format(parser.prog))


if __name__ == '__main__':
    main()
