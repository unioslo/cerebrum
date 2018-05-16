#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2002-2018 University of Oslo, Norway
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
""" Server implementation config for bofhd.

History
-------

This class used to be a part of the bofhd server script itself. It was
moved to a separate module after:

    commit ff3e3f1392a951a059020d56044f8017116bb69c
    Merge: c57e8ee 61f02de
    Date:  Fri Mar 18 10:34:58 2016 +0100

"""
from __future__ import print_function
import io


def _format_class(module, name):
    """ Format a line for the config. """
    return u'{0}/{1}'.format(module, name)


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
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    mod, cls = line.split("/", 1)
                except:
                    mod, cls = None, None
                if not mod or not cls:
                    raise Exception("Parse error in '%s' on line %d: %r" %
                                    (filename, lineno, line))
                self._exts.append((mod, cls))

    def extensions(self):
        """ All extensions from config. """
        for mod, cls in self._exts:
            yield mod, cls


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description="Parse config and output classes")
    parser.add_argument(
        'config',
        metavar='FILE',
        help='Bofhd configuration file')

    args = parser.parse_args()

    config = BofhdConfig(filename=args.config)
    print('Command classes:')
    for mod, name in config.extensions():
        print('-', _format_class(mod, name))
