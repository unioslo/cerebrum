#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005-2024 University of Oslo, Norway
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
Remove external id from a given source system.

This script removes a given external id-type from a provided source system for
persons with the same id-type (and optionally, the same id-value) in other
autoritative system.

A typical use-case is to remove temporary or obsolete ids, but wanting to keep
them if they would otherwise be lost.

Configuration
-------------
Only duplicates in ``cereconf.SYSTEM_LOOKUP_ORDER`` will be considered.

Example
-------
Generate a report of ids that *would* be deleted by running in dryrun mode:
::

    <script> -s SAP -t NO_BIRTHNO --ignore-value --dryrun --output report.csv

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import six
from functools import partial

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import csvutils
from Cerebrum.utils import file_stream

logger = logging.getLogger(__name__)


def find_candidate_ids(db, source_system, id_type):
    """ Find persons with *id_type* from *source_system*. """
    pe = Factory.get("Person")(db)
    entity_type = pe.const.entity_person
    for row in pe.search_external_ids(
            source_system=source_system,
            id_type=id_type,
            entity_type=entity_type,
            fetchall=False):
        yield (int(row['entity_id']), int(row['external_id']))


def get_duplicate_lookup(db, exclude_system, id_type, ignore_value=False):
    """ Get a lookup to check if a given id entry exists in other systems.  """
    co = Factory.get('Constants')(db)
    other_systems = (set(co.get_system_lookup_order())
                     - set([exclude_system]))

    logger.info("Considering duplicates from %s",
                ", ".join(sorted([six.text_type(s) for s in other_systems])))

    entries = find_candidate_ids(db, other_systems, id_type)
    if ignore_value:
        duplicates = set(p_id for p_id, _ in entries)
    else:
        duplicates = set(entries)

    def is_duplicate(entry):
        if ignore_value:
            value, _ = entry
        else:
            value = entry
        return value in duplicates

    return is_duplicate


def delete_external_id(db, person_id, source_system, id_type):
    pe = Factory.get("Person")(db)
    pe.find(person_id)
    pe._delete_external_id(source_system, id_type)


def write_csv_report(filename, entries):
    with file_stream.get_output_context(filename, encoding="utf-8") as f:
        writer = csvutils.UnicodeWriter(f, dialect=csvutils.CerebrumDialect)
        writer.writerow(("person_id", "external_id"))
        for t in sorted(entries):
            writer.writerow(t)
        f.flush()
        logger.info('Report written to %s', f.name)


def remove_duplicates(db, source_system, id_type, ignore_value=False):
    """
    Delete all *id_type* from *source_system* that exists in other systems.

    :param source_system: The source system to delete from
    :param id_type: The id type to delete
    :param bool ignore_value:
        Ignore the value seen in other systems.

        The default behaviour is to only delete the id if it exists with the
        same value in other systems.  Setting this to ``True`` will delete the
        id-type even if the id-value seen in other systems differs.

    :returns list:
        Returns tuples of (person_id, id_value) for all deleted ids.
    """
    is_duplicate = get_duplicate_lookup(db, source_system, id_type,
                                        ignore_value)

    logger.debug("Finding candidate ids...")
    candidates = sorted(
        set(find_candidate_ids(db, source_system, id_type)))

    deleted = []
    logger.info("Considering %d ids of type %s from %s",
                len(candidates), six.text_type(id_type),
                six.text_type(source_system))
    for i, entry in enumerate(candidates, 1):
        if is_duplicate(entry):
            person_d = dict(zip(['entity_id', 'ext_id'], entry))
            delete_external_id(db, person_d['entity_id'], source_system,
                               id_type)
            deleted.append(entry)

        if not (i % 1000):
            logger.debug("... processed %d candidates", i)

    logger.info("Deleted %d of %d candidates",
                len(deleted), len(candidates))
    return deleted


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source_arg = parser.add_argument(
        "-s", "--source-system",
        default="SAP",
        metavar="SYSTEM",
        help="Source system to remove from (default: %(default)s)",
    )
    id_type_arg = parser.add_argument(
        "-t", "--id-type",
        default="NO_BIRTHNO",
        metavar="IDTYPE",
        help="Id type to remove (default: %(default)s",
    )
    parser.add_argument(
        "--ignore-value",
        action="store_true",
        default="false",
        help="Remove id-types even if the value is different in other systems",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        default=file_stream.DEFAULT_STDOUT_NAME,
        help="write csv report to %(metavar)s (default: stdout)",
    )
    argutils.add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf("tee", args)

    db = Factory.get("Database")()
    co = Factory.get("Constants")(db)
    db.cl_init(change_program=parser.prog)

    get_const = partial(argutils.get_constant, db, parser)
    source_system = get_const(co.AuthoritativeSystem, args.source_system,
                              source_arg)
    id_type = get_const(co.EntityExternalId, args.id_type, id_type_arg)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    deleted = remove_duplicates(db, source_system, id_type, args.ignore_value)
    write_csv_report(args.output, deleted)

    if args.commit:
        db.commit()
        logger.debug('Committed all changes')
    else:
        db.rollback()
        logger.debug('Rolled back all changes')

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
