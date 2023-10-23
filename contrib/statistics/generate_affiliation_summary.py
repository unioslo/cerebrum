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
Generate a simple affiliation report.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import io
import json
import logging
import string
import textwrap

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import aggregate
from Cerebrum.utils import csvutils
from Cerebrum.utils import reprutils

logger = logging.getLogger(__name__)

# Suggestions for improvements:
#
# 1. Allow selecting affiliations to report on.  E.g.:
#
#   - Select affiliation by org unit (preferably with recursion)
#   - Select affiliation by source system(s), type(s), status(es)
#
# 2. Allow counting multiple values, like the legacy report.  E.g. make the
#    --count-by argument repeatable, and output one column for each count.
#    The JSON output values should probably then be objects grouped by
#    unique_key.
#
# 3. Generalize the output formatting:
#
#   - Allow table output for non-legacy report.
#   - Allow CSV/JSON for legacy report.
#   - Allow for more columns/values (see Output counts)


def get_affiliations(db, **select):
    """ Get affiliation dicts.  """
    pe = Factory.get("Person")(db)
    co = pe.const
    aff_map = {int(c): c for c in co.fetch_constants(co.PersonAffiliation)}
    st_map = {int(c): c for c in co.fetch_constants(co.PersonAffStatus)}
    sys_map = {int(c): c for c in co.fetch_constants(co.AuthoritativeSystem)}
    count = 0
    for row in pe.list_affiliations(**select):
        yield {
            'person_id': row['person_id'],
            'affiliation': aff_map[row['affiliation']],
            'status': st_map[row['status']],
            'source_system': sys_map[row['source_system']],
            'ou_id': row['ou_id'],
        }
        count += 1


@six.python_2_unicode_compatible
class Key(reprutils.ReprEvalMixin):
    """
    Affiliation key function.

    This class is a callable that turns affiliation dicts into keys based on
    the given template.  The key can be used for grouping or defining "unique"
    items when counting.

    E.g.:

      >>> Key("$affiliation")(Key.example)
      "AFF"

      >>> Key("$status | $source_system | $ou_id")(Key.example)
      "AFF/status | SYS | 321"

    """
    repr_id = False
    repr_module = False
    repr_args = ("template",)

    example = {
        'person_id': 123,
        'affiliation': "AFF",
        'status': "AFF/status",
        'source_system': "SYS",
        'ou_id': 321,
    }

    @classmethod
    def prepare_template(cls, template):
        try:
            tpl = string.Template(template)
        except ValueError as e:
            raise ValueError("Invalid key template: %s" % (e,))
        try:
            tpl.substitute(cls.example)
        except KeyError as e:
            raise ValueError("Invalid key template: %s" % (e,))
        return tpl

    def __init__(self, template):
        self.template = template

    @property
    def template(self):
        return self._raw_key

    @template.setter
    def template(self, value):
        tpl = self.prepare_template(value)
        self._raw_key = value
        self._tpl = tpl

    def __call__(self, values):
        return self._tpl.safe_substitute(dict(values))

    def __str__(self):
        return six.text_type(self._raw_key)


def group_by_key(iterable, key):
    pairs = ((key(i), i) for i in iterable)
    return aggregate.dict_collect_lists(pairs)


def count_unique_by_key(iterable, key):
    to_count = list(aggregate.unique(iterable, key=key))
    return len(to_count)


def _write_csv(filename, counts):
    with io.open(filename, mode="w", encoding="utf-8") as f:
        writer = csvutils.UnicodeWriter(f)
        for k in sorted(counts):
            writer.writerow((k, counts[k]))


def _write_json(filename, counts):
    with open(filename, mode="w") as f:
        json.dump(counts, f, indent=2, sort_keys=True)


def write_legacy_report(filename, affiliations):
    """
    Generate a legacy report.

    The legacy report works similar to the previous implementation of this
    script, and includes person and affiliation source primary key counts for
    both affiliation and affiliation status groupings.

    In this report, each affiliation is counted multiple times.
    """
    # Affiliation groupings
    groups = {'total': affiliations}
    groups.update(group_by_key(affiliations, key=Key("$affiliation")))
    groups.update(group_by_key(affiliations, key=Key("$status")))

    # Affiliation counts
    pe_key = Key("$person_id")
    pe_count = {k: count_unique_by_key(groups[k], key=pe_key)
                for k in groups}

    pk_key = Key("$person_id@${affiliation}@${ou_id}@${source_system}")
    pk_count = {k: count_unique_by_key(groups[k], key=pk_key)
                for k in groups}

    # Formatting
    group_size = max(len(k) for k in groups)
    count_size = max(len(str(i))
                     for i in (tuple(pe_count.values())
                               + tuple(pk_count.values())))
    line_fmt = "{:%d}  {:>%d}  {:>%d}" % (group_size,
                                          max(count_size, len("#persons")),
                                          max(count_size, len("#affs")))

    def print_line(key, persons, affs, **kwargs):
        line = line_fmt.format(six.text_type(key), six.text_type(persons),
                               six.text_type(affs))
        print(line, **kwargs)

    # Writing
    with io.open(filename, mode="w", encoding="utf-8") as f:
        print_line("", "#persons", "#affs", file=f)
        for k in sorted(groups):
            print_line(k, pe_count[k], pk_count[k], file=f)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Count affiliations.",
        epilog=textwrap.dedent(
            """
            Examples:

              Count number of affiliations, grouped by affiliation type, and
              write as CSV-rows to stdout:

                %(prog)s /dev/stdout

              Count number of unique persons grouped by affiliation status:

                %(prog)s --key '$status' --unique '$person_id' /dev/stdout

              Count unique org units grouped by affiliation and source system,
              and output as JSON:

                %(prog)s --key '${affiliation}@${source_system}' \\
                         --unique '$ou_id' \\
                         --json /dev/stdout

              Generate a legacy report that counts persons and affs over
              multiple groupings:
                %(prog)s --legacy /dev/stdout

            Key format placeholders:

              - $affiliation - e.g. ANSATT
              - $ou_id - entity id of org unit
              - $person_id - entity id of person
              - $source_system - e.g. FS
              - $status - e.g. ANSATT/tekadm
            """
        ),
    )

    parser.add_argument(
        "--legacy",
        action="store_true",
        help="ignore other options, and generate a legacy plaintext report",
    )

    default_group_key = Key("$affiliation")
    parser.add_argument(
        "-g", "--group-by",
        dest="group_key",
        type=Key,
        default=default_group_key,
        help="group results by %(metavar)s (default: %(default)s)",
        metavar="KEY",
    )

    default_unique_key = Key("${person_id}@${affiliation}@${ou_id}")
    parser.add_argument(
        "-c", "--count-by",
        dest="unique_key",
        type=Key,
        default=default_unique_key,
        help="count unique %(metavar)s in eaach group (default: %(default)s)",
        metavar="KEY",
    )
    default_writer = _write_csv
    fmt_arg = parser.add_mutually_exclusive_group()
    fmt_arg.add_argument(
        "--json",
        action="store_const",
        dest="writer",
        const=_write_json,
        help="write a JSON object (group as attributes, count as values)",
    )
    fmt_arg.add_argument(
        "--csv",
        action="store_const",
        dest="writer",
        const=_write_csv,
        help="write output as CSV rows with 'group,count' (default)",
    )
    fmt_arg.set_defaults(writer=default_writer)
    parser.add_argument(
        "filename",
    )

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('console', args)

    logger.info("start %s", parser.prog)
    logger.debug("args: %r", args)

    db = Factory.get('Database')()

    logger.info("fetching affiliations")
    affiliations = list(get_affiliations(db))
    logger.info("found %d affiliation source entries", len(affiliations))

    if args.legacy:
        logger.debug("generating legacy report...")
        write_legacy_report(args.filename, affiliations)
    else:
        logger.debug("generating report...")
        # Write a generic report based in the input arguments
        logger.info("group by: %s", repr(args.group_key))
        grouped = group_by_key(affiliations, key=args.group_key)

        logger.info("count by: %s", repr(args.unique_key))
        counted = {group: count_unique_by_key(grouped[group],
                                              key=args.unique_key)
                   for group in grouped}

        args.writer(args.filename, counted)

    logger.info("wrote output to %s", args.filename)
    logger.info("done %s", parser.prog)


if __name__ == "__main__":
    main()
