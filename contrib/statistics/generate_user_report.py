#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

"""This script produces a report over people and usernames.

This script produces a (daily?) report over people, their user names and their
activity statuses.

For each person in the database we report the following:

* fnr[1]
* all user names
* activity status[2]

[1] Should the person have multiple different fnrs, the one listed first in
--fnr-systems is used as the selection basis. If none are specified,
cereconf.SYSTEM_LOOKUP_ORDER is respected.

[2] A *person* with at least one valid affiliation is considered active. All
others are inactive.

This job has been requested for ØFK, but it could be used at any institution
using Cerebrum.
"""



import sys
import getopt

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
logger = Factory.get_logger("cronjob")



def generate_person_uname_report(stream, fnr_src_sys=None):
    """Display statistics about people/unames.

    Each person in Cerebrum gets as many entries at (s)he has usernames.

    Each entry is formatted thus:

    fnr:uname:aktiv/inaktiv

    ... where

    fnr		constants.externalid_fodselsnr
    uname	account name owned by that person
    aktiv	aktiv, if the *person* has at least one valid
                affiliation. inaktiv otherwise.
    """

    db = Factory.get("Database")()
    person = Factory.get("Person")(db)
    acc = Factory.get("Account")(db)
    const = Factory.get("Constants")(db)

    #
    # Get the right source system for external ids. If no source system is
    # specified, we'll prioritise the IDs as specified in SYSTEM_LOOKUP_ORDER.
    if fnr_src_sys:
        source_systems = [int(getattr(const, x))
                          for x in fnr_src_sys.split(",")]
    else:
        source_systems = [int(getattr(const, x))
                          for x in cereconf.SYSTEM_LOOKUP_ORDER]

    for p in person.list_persons():
        pid = p["person_id"]

        try:
            person.clear()
            person.find(pid)
        except Errors.NotFoundError:
            logger.warn("list_persons() reported a person, but person.find() "
                        "did not find it")
            continue

        # Select fnr from the list of candidates.
        fnrs = dict([(int(src), eid) for (junk, src, eid) in
                     person.get_external_id(id_type=const.externalid_fodselsnr)])
        fnr = ""
        for system in source_systems:
            if system in fnrs:
                fnr = fnrs[system]
                break

        # at least one active affiliation => 'aktiv'
        status = "inaktiv"
        if person.get_affiliations():
            status = "aktiv"

        # for all (unexpired) accounts owned by the person...
        accounts = acc.search(owner_id = pid)
        for entry in accounts:
            stream.write(":".join((fnr, entry["name"], status)))
            stream.write("\n")
# end generate_person_uname_report



def main(argv=None):
    """Main processing hub for program."""
    if argv is None:
        argv = sys.argv
        
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "f:s:",
                                   ["file=","fnr-systems="])
    except getopt.GetoptError, error:
        usage(message=error.msg)
        return 1

    output_stream = sys.stdout
    fnr_src_sys = None
    for opt, val in opts:
        if opt in ('-f', '--file',):
            output_stream = open(val, "w")
        elif opt in ('-s', '--fnr-systems',):
            fnr_src_sys = val

    generate_person_uname_report(output_stream, fnr_src_sys)

    if output_stream not in (sys.stdout, sys.stderr):
        output_stream.close()

    return 0
# end main



if __name__ == "__main__":
    sys.exit(main())
