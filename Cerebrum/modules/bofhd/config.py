#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2024 University of Oslo, Norway
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
Server implementation config for bofhd.

History
-------

This class used to be a part of the bofhd server script itself. It was
moved to a separate module after:

    commit ff3e3f1392a951a059020d56044f8017116bb69c
    Merge: c57e8ee 61f02de
    Date:  Fri Mar 18 10:34:58 2016 +0100

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io

import six

import Cerebrum.utils.module


def _parse_extension(value):
    """ parse a single line of bofhd config. """
    mod, _, cls = Cerebrum.utils.module.parse(value)
    if not cls:
        raise ValueError("missing class")
    if "." in cls:
        # bofhd has no support for fetching object attribtues (for now)
        raise ValueError("invalid class: " + repr(cls))
    return (mod, cls)


class BofhdConfig(object):

    """ Container for parsing and keeping a bofhd config. """

    def __init__(self, filename=None):
        """ Initialize new config. """
        self._exts = list()  # NOTE: Must keep order!
        if filename:
            self.load_from_file(filename)

    def load_from_file(self, filename):
        """ Load config file. """
        with io.open(filename, encoding='utf-8') as f:
            for lineno, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    ext = _parse_extension(line)
                except ValueError as e:
                    raise ValueError(
                        "Error in '%s', line %d: %s (%s)" %
                        (filename, lineno, six.text_type(e), repr(line)))
                self._exts.append(ext)

    def extensions(self):
        """ All extensions from config. """
        for mod, cls in self._exts:
            yield mod, cls


def _main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        description="Parse config and output classes",
    )
    parser.add_argument(
        'config',
        metavar='FILE',
        help='Bofhd configuration file',
    )

    args = parser.parse_args()

    config = BofhdConfig(filename=args.config)
    print('Command classes:')
    for mod, name in config.extensions():
        print("- {0}/{1}".format(mod, name))


if __name__ == '__main__':
    _main()
