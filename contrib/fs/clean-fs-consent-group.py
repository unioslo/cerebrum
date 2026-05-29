#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 University of Oslo, Norway
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
""" Remove obsolete members from FS consent group. """
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
from Cerebrum.group import group_sync
from Cerebrum.modules.fs import fs_group
from Cerebrum.database.ctx import db_context
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def get_account_by_name(db, name):
    ac = Factory.get("Account")(db)
    ac.find_by_name(name)
    return ac


def get_fs_persons(db):
    pe = Factory.get("Person")(db)
    return set(
        row['person_id']
        for row in pe.list_affiliations(source_system=pe.const.system_fs))


def update_group(db):
    group = fs_group.get_fs_consent_group(db)
    members = group_sync.get_current_members(group)
    logger.debug("found %d members of %s (%d)",
                 len(members), group.group_name, group.entity_id)
    fs_people = get_fs_persons(db)
    logger.debug("found %d people with fs affiliations",
                 len(fs_people))

    to_keep = members & fs_people
    group_sync.set_group_members(group, to_keep)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Remove obsolete members from FS consent group",
    )
    args_db = parser.add_argument_group("Database")
    argutils.add_commit_args(args_db)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("cronjob", args)

    db = Factory.get('Database')()
    logger.info("Start: %s", parser.prog)
    logger.debug("args: %s", repr(args))
    with db_context(db, dryrun=not args.commit):
        db.cl_init(change_program=parser.prog)
        update_group(db)

    logger.info("Done: %s", parser.prog)


if __name__ == '__main__':
    main()
