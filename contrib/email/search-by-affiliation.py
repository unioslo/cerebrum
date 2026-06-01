#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011-2026 University of Oslo, Norway
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
Look up email addresses from affiliations.

This script is a simple replacement for the old
``Cerebrum.modules.no.uio.PostmasterCommands``.

It provides a simple search for looking up email addresses.

Examples
--------
Email addrs for everyone affiliated with location code 373022, written to
/tmp/email.txt:
::

    <prog> --location 373022 --output /tmp/email.txt


All employees and active studens at faculty 15????, written to stdout.
::

    <prog> --affiliation ANSATT --affiliation STUDENT/aktiv --location 15


Future improvements
-------------------
Search by subtree
    Let the search follow the org hierarchy, rather than doing a partal
    location code match.

Per-affiliation source + ou
    Add support for looking up affiliations by each org unit
    (e.g.  DFO:ANSATT@373022 + FS:STUDENT/aktiv@150500).
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging
import textwrap

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import file_stream

logger = logging.getLogger(__name__)


def get_ou_ids(db, location_filter):
    """ Look up ou ids from a location code (stedkode) filter. """
    if len(location_filter) not in (2, 4, 6):
        raise ValueError("Location filter must be 2, 4 or 6 digits")
    ou = Factory.get("OU")(db)
    kwargs = {
        k: (None if v is None else int(v))
        for k, v in (
            ('fakultet', location_filter[:2] or None),
            ('institutt', location_filter[2:4] or None),
            ('avdeling', location_filter[4:6] or None),
        )
    }
    ou_ids = set(row['ou_id'] for row in ou.get_stedkoder(**kwargs))
    logger.debug("location %s -> %s", repr(location_filter), repr(ou_ids))
    return ou_ids


def get_addresses(db, affiliation, status, source_system, ou_id):
    """ Look up email addresses from affiliations. """
    pe = Factory.get("Person")(db)
    co = pe.const

    logger.debug("Caching email addresses...")
    addr_cache = dict(pe.list_primary_email_address(co.entity_person))
    logger.debug("Found %d people with email addr", len(addr_cache))

    logger.debug("Searching for candidates...")
    candidates = set()
    if affiliation:
        candidates.update(
            row['person_id']
            for row in pe.list_affiliations(
                affiliation=affiliation,
                source_system=source_system,
                ou_id=ou_id,
            )
        )
    if status:
        candidates.update(
            row['person_id']
            for row in pe.list_affiliations(
                status=status,
                source_system=source_system,
                ou_id=ou_id,
            )
        )
    logger.debug("Found %d matching people", len(candidates))

    addrs = set(
        addr_cache[person_id]
        for person_id in candidates
        if person_id in addr_cache
    )
    logger.info("Found %d matching addresses", len(addrs))
    missing = candidates - set(addr_cache)
    if missing:
        logger.warning("Missing address for %d matching persons", len(missing))
    return addrs


def write_output(filename, addresses):
    with file_stream.get_output_context(filename, encoding="utf-8") as f:
        for addr in sorted(addresses):
            print(addr, file=f)
        logger.info("Wrote %d addrs to %s", len(addresses), repr(f))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Look up email addresses from affiliations",
        epilog=textwrap.dedent(
            """
            AND-filters
                Each filter argument name adds an *AND* filter.  E.g.
                --affiliation TILKNYTTET --sys GREG will only include people
                with the given affiliation from the given source system.

            OR-filters
                All filter arguments can be repeated, and each repeated value
                adds an *OR* filter.  E.g. --affilition ANSATT/tekadm
                --affiliation STUDENT will include people with either of the
                given affiliations.

            SKO
                Filters by affiliation org unit, and uses location codes
                (stedkode).

                Supports partial location codes.  E.g. --location 3730, will
                include all org units matching the location code pattern
                3730??, and is equivalent to adding each of the org unit
                location codes as a separate argument.

                Partial location codes *must* be an even number.

            FILE
                All email addresses are written to this file. A literal
                `{stdout_value}` will write addresses to stdout.  This is the
                default.
            """
        ).strip().format(stdout_value=file_stream.DEFAULT_STDOUT_NAME),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    arg_aff = parser.add_argument(
        "-a", "--affiliation",
        action="append",
        dest="affiliations",
        help="Filter by affiliation and/or status",
        metavar="AFF[/status]",
    )
    arg_src = parser.add_argument(
        "-s", "--source",
        action="append",
        dest="source_systems",
        help="Filter by source systems",
        metavar="SYS",
    )
    arg_sko = parser.add_argument(
        "-l", "--location",
        action="append",
        dest="locations",
        help="Filter by org unit (location code)",
        metavar="SKO",
    )
    parser.add_argument(
        "-o", "--output",
        dest="output",
        default=file_stream.DEFAULT_STDOUT_NAME,
        help="Write addresses to %(metavar)s (default: stdout)",
        metavar="FILE",
    )

    Cerebrum.logutils.options.install_subparser(parser, default_level="INFO")

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf("console", args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    db = Factory.get("Database")()
    co = Factory.get("Constants")(db)

    # Validate/look up args

    affiliations = []
    statuses = []
    with argutils.ParserContext(parser, arg_aff):
        for value in (args.affiliations or ()):
            aff, st = co.get_affiliation(value)
            if st is None:
                affiliations.append(aff)
            else:
                statuses.append(st)
    logger.info("affiliation: %s",
                ", ".join(sorted(six.text_type(a) for a in affiliations +
                                 statuses))
                if (affiliations or statuses) else "*")

    sources = []
    with argutils.ParserContext(parser, arg_src):
        for value in (args.source_systems or ()):
            src = co.get_constant(co.AuthoritativeSystem, value)
            sources.append(src)
    logger.info("source_system: %s",
                ", ".join(sorted(six.text_type(s) for s in sources))
                if sources else "*")

    ou_ids = set()
    with argutils.ParserContext(parser, arg_sko):
        for value in (args.locations or ()):
            ou_ids.update(get_ou_ids(db, value))
    logger.info("ou-id: %s",
                ", ".join(six.text_type(ou_id) for ou_id in sorted(ou_ids))
                if ou_ids else "*")

    # Find addrs and write output

    addrs = get_addresses(
        db,
        affiliations,
        statuses,
        sources or None,
        ou_ids or None,
    )
    write_output(args.output, addrs)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
