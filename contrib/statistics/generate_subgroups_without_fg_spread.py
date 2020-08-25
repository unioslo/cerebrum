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
without filegroup-spread or with different filegroup-spread
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


def find_subgroups_without_fg_spread(db, filter_expired_groups=False):
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

    co = Factory.get('Constants')(db)
    gr = Factory.get('Group')(db)

    fg_spreads = (co.spread_ifi_nis_fg,
                  co.spread_uio_nis_fg,
                  co.spread_hpc_nis_fg)

    filegroups = gr.search(spread=fg_spreads,
                           filter_expired=filter_expired_groups)

    for filegroup in filegroups:
        gr.clear()
        gr.find(filegroup['group_id'])
        filegroup_spreads = set(s['spread'] for s in gr.get_spread())
        # Extracting the specific fg-spreads of this filegroup
        filegroup_fg_spreads = set(fg_spreads).intersection(filegroup_spreads)

        subgroups_all = gr.search_members(
            group_id=filegroup['group_id'],
            member_type=co.entity_group,
            indirect_members=True,
            member_filter_expired=filter_expired_groups,
            include_member_entity_name=True)

        subgroups_without_fg_spread = []
        for sub in subgroups_all:
            gr.clear()
            gr.find(sub['member_id'])
            sub_spreads = set(s['spread'] for s in gr.get_spread())
            # Extracting fg-spreads of this subgroup, if any
            subgroup_fg_spreads = set(fg_spreads).intersection(sub_spreads)
            # If subgroup does not share fg-spread with filegroup
            # we add it to our list
            if not subgroup_fg_spreads.intersection(filegroup_fg_spreads):
                subgroups_without_fg_spread.append(sub)

        for subgroup in subgroups_without_fg_spread:
            num_members_sub = len(gr.search_members(
                group_id=subgroup['member_id'],
                member_type=co.entity_account,
                indirect_members=True,
                member_filter_expired=filter_expired_groups))

            groups = {
                'filegroup': text_type(filegroup['name']),
                'subgroup': text_type(subgroup['member_name']),
                'members_in_sub': num_members_sub,
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
