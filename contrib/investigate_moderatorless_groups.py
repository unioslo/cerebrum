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
This script finds all manualgroups without a moderator and sends a report
to drift.
"""

from __future__ import unicode_literals
import datetime
import six
import logging
import cereconf
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.utils import email
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def get_title():
    """Produce timestamped title for email"""
    return 'Survey of moderatorless manual groups ({t})'.format(
        t=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


def get_abandoned_manual_groups():
    """Extract all manual groups without an admin"""
    database = Factory.get('Database')()
    group = Factory.get('Group')(database)
    const = Factory.get('Constants')(database)
    adminless = sorted(group.get_adminless_groups())
    manual_abandonees = {
        const.GroupType(g_type): [] for g_type in cereconf.MANUAL_GROUP_TYPES}
    today = datetime.datetime.now()
    for adminless_group in adminless:
        group.find(adminless_group[0])
        g_type = const.GroupType(group.group_type)
        if g_type in manual_abandonees:
            expire_date = group.expire_date
            if expire_date and expire_date > today:
                manual_abandonees[g_type].append({'id': group.entity_id,
                                                  'name': group.group_name,
                                                  'desc': group.description})
        group.clear()
    return {k: v for k, v in manual_abandonees.items() if v}


def make_table(manual_abandonees):
    """Create a human readable table of the orphant groups found

    :type abandonees: dict:
    :arg abandonees: all group ids belonging to moderatorless manual groups,
                     sorted by group_type
    :returns: Table with upt o 4 sections and 8 columns of group ids
    """
    txt = 'These manual groups, sorted by type and id, lacks an admin:\n\n'
    for group_type, abandonees in manual_abandonees.items():
        txt += six.text_type(group_type) + ': {}'.format(len(abandonees))
        txt += '\n' + 80*'-' + '\n'
        txt += '\n'.join(
            '{id}, {name}, {desc}'.format(**a) for a in abandonees)
        txt += '\n\n'
    return txt


def main(inargs=None):
    """Find moderatorless groups, make a nice table and send it to drift"""
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-r', '--recipient',
        dest='recipient',
        default=None,
        help='Recipient of the report'
    )
    logutils.options.install_subparser(parser)

    argutils.add_commit_args(parser, default=False)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    logger.info('START %s', parser.prog)
    logger.info('Extracting adminless groups')
    abandoned_manual_groups = get_abandoned_manual_groups()
    logger.info('Creating table')
    table = make_table(abandoned_manual_groups)
    args = parser.parse_args(inargs)
    if args.recipient:
        logger.info('Sending email to %s', args.recipient)
        email.sendmail(
            args.recipient, 'noreply@usit.uio.no', get_title(), table)
    else:
        logger.info('No email provided')
    logger.info('DONE %s', parser.prog)


if __name__ == '__main__':
    main()
