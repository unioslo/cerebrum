#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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
""" Generate a list of persons with name diff.

This script generates a list of persons with different names in
regards to 2 source systems (f.eks: SAP/FS, ...) given in argument
to the script.

"""
import argparse
import logging
import sys

from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type, get_constant


logger = logging.getLogger(__name__)


def generate_diff(db, src_sys_a, src_sys_b):

    co = Factory.get("Constants")(db)
    pe = Factory.get("Person")(db)

    def _u(text):
        if text is None:
            return text_type('')
        if isinstance(text, bytes):
            return text.decode(db.encoding)
        return text_type(text)

    for row in pe.list_persons():
        # Test if initialisation of person succeeds and person in question
        # exists
        try:
            pe.clear()
            pe.find(row["person_id"])
        except Errors.NotFoundError:
            logger.warn("list_persons() reported a person, but person.find() "
                        "did not find it")
            continue

        # Select fnr objects from the list of candidates.
        # TODO: Should probably look at affs, not fnr?
        person_ids = dict(
            (int(src), _u(eid)) for (junk, src, eid)
            in pe.get_external_id(id_type=co.externalid_fodselsnr))

        # TODO: check if fnr objects have identical numbers as well

        # Check if the person object in question has got both source systems
        if any(src not in person_ids for src in (src_sys_b, src_sys_b)):
            continue

        # Check if there is a name entry for the first source system
        try:
            name_a_first = _u(pe.get_name(src_sys_a, co.name_first))
            name_a_last = _u(pe.get_name(src_sys_a, co.name_last))
        except Errors.NotFoundError:
            continue

        try:
            name_b_first = _u(pe.get_name(src_sys_b, co.name_first))
            name_b_last = _u(pe.get_name(src_sys_b, co.name_last))
        except Errors.NotFoundError:
            continue

        if name_a_first != name_b_first or name_a_last != name_b_last:
            person_id = person_ids[src_sys_a]
            yield (person_id,
                   ' '.join((name_a_first, name_a_last)),
                   ' '.join((name_b_first, name_b_last)))


def format_diff(ident, value_a, value_b):
    return u':'.join((ident, value_a, value_b))


def output_diff(stream, codec, iterator):
    output = codec.streamwriter(stream)
    for diff in iterator:
        output.write(format_diff(*diff))
        output.write("\n")
    output.write("\n")


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")
    diff_arg = parser.add_argument(
        'source_system',
        nargs=2,
        metavar='SYSTEM',
        help='source system to diff')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get("Database")()
    co = Factory.get("Constants")(db)

    systems = [
        get_constant(db, parser, co.AuthoritativeSystem, value, diff_arg)
        for value in args.source_system]
    logger.debug("systems: %r", systems)

    output_diff(args.output, args.codec, generate_diff(db, *systems))

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == "__main__":
    main()
