#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
"""Update spreads of automatic groups

Spreads are added based on config rules. This does not remove any spreads
currently.
"""
from __future__ import unicode_literals
import logging
import argparse
import six

from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules.automatic_group.spreads import (load_rules,
                                                      assert_spreads,
                                                      select_group_ids)
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def process_spreads(gr, rules):
    for name, (spreads, filters) in six.iteritems(rules):
        logger.info('Processing rule: %s', name)
        log_spreads = [six.text_type(s) for s in spreads]
        for group_id in select_group_ids(gr, filters):
            logger.info('Group: %s should have spreads: %s',
                        group_id,
                        log_spreads)
            assert_spreads(gr, group_id, spreads)


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-n', '--names',
        action='append',
        type=six.text_type,
        help='Which rules from the config should be processed?',
        required=True
    )
    add_commit_args(parser)

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)
    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)
    rules = load_rules(co, args.names)
    process_spreads(gr, rules)
    if args.commit:
        logger.info('Committing changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done with %s', parser.prog)


if __name__ == '__main__':
    main()
