#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2013, 2017 University of Oslo, Norway
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
"""This script has functionality for finding, categorizing, counting and
setting expire dates on fronter groups"""

from __future__ import print_function, unicode_literals
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.fs.fs_group import FsGroupCategorizer, get_groups
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def set_fronter_group_expire_dates(db, group_expirations):
    gr = Factory.get('Group')(db)
    for group_name, expire_date in group_expirations.items():
        gr.clear()
        gr.find_by_name(group_name)
        gr.expire_date = expire_date
        gr.write_db()
        logger.debug('Set expire_date %s for group %s',
                     expire_date,
                     group_name)


def main(inargs=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-e', '--expire-groups',
        action='store_true',
        help='Set expire dates on groups that should have an expire date',
    )
    add_commit_args(parser)

    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    fronter_group_categorizer = FsGroupCategorizer(db)

    general_stats, specific_stats, group_expirations = (
        fronter_group_categorizer.categorize())
    for k, v in sorted(specific_stats.items()):
        print('%s: %s' % (k, v))
    for k in sorted(general_stats):
        print('%s: %s' % (k, general_stats[k]))

    if args.expire_groups:
        logger.info('Setting expire dates')
        set_fronter_group_expire_dates(db, group_expirations)

        if args.commit:
            db.commit()

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
