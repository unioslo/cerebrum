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
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.utils import email


def get_title():
    """Produce timestamped title for email"""
    return 'Survey of moderatorless manual groups ({t})'.format(
        t=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


def get_abandoned_manual_groups():
    """Extract all manual groupsd without an admin"""
    database = Factory.get('Database')()
    group = Factory.get('Group')(database)
    const = Factory.get('Constants')(database)
    adminless = sorted(group.get_adminless_groups())
    manual_abandonees = {
        const.GroupType(g_type): [] for g_type in cereconf.MANUAL_GROUP_TYPES}
    for adminless_group in adminless:
        group.find(adminless_group[0])
        g_type = const.human2constant(group.group_type)
        if g_type in manual_abandonees:
            manual_abandonees[g_type].append(group.entity_id)
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
        txt += '\n' + 80*'-'
        line = '\n'
        for i, abandoned in enumerate(abandonees):
            line += '{:>10}'.format(abandoned)
            if i > 1 and not (i + 1) % 8:
                txt += line
                line = '\n'
        if len(abandonees) % 8:
            txt += line
        txt += '\n\n'
    return txt


def main():
    """Find moderatorless groups, make a nice table and send it to drift"""
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse
    logger = Factory.get_logger(__name__)
    parser = argparse.ArgumentParser(description=__doc__)
    logger.info('START %s', parser.prog)
    logger.info('Extracting adminless groups')
    abandoned_manual_groups = get_abandoned_manual_groups()
    logger.info('Creating table')
    table = make_table(abandoned_manual_groups)
    recipients = 'cerebrum-uio-logs@usit.uio.no'
    logger.info('Sending email to %s', recipients)
    email.sendmail(recipients, 'noreply@usit.uio.no', get_title(), table)
    logger.info('DONE %s', parser.prog)


if __name__ == '__main__':
    main()
