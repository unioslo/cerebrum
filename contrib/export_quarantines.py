#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2015 University of Oslo, Norway
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
"""Utilities/script to export quarantines to file."""

from __future__ import with_statement


def parse_opts(args=None):
    """Parse arguments to export_quarantines.py.

    :param str args: args to parse.
    :return argparse.Namespace: Parsed args."""
    try:
        import argparse
    except ImportError:
        from Cerebrum.extlib import argparse

    parser = argparse.ArgumentParser(
        description="Export quarantines in JSON-format to file")
    parser.add_argument(
        '--outfile',
        required=True,
        help="Write export to filename")
    parser.add_argument(
        '--quarantines',
        nargs='*',
        required=True,
        help="Quarantines that should be exported (i.e. 'radius vpn')")
    return parser.parse_args(args.split() if args else None)


def parse_quarantine_strings(co, quarantines):
    """Quarantine()-ify strings.

    :param co: Constants-object.
    :param list: List of quarantine codes.
    :return: set(<Cerebrum.Constants._QuarantineCode>)."""
    return set(co.Quarantine(q) for q in quarantines)


def get_quarantines(db, quarantine_types=None):
    """List quarantines.

    :param db: Database-object.
    :param quarantine_types: Quarantine-types to filter by.
    :return list(<dict()>): List of quarantines."""
    from Cerebrum.Entity import EntityQuarantine
    eq = EntityQuarantine(db)
    return [row.dict() for row in
            eq.list_entity_quarantines(quarantine_types=quarantine_types)]


def codes_to_human(db, en, co, quarantines):
    """Convert Cerebrum-codes to more usable information.
    :param db: Database-object.
    :param en: Entity-object.
    :param co: Constants-object.

    :param list(<dict()>) quarantines: List of quarantines.
    :return list(<dict()>) quarantines: List of quarantines.
    """
    for q in quarantines:
        q['quarantine_type'] = str(co.Quarantine(q['quarantine_type']))
        en.clear()
        en.find(q['entity_id'])
        if en.entity_type == co.entity_account:
            q['account_name'] = en.get_subclassed_object().account_name
            del q['entity_id']
    return quarantines


def dump_json(quarantines, out_file):
    """Dump a list of quarantines to JSON-file.

    Objects of type mx.DateTime.DateTimeType are serialized by calling str().

    :param list(<Cerebrum.extlib.db_row.row>) quarantines: List of quarantines.
    :param basestring outfile: File to write."""
    try:
        import json
    except ImportError:
        from Cerebrum.extlib import json

    class Encoder(json.JSONEncoder):
        def default(self, obj):
            from mx.DateTime import DateTimeType

            if isinstance(obj, DateTimeType):
                return str(obj)
            return json.JSONEncoder.default(self, obj)

    with open(out_file, 'w') as f:
        json.dump(quarantines, f, cls=Encoder, indent=4, sort_keys=True)

if __name__ == '__main__':
    """Actual script."""
    import cereconf
    getattr(cereconf, "Linter", None)

    from Cerebrum.Utils import Factory
    from Cerebrum import Errors
    db = Factory.get('Database')(client_encoding='utf-8')
    en = Factory.get('Entity')(db)
    co = Factory.get('Constants')(db)

    opts = parse_opts()
    try:
        dump_json(
            codes_to_human(
                db, en, co,
                get_quarantines(
                    db, parse_quarantine_strings(
                        co, opts.quarantines))),
            opts.outfile)
    except Errors.NotFoundError, e:
        print(str(e) + '\n\nError: No existing quarantine?')
        import sys
        sys.exit(1)
