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
This script finds all manual groups without a moderator and sends a report
to drift.
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

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import email as email_utils
from Cerebrum.utils import file_stream

logger = logging.getLogger(__name__)


def format_subject(_when=None):
    """Produce timestamped title for email"""
    when = _when or date_utils.now()
    return "Survey of moderatorless manual groups ({when})".format(
        when=when.strftime('%Y-%m-%d %H:%M:%S'),
    )


def get_abandoned_manual_groups(database):
    """Extract all manual groups without an admin"""
    group = Factory.get('Group')(database)
    const = Factory.get('Constants')(database)

    # We only consider MANUAL_GROUP_TYPES
    by_group_type = {
        const.get_constant(const.GroupType, g_type): []
        for g_type in cereconf.MANUAL_GROUP_TYPES
    }

    group_cache = {
        row['group_id']: {
            'group_type': const.GroupType(row['group_type']),
            'group_name': row['name'],
            'group_desc': row['description'],
        }
        for row in group.search(
            filter_expired=True,
            group_type=list(by_group_type.keys()),
        )
    }
    logger.debug("Cached %d groups", len(group_cache))

    candidates = set(r['group_id'] for r in group.get_adminless_groups())
    logger.debug("Found %d groups without moderators", len(candidates))

    for group_id in sorted(candidates):
        if group_id not in group_cache:
            continue  # expired, wrong type
        group_info = group_cache[group_id]
        group_type = group_info['group_type']
        # if group_type == const.group_type_internal:
        #     # never consider internal groups
        #     continue

        by_group_type[group_type].append({
            'id': group_id,
            'name': group_info['group_name'],
            'desc': group_info['group_desc'],
        })
    return {k: v for k, v in by_group_type.items() if v}


def format_table(groups_by_type):
    """Create a human readable table of the orphant groups found

    :param dict groups_by_type:
        a map if group-type to list of groups to include in the report

    :return str:
        A formatted report table
    """
    txt = "These manual groups, sorted by type and id, lacks an admin:\n\n"
    for group_type in sorted(groups_by_type):
        groups = groups_by_type[group_type]
        txt += six.text_type(group_type) + ": {}".format(len(groups))
        txt += "\n" + 80*"-" + "\n"
        txt += "\n".join(
            "{id}, {name}, {desc}".format(**a) for a in groups
        )
        txt += "\n\n"
    return txt


def send_report(recipient, subject, body):
    """ Send formatted report by email to *recipient*. """
    debug_message = email_utils.sendmail(
        toaddr=recipient,
        fromaddr="noreply@usit.uio.no",
        subject=subject,
        body=body,
    )
    if debug_message:
        logger.info("Email disabled - would send report to %s", recipient)
    else:
        logger.info("Sent report to %s", recipient)


def write_report(filename, subject, body):
    """ Write formatted report to *filename*. """
    with file_stream.get_output_context(filename, encoding="utf-8") as f:
        f.write(subject + "\n")
        f.write("=" * len(subject) + "\n")
        f.write(body + "\n")
    logger.info("Wrote report to %s", filename)


def main(argv=None):
    """Find moderatorless groups, make a nice table and send it to drift"""
    parser = argparse.ArgumentParser(
        description="Find and report groups without moderators",
    )
    parser.add_argument(
        "-f", "--file",
        dest="filename",
        default=None,
        help="Write report to %(metavar)s",
        metavar="FILE",
    )
    parser.add_argument(
        "-r", "--recipient",
        dest="recipient",
        default=None,
        help="Send report to %(metavar)s",
        metavar="ADDR",
    )
    parser.add_argument(
        "--force",
        dest="force",
        action="store_true",
        default=False,
        help="Write or send empty reports",
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(argv)
    with argutils.ParserContext(parser):
        if not any((args.recipient, args.filename)):
            raise ValueError("Filename or recipient is required")

    Cerebrum.logutils.autoconf("cronjob", args)
    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    logger.debug("Finding groups without moderators...")
    database = Factory.get('Database')()
    groups_by_type = get_abandoned_manual_groups(database)
    n_groups = sum(len(v) for v in groups_by_type.values())
    logger.info("Found %d target groups without moderators", n_groups)

    if args.force or n_groups:
        logger.debug("Preparing report...")
        subject = format_subject()
        body = format_table(groups_by_type)

        if args.recipient:
            send_report(args.recipient, subject, body)
        if args.filename:
            write_report(args.filename, subject, body)
    else:
        logger.info("No groups to report")

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
