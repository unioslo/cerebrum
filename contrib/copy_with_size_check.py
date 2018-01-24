#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2013 University of Oslo, Norway
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

"""USAGE
    ./copy_with_size_check.py [options]

    This script will replace the output file with the input file if the changes
    are within the specified limits. This is done by reading one line at a time
    from input and writing to a temporary output file using SimilarSizeWriter.

    If the changes are too big:
        - the path to the temporary output file is logged/written to console
        - a FileChangeTooBigError exception is thrown

    If the changes are within the limits:
        - the temporary output file replaces the output file

    This script should not be used for binary files.

EXAMPLES
    Replace outFile with inFile if inFile is not 10% bigger/smaller in bytes
        [script] --input inFile --output outFile --limit-percentage 10

    Replace outFile with inFile if inFile is not 50% bigger/smaller in bytes,
    and is not 100 lines longer/shorter
        [script] -i inFile -o outFile -p 50 -l 100

OPTIONS
    -i, --input  <file>   File to read from.
    -o, --output <file>   This file will be overwritten by the input file if
                          the changes aren't too big.
    -p, --limit-percentage <percentage>
                          If the input file size is bigger or smaller by this
                          percentage, output will not be overwritten.
    -l, --limit-lines <lines>
                          If the input file is longer or shorter by this number
                          of lines, output will not be overwritten."""

import os
import sys
import getopt

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.utils.atomicfile import SimilarLineCountWriter
from Cerebrum.utils.atomicfile import FileChangeTooBigError


def write_and_check_size(
        logger, inFilePath, outFilePath,
        limit_percentage=False, limit_lines=False):
    """Reads from the input file, writes to output file using SimilarSizeWriter.
    Changes to output file are done only if within limits.

    @param logger: Logger object inherited from main()
    @type logger: Logger

    @param inFilePath: Input file
    @type inFilePath: String, path to file

    @param outFilePath: Output file
    @type outFilePath: String, path to file

    @param limit_percentage: Percentage change limit
    @type limit_percentage: Float

    @param limit_lines: Line count change limit
    @type limit_lines: Float"""

    try:
        inFile = open(inFilePath, 'r')  # Can we read from input?
        assert(os.access(outFilePath, os.W_OK))  # Is output writable?
    except IOError, err:
        logger.error(err)
        raise err

    logger.info("Reading from: %s (%s bytes)",
                inFilePath, os.path.getsize(inFilePath))
    logger.info("Comparing to: %s (%s bytes)",
                outFilePath, os.path.getsize(outFilePath))

    if limit_percentage:
        ssw = SimilarSizeWriter(outFilePath, mode='w')
        ssw.max_pct_change = limit_percentage
    else:
        ssw = SimilarLineCountWriter(outFilePath, mode='w')
        ssw.max_line_change = limit_lines

    # read from input, write to temporary output file
    for line in inFile:
        ssw.write(line)

    try:
        # close() checks that changes are within limits
        ssw.close()
    except FileChangeTooBigError as err:
        logger.error(
            "Changes are too big, leaving behind temporary file %s",
            ssw._tmpname)
        raise err

    logger.info("Changes are within limits, file replaced")


def usage(exitcode=0):
    """Prints usage information."""

    print __doc__
    sys.exit(exitcode)


def main():
    """Reads options and moves forward."""

    logger = Factory.get_logger('cronjob')

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'o:i:p:l:',
            ['output=', 'input=', 'limit-percentage=', 'limit-lines=']
        )
    except getopt.GetoptError, err:
        logger.error(err)
        usage(1)

    outFilePath = inFilePath = limit_percentage = limit_lines = None

    for opt, val in opts:
        if opt in ('-o', '--output'):
            outFilePath = val
        if opt in ('-i', '--input'):
            inFilePath = val
        if opt in ('-p', '--limit-percentage'):
            limit_percentage = float(val)
        if opt in ('-l', '--limit-lines'):
            limit_lines = float(val)

    if not limit_percentage and not limit_lines:
        logger.error('Missing --limit-percentage or --limit-lines parameter')
        usage(1)

    if not inFilePath or not outFilePath:
        logger.error('Missing --input or --output parameter')
        usage(1)

    write_and_check_size(
        logger, inFilePath, outFilePath, limit_percentage, limit_lines)


# If we run as a program, execute main(), then exit
if __name__ == '__main__':
        sys.exit(main())
