#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2025 University of Oslo, Norway
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
Delete AD-traits for a given account.

Usage: remove_all_ad_traits.py [--dryrun|--commit] username
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
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def remove_ad_traits(db, uname):
    ac = Factory.get('Account')(db)
    ac.find_by_name(uname)
    # Not sure how useful AccountHiOfMixin.delete_ad_attrs is - the method
    # fails if *any* of the `cereconf.AD_TRAIT_TYPES` traits are missing from
    # the account.
    ac.delete_ad_attrs()
    logger.info("Deleted all ad traits for %s (%d)",
                ac.account_name, ac.entity_id)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Remove AD-related traits from a given user",
    )
    parser.add_argument(
        "username",
        help="username to remove traits for",
    )
    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    default_log_preset = "tee" if args.commit else "console"
    Cerebrum.logutils.autoconf(default_log_preset, args)

    db = Factory.get('Database')()
    db.cl_init(change_program="remove_ad_traits")
    remove_ad_traits(db, args.username)

    if args.commit:
        logger.info("Committing changes")
        db.commit()
    else:
        logger.info("Rolling back changes (dryrun)")
        db.rollback()


if __name__ == '__main__':
    main()
