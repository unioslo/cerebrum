#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2023 University of Oslo, Norway
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
import argparse

import Cerebrum.utils.csvutils as csvutils
import Cerebrum.logutils

from Cerebrum.Utils import Factory

def cachedata(db):
    ac = Factory.get("Account")(db)
    co = Factory.get("Constants")(db)
    ou = Factory.get("OU")(db)

    cache = dict()
    cache["accounts"] = list(account["owner_id"] for account in ac.list())
    cache["status"] = dict(
        (int(r), str(r)) for r in co.fetch_constants(co.PersonAffStatus)
    )
    cache["ou"] = dict(
        (
            sko["ou_id"], "{:02d}{:02d}{:02d}".format(sko["fakultet"], sko["institutt"], sko["avdeling"])
        )
        for sko in ou.get_stedkoder()
    )
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        type=argparse.FileType(mode="w"),
        help="CSV file where output is written.",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf("tee", args)
    affiliations = get_affiliations()
    create_csv(args.output, affiliations)


if __name__ == "__main__":
    main()
