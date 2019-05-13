#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2018-2019 University of Tromso, Norway
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
"""
from __future__ import print_function

import argparse
import io
import logging
import os
import sys

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.utils.argutils import ParserContext

logger = logging.getLogger(__name__)


default_input_1 = os.path.join(sys.prefix, 'var/dumps/paga/uit_paga_last.csv')
default_input_2 = os.path.join(
    '/home/cerebrum/cerebrum/contrib/no/uit/'
    'uit_addons/scripts/adm2020/uit_paga_adminpeople_final.csv')
default_output = os.path.join(sys.prefix, 'var/dumps/paga/uit_paga_last.csv')


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Concatenate files",
    )
    i1_arg = parser.add_argument(  # noqa: F841
        '--input1',
        dest='input_1',
        default=default_input_1,
        help='First input to write (ignored, default: %(default)s)',
    )
    i2_arg = parser.add_argument(
        '--input2',
        dest='input_2',
        default=default_input_2,
        help='Second input to write (deprecated, default: %(default)s)',
    )
    input_arg = parser.add_argument(
        '--input',
        action='append',
        dest='inputs',
        help='Additional file to write to output',
        metavar='infile',
    )
    parser.add_argument(
        '--output',
        dest='output',
        default=default_output,
        help='Write input files to %(metavar)s (default: %(default)s)',
        metavar='outfile'
    )
    parser.add_argument(
        '--output-mode',
        dest='mode',
        choices=['w', 'a'],
        default='a',
        help='Open output file with mode %(choices)s (default: %(default)s)',
        metavar='mode',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('crontab', args)

    logger.info('Start %r', parser.prog)
    logger.debug("args: %r", args)

    inputs = []

    def add_file(filename):
        if os.path.isfile(filename):
            inputs.append(filename)
        else:
            raise ValueError('no file %r' % (filename, ))

    # if args.input_1:
    #     with ParserContext(parser, i1_arg):
    #         add_file(args.input_1)
    if args.input_2:
        with ParserContext(parser, i2_arg):
            add_file(args.input_2)

    with ParserContext(parser, input_arg):
        for filename in (args.inputs or ()):
            add_file(filename)

    logger.debug("Input files: %r", inputs)

    # TODO: We should use io.open, io.String to ensure all files are in the
    #       same encoding
    file_buffer = io.BytesIO()
    for filename in inputs:
        with open(filename, 'r') as fin:
            file_buffer.write(fin.read())
            logger.debug('Read %r', fin.name)

    def write(fout):
        fout.write(file_buffer.getvalue())
        logger.info('Files written to %r', fout.name)

    if args.output == '-':
        write(sys.stdout)
    else:
        with open(args.output, args.mode) as fout:
            write(fout)

    logger.info('Done %r', parser.prog)


if __name__ == '__main__':
    main()
