#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2025 University of Oslo, Norway
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
Script for removing change types from changelog, etc...

Caveats
--------
This will remove audit log history.

--------
The basic code for this script was moved from `makedb.py` to reduce clutter and
complexity.  Also, this option was undocumented, and only touched mod_changelog
-- not sure we ever actually want to do this.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging
import textwrap

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Constants
from Cerebrum.database.ctx import db_context
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils.sorting import make_priority_lookup

logger = logging.getLogger(__name__)


def get_superfluous_codes(const):
    """ Get change types that aren't defined in code. """
    return [
        Constants._ChangeTypeCode(c_int)
        for c_type, c_int, c_str in const._get_superfluous_codes()
        if c_type is Constants._ChangeTypeCode
    ]


def _delete_rows_by_key(db, table, key, value):
    """ Delete rows from *table* where *key* = *value* """
    logger.debug("deleting from table %s where %s=%s",
                 table, key, repr(value))
    num = db.query_1(
        "SELECT count(*) from {} where {} = :value".format(table, key),
        {'value': value},
    )
    logger.debug("found %d rows to delete from table %s", num, table)
    db.execute(
        "DELETE FROM {} where {} = :value".format(table, key),
        {'value': value},
    )
    return num


def delete_audit_entries(db, code):
    if not isinstance(code, Constants._ChangeTypeCode):
        raise ValueError("Invalid change type: " + repr(code))

    logger.info("Removing audit log records of type %s", repr(code))
    deleted = _delete_rows_by_key(db, "audit_log", "change_type", int(code))
    logger.info("Deleted %d audit log records of type %s",
                deleted, repr(code))


def delete_change_entries(db, code):
    if not isinstance(code, Constants._ChangeTypeCode):
        raise ValueError("Invalid change type: " + repr(code))

    logger.info("Removing change log entries of type %s", repr(code))
    deleted = _delete_rows_by_key(db, "change_log", "change_type_id",
                                  int(code))
    logger.info("Deleted %d change log entries for type %s",
                deleted, repr(code))


def delete_event_entries(db, code):
    if not isinstance(code, Constants._ChangeTypeCode):
        raise ValueError("Invalid change type: " + repr(code))

    logger.info("Removing event mappings for event type %s", repr(code))
    deleted = _delete_rows_by_key(db, "event_to_target", "event_type",
                                  int(code))
    logger.info("Deleted %d event mappings for event type %s",
                deleted, repr(code))

    logger.info("Removing events of event type %s", repr(code))
    deleted = _delete_rows_by_key(db, "event_log", "event_type", int(code))
    logger.info("Deleted %d events of event type %s", deleted, repr(code))


LOG_MAP = {
    'event': delete_event_entries,
    'change': delete_change_entries,
    'audit': delete_audit_entries,
}
# Preferred delete order
LOG_ORDER_KEY = make_priority_lookup(("event", "change", "audit"))


def log_type(raw_value):
    key = raw_value.strip().lower()
    if key in LOG_MAP:
        return key
    raise ValueError("invalid value")


def main(argv=None):
    log_text_list = "\n".join("  - {}".format(n) for n in sorted(LOG_MAP))
    parser = argparse.ArgumentParser(
        description="Delete entries of a given change type from changelogs",
        epilog=textwrap.dedent(
            """
            Logs:
            {}
            """
        ).strip().format(log_text_list),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    log_mutex = parser.add_mutually_exclusive_group(required=True)
    log_mutex.add_argument(
        "--log",
        action="append",
        type=log_type,
        dest="log",
        help="delete from log type %(metavar)s",
        metavar="LOG",
    )
    log_mutex.add_argument(
        "--all-logs",
        action="store_const",
        const=list(LOG_MAP.keys()),
        dest="log",
        help="delete from all log types",
    )

    const_mutex = parser.add_mutually_exclusive_group(required=True)
    ct_arg = const_mutex.add_argument(
        "--change-type",
        action="append",
        help="delete change type %(metavar)s",
        metavar="TYPE",
    )
    const_mutex.add_argument(
        "--obsolete",
        action="store_true",
        dest="delete_all",
        help="delete all obsolete change types",
    )
    Cerebrum.logutils.options.install_subparser(parser)
    argutils.add_commit_args(parser)

    args = parser.parse_args(argv)
    default_preset = "tee" if args.commit else "console"
    Cerebrum.logutils.autoconf(default_preset, args)

    db = Factory.get("Database")()
    # Force constants to use *our* db-transaction
    Constants._CerebrumCode.sql = property(lambda *a: db)
    clconst = Factory.get("CLConstants")(db)
    obsolete = {six.text_type(c): c for c in get_superfluous_codes(clconst)}

    def _get_type(value):
        if value in obsolete:
            return obsolete[value]
        return clconst.get_constant(Constants._ChangeTypeCode, value)

    logs = sorted(args.log, key=LOG_ORDER_KEY)
    logger.info("change-logs: %s", logs)

    if args.delete_all:
        change_types = sorted(obsolete.values(), key=six.text_type)
    else:
        with argutils.ParserContext(parser, ct_arg):
            change_types = sorted(
                [_get_type(v) for v in args.change_type],
                key=six.text_type,
            )

    logger.info("change-types: %s", [six.text_type(c) for c in change_types])

    # Ready to delete
    with db_context(db, dryrun=(not args.commit)):
        for log in logs:
            delete_entries = LOG_MAP[log]
            for change_type in change_types:
                delete_entries(db, change_type)


if __name__ == "__main__":
    main()
