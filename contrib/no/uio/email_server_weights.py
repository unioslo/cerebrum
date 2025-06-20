#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005-2025 University of Oslo, Norway
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
Updates the weight traits associated with the email servers.

For a user to be assigned to a given IMAP server, the server needs a weight
trait - only weighted servers will considered for new email accounts.

Each user has a given email quota, which takes up a portion of the total
available disk space on the server.  As more and more accounts eat up available
disk space, this script will re-calculate server weights to prioritize other
IMAP servers for new accounts.

Some IMAP servers may not be suitable for hosting personal email accounts
(e.g.  servers for hosting mailing lists).  These can be excluded from the
weight calculation by providing one or more exclude regex patterns with
--exclude.  Matching server names will not be assigned a weight trait
(and any existing weight trait will be removed).

The weight algorithm is simple: Each server gets a weights value based on the
difference between its currently assigned quota and the maximum assigned
quota.  See
:meth:`Cerebrum.modules.no.uio.Account.AccountUiOMixin._pick_email_server` for
implememtation details.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging
import re

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.Email import EmailQuota, EmailServer
from Cerebrum.modules.EmailConstants import _EmailServerTypeCode
from Cerebrum.utils import argutils


logger = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Re-calculate email server weights",
    )
    server_type_arg = parser.add_argument(
        "--server-type",
        action="store",
        help="Only consider email servers of type %(metavar)s",
        metavar="<type>",
    )
    regex_arg = parser.add_argument(
        "--exclude", "--except",
        dest="patterns",
        action='append',
        help=(
            "Do not consider email servers with hostname matching "
            " any %(metavar)s (can be repeated)"
        ),
        metavar="<regex>",
    )
    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("cronjob", args)
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    server_type = combined_pattern = None
    db = Factory.get('Database')()

    # Normalize --server-type
    if args.server_type:
        server_type = argutils.get_constant(
            db, parser, _EmailServerTypeCode, args.server_type,
            argument=server_type_arg)
    logger.info("Considering server type: %s",
                "<all>" if server_type is None else six.text_type(server_type))

    # Normalize --except
    patterns = []
    with argutils.ParserContext(parser, regex_arg):
        for raw_pattern in args.patterns:
            try:
                patterns.append(re.compile(raw_pattern))
            except Exception:
                logger.error("Invalid pattern: %s", repr(raw_pattern))
                raise
    if patterns:
        combined_pattern = re.compile(
            "(?:" + ")|(?:".join(p.pattern for p in patterns) + ")"
        )
    logger.info("Considering hostnames matching: %s",
                ".*" if combined_pattern is None else combined_pattern.pattern)

    with db_context(db, dryrun=not args.commit):
        db.cl_init(change_program="e_srv_weights")
        process_servers(db, server_type, combined_pattern)

    logger.info("Done %s", parser.prog)


def process_servers(db, server_type, exclude_regex):
    es = EmailServer(db)
    eq = EmailQuota(db)
    weight_trait = es.const.trait_email_server_weight

    # This lists all hosts, so we need to filter on server_type later.
    current_weights = {
        int(row['entity_id']): row['numval']
        for row in es.list_traits(weight_trait)
    }
    logger.info("Found %d weighted servers", len(current_weights))

    assigned = {}
    server_ident = {}
    for row in es.list_email_server_ext(server_type=server_type):
        # To assist with more meaningful log records:
        srv_id = int(row['server_id'])
        server_ident[srv_id] = "%s (%d)" % (row['name'], srv_id)

        if exclude_regex and exclude_regex.match(row['name']):
            logger.debug("Skipping server %s - excluded by pattern",
                         server_ident[srv_id])
            continue

        quota_stats = eq.get_quota_stats_by_server(srv_id)
        assigned[srv_id] = int(quota_stats['total_quota'] or 0)
        logger.debug("Current assigned quota for %s: %d",
                     server_ident[srv_id], assigned[srv_id])
    logger.info("Found %d candidate servers", len(assigned))

    # Note that we add 10% to the max value - this is to avoid weird skew
    # problems when the assigned server quotas are similar (e.g. when
    # starting out a new installation).  The max_weight boost ensures that
    # every server has a chance of getting new users, even the server with the
    # most currently assigned quota.
    max_weight = (max(assigned.values()) * 110) // 100

    for srv_id, quota in assigned.items():
        current_weight = current_weights.pop(srv_id, None)
        es.clear()
        es.find(srv_id)
        # We add 1 to handle an edge-case where there's only candidate server
        new_weight = max_weight - quota + 1
        if current_weight != new_weight:
            logger.info("Updating weight from %s to %s for %s",
                        repr(current_weight), repr(new_weight),
                        server_ident[srv_id])
            es.populate_trait(weight_trait, numval=new_weight)
            es.write_db()

    for obsolete_id, obsolete_value in current_weights.items():
        es.clear()
        es.find(obsolete_id)
        if server_type is None or es.email_server_type == server_type:
            logger.info("Deleting obsolete weight (%d) for %s (%d)",
                        obsolete_value, es.name, es.entity_id)
            es.delete_trait(weight_trait)


if __name__ == '__main__':
    main()
