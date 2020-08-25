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
"""
Generate HTML or CSV report of filegroups containing subgroups
without filegroup-spread
"""

import argparse
import logging
import os
from time import time as now

from jinja2 import Environment, FileSystemLoader
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.csvutils as _csvutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)


def find_subgroups_without_mail_spread(db, filter_expired_groups=False):
    """Extract filegroups containing subgroups without fg-spread.

    :type db: Cerebrum.CLDatabase.CLDatabase
    :param db: Database to search for groups

    :type filter_expired_groups: bool
    :param filter_expired_groups: Filter out groups that are expired

    :rtype: generator
    :return:
        Generator yielding dicts with filegroup, subgroup and
        number of members in subgroup
    """
    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)

    result = db.query(
        """
        SELECT group_id, member_id
        FROM [:table schema=cerebrum name=group_member] filegroup
        WHERE
            filegroup.member_type= :group_type
            AND
            filegroup.group_id IN
                (SELECT entity_spread.entity_id
                FROM [:table schema=cerebrum name=entity_spread] entity_spread
                WHERE
                    entity_spread.spread= :ifi_fg_spread OR
                    entity_spread.spread= :uio_fg_spread OR
                    entity_spread.spread= :hpc_fg_spread)
            AND
            NOT filegroup.member_id IN
                (SELECT entity_spread.entity_id
                FROM [:table schema=cerebrum name=entity_spread] entity_spread
                WHERE
                    entity_spread.spread= :ifi_fg_spread OR
                    entity_spread.spread= :uio_fg_spread OR
                    entity_spread.spread= :hpc_fg_spread)
        """,
        {
            'ifi_fg_spread': co.spread_ifi_nis_fg,
            'uio_fg_spread': co.spread_uio_nis_fg,
            'hpc_fg_spread': co.spread_hpc_nis_fg,
            'group_type': co.entity_group,
        })

    for row in result:
        filegroup = gr.search(group_id=row['group_id'],
                              filter_expired=filter_expired_groups)
        subgroup = gr.search(group_id=row['member_id'],
                             filter_expired=filter_expired_groups)
        members_in_sub = len(gr.search_members(
                              group_id=row['member_id'],
                              member_filter_expired=filter_expired_groups))

        # When filtering expired groups, gr.search returns empty list
        if len(filegroup) == 0 or len(subgroup) == 0:
            continue

        groups = {
            'filegroup': text_type(filegroup[0][1]),
            'subgroup': text_type(subgroup[0][1]),
            'members_in_sub': text_type(members_in_sub),
        }
        yield groups


def generate_csv_report(file, codec, groups, num_fgroups):
    output = codec.streamwriter(file)
    output.write('Number of filegroups: {}\n'.format(num_fgroups))
    output.write('Filegroups,')
    output.write('Subgroups,')
    output.write('Members in subgroup\n')

    fields = ['filegroup', 'subgroup', 'members_in_sub']
    writer = _csvutils.UnicodeDictWriter(output, fields)
    writer.writerows(groups)


def generate_html_report(file, codec, groups, num_fgroups):
    output = codec.streamwriter(file)
    env = Environment(
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                             'templates')))
    template = env.get_template('simple_list_overview.html')
    title = 'Filegroups containing subgroups without fg-spread'

    output.write(
        template.render(
            encoding=codec.name,
            headers=(
                ('filegroup', 'Filegroup'),
                ('subgroup', 'Subgroups without fg-spread'),
                ('members_in_sub', 'Members in subgroup')),
            title=title,
            prelist='<h3>{}</h3>'
                    '<p>Number of filegroups: {}</p>'.format(title, num_fgroups),
            items=groups,
            ))
    output.write('\n')


DEFAULT_ENCODING = 'utf-8'
DEFAULT_FORMAT = 'html'
FORMATS = {'html', 'csv'}


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-f', '--file',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='output file for the report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help='output file encoding (default: %(default)s)')
    parser.add_argument(
        '--format',
        choices=FORMATS,
        default=DEFAULT_FORMAT,
        help='format of the report (default: %(default)s)')
    parser.add_argument(
        '--filter-expired',
        action='store_true',
        dest='filter',
        help='do not include expired groups in report')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Reporting filegroups containing subgroups without fg-spread')
    logger.debug('args: %r', args)

    start = now()
    db = Factory.get('Database')()
    groups = list(find_subgroups_without_mail_spread(db, args.filter))
    num_fgroups = len(set(g['filegroup'] for g in groups))

    with args.file as file:
        if args.format == 'html':
            generate_html_report(file, args.codec, sorted(groups), num_fgroups)
            logger.info('HTML report written to %s', file.name)
        if args.format == 'csv':
            generate_csv_report(file, args.codec, sorted(groups), num_fgroups)
            logger.info('CSV report written to %s', file.name)

    logger.info('Report generated in %.2fs', now() - start)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
