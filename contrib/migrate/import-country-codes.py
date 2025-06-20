#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2025 University of Oslo, Norway
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
Script for importing country codes from an import file.

File format
-----------
The country code file format should contain one country per line, with four
tab-separated fields:
::

    <code><tab><unused><tab><country><tab><phone-prefix>

`<code>`
    A lowercase ISO3166-1 alpha-2 (two-letter) country code

`<unused>`
    Not used, can be an an empty or non-emptry string.

    The reason for this field is lost to the ages, but the original import
    files probably included this field for some reason.

`<country>`
    The ISO3166 country name (English shortname in title case) for the given
    country code

`<phone-prefix>`
    An optional ITU-T E.123 country code (international calling code prefix)
    for the country code.

Example:
::

    no<tab><tab>Norway<tab>+47
    se<tab><tab>Sweden<tab>+46
    sj<tab><tab>Svalbard and Jan Mayen<tab>


Caveats
--------
Country codes imported through this script aren't available as actual constant
objects in code - only in the database.  This works for the most part, but
*can* cause problems in some use cases.  Probably better to define actual
constants...

The only real use case for country codes is storing addresses for multiple
countries.  Cerebrum is not really an address database - only import country
codes if you *really* need to support foreign addresses in Cerebrum!  Note that
some code may be hard-coded to ignore the country field in addresses and/or
hard-code some country string when formatting addresses.

This script can really only be used to import *new* country codes. Any existing
country codes must be removed from the file before import.  This should
probably be fixed (i.e. we should be able to ignore exising country codes, and
update country code fields).

History
--------
The basic code for this script was moved from `makedb.py` to reduce clutter and
complexity, and add more normalization and fail-safes to the country code
import.
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

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Constants
from Cerebrum.database.ctx import db_context
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.textnorm import normalize_text

logger = logging.getLogger(__name__)


def read_country_file(filename):
    """
    Read country code tuples from *filename*.

    :param str filename:
        Path to a file with country codes.

        One code per line - four tab-separated fields.

    :returns generator:
        yields tuples with country code, country name, and phone prefix
    """
    logger.info("reading country codes from %s", repr(filename))
    found = 0
    with io.open(filename, mode="r", encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, 1):
            line = normalize_text(raw_line.strip(" \r\n"))
            if not line:
                continue
            if line.startswith("#"):
                continue
            fields = [field.strip() for field in line.split("\t")]
            if len(fields) != 4:
                raise ValueError(
                    "invalid entry on line %d: %s (got %d fields, expected %d)"
                    % (lineno, repr(raw_line), len(fields), 4)
                )
            code, _, name, phone_prefix = fields
            if not len(code) == 2:
                raise ValueError(
                    "invalid entry on line %d: %s (invalid country code)"
                    % (lineno, repr(raw_line))
                )
            if not name:
                raise ValueError(
                    "invalid entry on line %d: %s (no country name)"
                    % (lineno, repr(raw_line))
                )
            if (phone_prefix
                    and (not phone_prefix.startswith("+")
                         or not phone_prefix[1:].isdigit())):
                raise ValueError(
                    "invalid entry on line %d: %s (invalid calling code)"
                    % (lineno, repr(raw_line))
                )

            found += 1
            yield (code.lower(), name, (phone_prefix or None))

    logger.info("read %d country codes from %s", found, repr(filename))


def insert_codes(const, iterable):
    """
    Insert country codes.

    :type const: Cerebrum.Constants.Constants
    :param iterable:
        An iterable of (code, name, phone prefix) tuples.
    """
    for code, name, phone_prefix in iterable:
        code_obj = const.Country(code, name, phone_prefix, description=name)
        code_obj.insert()
        # this should probably be logged by code_obj.insert()
        logger.info("inserted country code: %s, name: %s, phone prefix: %s",
                    repr(code), repr(name), repr(phone_prefix))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Import country codes",
    )
    parser.add_argument(
        "file",
        help="A country code file to import",
    )
    Cerebrum.logutils.options.install_subparser(parser)
    add_commit_args(parser)

    args = parser.parse_args(argv)
    default_preset = "tee" if args.commit else "console"
    Cerebrum.logutils.autoconf(default_preset, args)

    logger.info("Start %s", parser.prog)

    db = Factory.get("Database")()
    # Monkeypatch constants to use our current db-transaction
    Constants._CerebrumCode.sql = property(lambda *args: db)
    co = Factory.get("Constants")(db)

    countries = list(read_country_file(args.file))
    with db_context(db, dryrun=(not args.commit)):
        insert_codes(co, countries)

    logger.info("Done %s", parser.prog)


if __name__ == "__main__":
    main()
