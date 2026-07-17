#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023-2024 University of Oslo, Norway
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
Create a CSV file that outputs the amount of active accounts
distributed by OU and affiliation status.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import csvutils
from Cerebrum.utils import file_stream


logger = logging.getLogger(__name__)


def cachedata(db):
    ac = Factory.get("Account")(db)
    co = Factory.get("Constants")(db)
    ou = Factory.get("OU")(db)

    cache = dict()
    cache["accounts"] = list(account["owner_id"] for account in ac.list())
    cache["status"] = {
        int(status): str(status)
        for status in co.fetch_constants(co.PersonAffStatus)
    }
    cache["ou"] = {
        sko["ou_id"]: "{:02d}{:02d}{:02d}".format(sko["fakultet"],
                                                  sko["institutt"],
                                                  sko["avdeling"])
        for sko in ou.get_stedkoder()
    }
    return cache


def get_affiliations():
    db = Factory.get("Database")()
    pe = Factory.get("Person")(db)
    affs = list()
    cache = cachedata(db)

    for row in pe.list_affiliations():
        if row["person_id"] in cache["accounts"]:
            ou = cache["ou"][row["ou_id"]]
            status = cache["status"][row["status"]]
            affs.append((ou, status))
    return affs


def create_csv(filename, affiliations):
    output = (
        {
            "OU": unique[0],
            "aff-status": unique[1],
            "antall-personer": affiliations.count(unique),
        }
        for unique in sorted(set(affiliations))
    )
    header = ["OU", "aff-status", "antall-personer"]
    writer = csvutils.UnicodeDictWriter(filename, fieldnames=header)
    writer.writeheader()
    writer.writerows(output)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        metavar='FILE',
        default=file_stream.DEFAULT_STDOUT_NAME,
        help="write output to %(metavar)s (default: stdout)",
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("tee", args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    affiliations = get_affiliations()
    with file_stream.get_output_context(args.output, encoding="utf-8") as f:
        create_csv(f, affiliations)
        logger.info('Report written to %s', f.name)

    logger.info('Done with script %s', parser.prog)


if __name__ == "__main__":
    main()
