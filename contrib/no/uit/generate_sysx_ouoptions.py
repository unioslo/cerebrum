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

#
# This script reads data exported from our HR system PAGA.
# It is a simple CSV file.
#

from __future__ import unicode_literals

import argparse
import csv
import datetime
import io
import os

import cereconf
import Cerebrum.logutils

from Cerebrum.Utils import Factory

# Define defaults
CHARSEP = ';'

# some common vars
db = Factory.get('Database')()
logger = Factory.get_logger("cronjob")

# define field positions in PAGA csv-data
# First line in PAGA csv file contains field names. Use them.
# STEDKODE = 4
# FAKULTET = 1
# INSTITUTT = 3
# GRUPPE = 6

STEDKODE = 0
KORTNAVN = 3
LANGNAVN = 4

# Default file locations
CB_SOURCEDATA_PATH = cereconf.CB_SOURCEDATA_PATH
DUMPDIR = cereconf.DUMPDIR

default_input_file = os.path.join(CB_SOURCEDATA_PATH,
                                  'steder',
                                  'stedtre-gjeldende.csv')

default_output_file = os.path.join(
    DUMPDIR,
    'ouoptions_{}.xml'.format(datetime.date.today().strftime('%Y%m%d')))


def convert(data, encoding='utf-8'):
    """Convert internal data to a given encoding."""
    if isinstance(data, dict):
        return {convert(key, encoding): convert(value, encoding)
                for key, value in data.iteritems()}
    elif isinstance(data, list):
        return [convert(element, encoding) for element in data]
    elif isinstance(data, bytes):
        return data.decode(encoding)
    else:
        return data


def parse_stedtre_csv(stedtrefile):
    sted = {}

    logger.info("Loading stedtre file...")
    with open(stedtrefile, 'r') as fp:
        reader = csv.reader(fp, delimiter=str(CHARSEP))
        for detail in reader:
            detail = convert(detail, encoding='iso-8859-1')
            if detail != '\n' and len(detail) > 0 and detail[0] != '' and \
                    detail[0][0] != "#":
                sted[detail[STEDKODE]] = {'kortnavn': detail[KORTNAVN],
                                          'langnavn': detail[LANGNAVN]}
                # print "processing line:%s" % detail
            else:
                pass
                # print "skipping line:%s" % detail
    return sted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-i', '--in-file',
        dest='source',
        help='Read OUs from source file %(metavar)s',
        metavar='<file>',
    )
    parser.add_argument(
        '-o', '--out-file', '--Out_file',
        dest='output',
        help='Write output a %(metavar)s XML file',
        metavar='<file>',
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('crontab', args)

    logger.info('Start %r', parser.prog)
    logger.debug("args: %r", args)

    if args.source:
        stedtre_file = args.source
    else:
        stedtre_file = default_input_file

    if args.output:
        out_file = args.output
    else:
        out_file = default_output_file

    sted = parse_stedtre_csv(stedtre_file)
    logger.debug("Information collected. Got %d OUs", len(sted))

    with io.open(out_file, 'w', encoding='utf-8') as fp:
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

    logger.info('Output written to %r', out_file)
    logger.info('Done %r', parser.prog)


if __name__ == '__main__':
    main()
