#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018-2025 University of Oslo, Norway
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
Remove obsolete bofh auth data.

The `auth_op_target` and `auth_op_roles` tables can contain entries that refers
to deleted entities.  This script finds and removes these entries.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.bofhd.auth import BofhdAuthRole, BofhdAuthOpTarget

logger = logging.getLogger(__name__)


def clean_obsolete_targets(db):
    """Remove obsolete auth data."""
    op_targets = BofhdAuthOpTarget(db)
    auth_roles = BofhdAuthRole(db)

    before_count = {
        'roles': auth_roles.count_invalid(),
        'targets': op_targets.count_invalid(),
    }

    auth_roles.remove_invalid()
    op_targets.remove_invalid()

    after_count = {
        'roles': auth_roles.count_invalid(),
        'targets': op_targets.count_invalid(),
    }

    logger.info("Removed %d obsolete roles and %d obsolete targets",
                before_count['roles'] - after_count['roles'],
                before_count['targets'] - after_count['targets'])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Remove obsolete bofhd auth targets",
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    dryrun = not args.commit
    with db_context(Factory.get('Database')(), dryrun) as db:
        db.cl_init(change_program=parser.prog)
        clean_obsolete_targets(db)

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
