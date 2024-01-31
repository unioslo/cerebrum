#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
Process person from Greg and create/update user account.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.no.uit import greg_users
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.date import parse_date

logger = logging.getLogger(__name__)


def _get_account_owner_id(account):
    entity_type = account.const.EntityType(account.owner_type)
    if entity_type == account.const.entity_person:
        return account.owner_id
    raise LookupError("Invalid account owner type: "
                      + six.text_type(entity_type))


def find_person_id(db, args):
    pe = Factory.get("Person")(db)
    ac = Factory.get("Account")(db)

    if args.person_id is not None:
        try:
            pe.find(args.person_id)
            return pe.entity_id
        except NotFoundError:
            pass
        raise LookupError("Invalid person id: " + repr(args.person_id))

    if args.account_id is not None:
        try:
            ac.find(args.account_id)
            return _get_account_owner_id(ac)
        except NotFoundError:
            pass
        raise LookupError("Invalid account id: " + repr(args.account_id))

    if args.account_name:
        try:
            ac.find_by_name(args.account_name)
            return _get_account_owner_id(ac)
        except NotFoundError:
            pass
        raise LookupError("Invalid account name: " + repr(args.account_name))

    if args.greg_id:
        try:
            pe.find_by_external_id(id_type=pe.const.externalid_greg_pid,
                                   external_id=args.greg_id)
            return pe.entity_id
        except NotFoundError:
            pass
        raise LookupError("Invalid greg id: " + repr(args.greg_id))

    # Should not be possible to readh
    raise RuntimeError("No person identifier in args: " + repr(args))


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Update a single person/user",
        epilog="""
            This script updates a single user account from Greg-data.
        """.strip()
    )
    parser.add_argument(
        "--expire-date",
        type=parse_date,
        help="An expire-date to set/use",
        metavar="<iso-8601 date>",
    )

    person_args = parser.add_argument_group("Person")
    person_mutex = person_args.add_mutually_exclusive_group(required=True)
    person_mutex.add_argument(
        "--person-id",
        type=int,
        help="Get person by entity-id",
        metavar="<entity-id>",
    )
    person_mutex.add_argument(
        "--account-id",
        type=int,
        help="Get person by account entity-id",
        metavar="<entity-id>",
    )
    person_mutex.add_argument(
        "--account-name",
        help="Get person by account name",
        metavar="<username>",
    )
    person_mutex.add_argument(
        "--greg-id",
        help="Get person by greg-id",
        metavar="<greg-id>",
    )

    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    default_preset = 'tee' if args.commit else 'console'
    Cerebrum.logutils.autoconf(default_preset, args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get("Database")()
    db.cl_init(change_program=parser.prog)

    with db_context(db, not args.commit) as ctx:

        person_id = find_person_id(ctx, args)
        expire_date = args.expire_date
        greg_users.update_greg_person(db, person_id, expire_date)

    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
