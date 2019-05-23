#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import getopt
import sys

from Cerebrum.Utils import Factory

progname = __file__.split("/")[-1]
__doc__ = """Usage: %s [options]
    Generate ouoptionsfile for SystemX

    options:
    -o | --out_file   : file to store output
    -s | --stedtre-file  : file to read from
    -h | --help       : show this
    --logger-name     : name of logger to use
    --logger-level    : loglevel to use

    """ % progname

# Define defaults
CHARSEP = ';'
default_stedtre_file = '/cerebrum/var/source/stedtre-gjeldende.csv'
default_out_file = 'ouoptions'

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


def parse_stedtre_csv(stedtrefile):
    import csv
    sted = {}

    logger.info("Loading stedtre file...")
    for detail in csv.reader(open(stedtrefile, 'r'), delimiter=CHARSEP):
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
    out_file = default_out_file
    stedtre_file = default_stedtre_file
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hs:o:',
                                   ['stedtre-file=', 'out-file=', 'help'])
    except getopt.GetoptError, m:
        usage(1, m)

    for opt, val in opts:
        if opt in ('-o', '--out-file'):
            out_file = val
        if opt in ('-s', '--stedtre-file'):
            stedtre_file = val

        if opt in ('-h', '--help'):
            usage()

    sted = parse_stedtre_csv(stedtre_file)
    logger.debug("Information collected. Got %d OUs", len(sted))

    fp = open(out_file, 'w')
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

    fp.close()
    logger.debug("File written.")


def usage(exit_code=0, msg=None):
    if msg:
        print msg
    print __doc__
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
