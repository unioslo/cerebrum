#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 University of Oslo, Norway
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
Validate studconfig.xml
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import io
import logging
import os
import sys

import lxml
import lxml.etree

import Cerebrum.logutils
import Cerebrum.logutils.options

logger = logging.getLogger(__name__)


DTD_FILE = "design/studconfig.dtd"
DTD_PATHS = (
    # devutils/envtoolkit envvar
    os.environ.get("CEREBRUM_PATH"),

    # The studconfig.dtd file isn't actually installed, but this is where we'd
    # expect to find it.
    os.path.join(sys.prefix, "share/cerebrum"),
)


XML_FILE = "studconfig.xml"
XML_PATHS = (
    # devutils/envtoolkit envvar
    os.environ.get("CEREBRUM_CONFIG_ETC"),

    # Expected install path
    os.path.join(sys.prefix, "etc/cerebrum"),
)


def find_file(rel, bases):
    """ Find a relative file path in a list of base directories. """
    for base in bases:
        if base and os.path.isdir(base):
            filename = os.path.join(base, rel)
            if os.path.isfile(filename):
                return filename
    return None


def read_dtd(filename):
    with io.open(filename, mode="rb") as bstream:
        return lxml.etree.DTD(bstream)


def read_xml(filename):
    with io.open(filename, mode="rb") as bstream:
        xml_bytes = bstream.read()
    return lxml.etree.XML(xml_bytes)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate studconfig.xml",
        epilog="""
          By default, this script will try to find and validate a
          studconfig.xml against its studconfig.dtd, but it can be used to
          validate any XML file against any standalone DTD file.
        """,
    )

    dtd_default = find_file(DTD_FILE, DTD_PATHS)
    dtd_required = dtd_default is None
    dtd_help = " (required)" if dtd_required else " (default: %(default)s)"
    parser.add_argument(
        "-d", "--dtd",
        default=dtd_default,
        required=dtd_required,
        help="Read definiton from %(metavar)s" + dtd_help,
        metavar="DTD",
    )

    xml_default = find_file(XML_FILE, XML_PATHS)
    xml_required = xml_default is None
    xml_help = " (required)" if xml_required else " (default: %(default)s)"
    parser.add_argument(
        "-x", "--xml",
        default=xml_default,
        required=xml_required,
        help="Read document to validate from %(metavar)s" + xml_help,
        metavar="XML",
    )
    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: "INFO",
    })

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("console", args)

    dtd = read_dtd(args.dtd)
    xml = read_xml(args.xml)

    is_valid = dtd.validate(xml)
    print("Valid:", repr(is_valid))

    if is_valid:
        return
    raise SystemExit(dtd.error_log)


if __name__ == "__main__":
    main()
