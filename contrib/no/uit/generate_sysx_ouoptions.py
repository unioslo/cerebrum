#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2002-2019 University of Oslo, Norway
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
Generate OU data for System X.

This script reads data exported from our HR system PAGA.  It is a simple
CSV file.
"""
from __future__ import unicode_literals

import argparse
import csv
import datetime
import logging
import io
import os
import sys

import Cerebrum.logutils
import Cerebrum.logutils.options

# Define defaults
INPUT_CHARSEP = ';'
INPUT_ENCODING = 'utf-8'

# define field positions in PAGA csv-data
# First line in PAGA csv file contains field names. Use them.
# STEDKODE = 4
# FAKULTET = 1
# INSTITUTT = 3
# GRUPPE = 6

STEDKODE = 0
KORTNAVN = 3
LANGNAVN = 4

logger = logging.getLogger(__name__)


def parse_stedtre_csv(filename):
    sted = {}
    logger.info('Loading stedtre file=%r', filename)
    with open(filename, 'r') as fp:
        reader = csv.reader(fp, delimiter=INPUT_CHARSEP.encode(INPUT_ENCODING))
        for detail in reader:
            detail = [f.decode(INPUT_ENCODING) for f in detail]
            if not detail or not detail[0].strip():
                continue
            if detail[0].strip().startswith('#'):
                continue
            if len(detail) < LANGNAVN:
                logger.error("Invalid data on line %d: %r",
                             reader.line_num, detail)
                continue
            try:
                sted[detail[STEDKODE]] = {
                    'kortnavn': detail[KORTNAVN],
                    'langnavn': detail[LANGNAVN],
                }
            except Exception:
                logger.error("Invalid data on line %d: %r",
                             reader.line_num, detail)
                raise
    return sted


default_input_file = os.path.join(
    sys.prefix, 'var/cache/steder/stedtre-gjeldende.csv')

default_output_file = os.path.join(
    sys.prefix, 'var/cache',
    'ouoptions_{}.xml'.format(datetime.date.today().strftime('%Y%m%d')))


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-i', '--in-file',
        dest='source',
        default=default_input_file,
        help='Read OUs from source file %(metavar)s',
        metavar='<file>',
    )
    parser.add_argument(
        '-o', '--out-file',
        dest='output',
        default=default_output_file,
        help='Write output a %(metavar)s XML file',
        metavar='<file>',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %r', parser.prog)
    logger.debug("args: %r", args)

    sted = parse_stedtre_csv(args.source)
    logger.debug("Information collected. Got %d OUs", len(sted))

    # TODO: Use csv module?
    with io.open(args.output, 'w', encoding='utf-8') as fp:
        for stedkode in sorted(sted.keys()):
            if stedkode == '000000':
                fp.write("%s : %s : %s\n" % (
                    stedkode,
                    sted[stedkode]['langnavn'],
                    sted[stedkode]['langnavn']))
            elif stedkode[2:4] == '00':
                current_faculty = sted[stedkode]['kortnavn']
                fp.write("%s : %s : %s\n" % (
                    stedkode, current_faculty, sted[stedkode]['langnavn']))
            else:
                fp.write("%s : %s : %s\n" % (
                    stedkode,
                    current_faculty,
                    sted[stedkode]['langnavn']))

    logger.info('Output written to %r', args.output)
    logger.info('Done %r', parser.prog)


if __name__ == '__main__':
    main()
