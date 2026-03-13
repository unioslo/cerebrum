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
FS import for NMH.

fagfelt trait
    The NMH import adds import of a trait for storing field of study in a
    special trait (fagfelt).

    NMH has a custom query for getting these values from FS in
    :meth:`Cerebrum.modules.no.nmh.access_FS.NMHUndervisning.list_fagperson_semester`
    The values are later used to generate `eduPersonEntitlement` in
    :mod:`Cerebrum.modules.no.nmh.OrgLdif`.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import json
import logging
import os.path

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.fs.import_fs import FsImporter
from Cerebrum.modules.no.uio.AutoStud import StudentInfo
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def parse_fagfelt(person_info):
    """
    Extract subject area values from student data.

    >>> parse_fagfelt({})
    None
    >>> parse_fagfelt({'fagperson': [{'fagfelt': 'foo'}, {'fagfelt': 'bar'}]})
    ["bar", "foo"]
    """
    fagperson = person_info.get('fagperson') or []
    fields = [f['fagfelt'] for f in fagperson if f.get('fagfelt')]
    return sorted(fields)


class FsImporterNmh(FsImporter):

    def _update_person(self, person, person_info):
        super(FsImporterNmh, self)._update_person(person, person_info)
        self._register_fagomrade(person, person_info)

    def _register_fagomrade(self, person, person_info):
        """
        Add subject / field (fagomrade / fagfelt) for a person.

        This is stored in a custom NMH trait (trait_fagomrade_fagfelt) as a
        JSON-serialized list of strings.

        The trait is not set if no 'fagfelt' is registered.
        """
        trait_type = self.co.trait_fagomrade_fagfelt
        old_fagfelt = person.get_trait(trait=trait_type) or {}

        # Extract fagfelt from any fagperson rows
        new_fagfelt = parse_fagfelt(person_info)
        new_serialized = json.dumps(new_fagfelt)

        if old_fagfelt and not new_fagfelt:
            logger.debug("Removing fagfelt for person id: %d",
                         person.entity_id)
            person.delete_trait(code=trait_type)
            person.write_db()
        elif new_fagfelt and new_serialized != old_fagfelt.get('strval'):
            logger.debug("Updating fagfelt for person id: %d",
                         person.entity_id)
            person.populate_trait(code=trait_type, strval=new_serialized)
            person.write_db()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--person-file',
        dest='personfile',
        default=os.path.join(cereconf.FS_DATA_DIR, "merged_persons.xml"),
    )
    parser.add_argument(
        '-s', '--studieprogram-file',
        dest='studieprogramfile',
        default=os.path.join(cereconf.FS_DATA_DIR, "studieprog.xml"),
    )
    parser.add_argument(
        '-g', '--generate-groups',
        dest='gen_groups',
        action='store_true',
    )
    parser.add_argument(
        '-d', '--include-delete',
        dest='include_delete',
        action='store_true',
    )
    add_commit_args(parser, default=True)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info("Start %s", parser.prog)
    logger.debug("args: %s", repr(args))

    source = 'system_fs'
    rules = [
        ('fagperson', ('_arbeide', '_hjemsted', '_besok_adr')),
        ('aktiv', ('_hjemsted', '_semadr', None)),
        ('evu', ('_job', '_hjem', None)),
    ]
    address_map = {
        '_arbeide': (
            'adrlin1_arbeide',
            'adrlin2_arbeide',
            'adrlin3_arbeide',
            'postnr_arbeide',
            'adresseland_arbeide',
        ),
        '_hjemsted': (
            'adrlin1_hjemsted',
            'adrlin2_hjemsted',
            'adrlin3_hjemsted',
            'postnr_hjemsted',
            'adresseland_hjemsted',
        ),
        '_semadr': (
            'adrlin1_semadr',
            'adrlin2_semadr',
            'adrlin3_semadr',
            'postnr_semadr',
            'adresseland_semadr',
        ),
        '_job': (
            'adrlin1_job',
            'adrlin2_job',
            'adrlin3_job',
            'postnr_job',
            'adresseland_job',
        ),
        '_hjem': (
            'adrlin1_hjem',
            'adrlin2_hjem',
            'adrlin3_hjem',
            'postnr_hjem',
            'adresseland_hjem',
        ),
        '_besok_adr': (
            'institusjonsnr',
            'faknr',
            'instituttnr',
            'gruppenr',
        ),
    }

    fs_importer = FsImporterNmh(
        gen_groups=args.gen_groups,
        include_delete=args.include_delete,
        commit=args.commit,
        studieprogramfile=args.studieprogramfile,
        source=source,
        rules=rules,
        adr_map=address_map,
    )

    # Run import
    StudentInfo.StudentInfoParser(
        args.personfile,
        fs_importer.process_person_callback,
        logger,
    )

    if args.include_delete:
        fs_importer.rem_old_aff()

    if args.commit:
        fs_importer.db.commit()
        logger.info('Changes were committed to the database')
    else:
        fs_importer.db.rollback()
        logger.info('Dry run. Changes to the database were rolled back')

    logger.info("Found %d persons without name", fs_importer.no_name)
    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
