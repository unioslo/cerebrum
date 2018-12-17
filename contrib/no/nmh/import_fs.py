#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2018 University of Oslo, Norway
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
from __future__ import unicode_literals

import logging
import argparse
import json
from os.path import join as pj

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.fs.import_fs import FsImporter
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.AutoStud import StudentInfo
from Cerebrum.utils.argutils import add_commit_args

import cereconf

import mx

# Globals
logger = logging.getLogger(__name__)


class FsImporterNmh(FsImporter):
    # def rem_old_aff(self):
    #     person = Factory.get("Person")(self.db)
    #     for k, v in self.old_aff.items():
    #         if v:
    #             ent_id, ou, affi = k.split(':')
    #             person.clear()
    #             person.find(int(ent_id))
    #             person.delete_affiliation(ou, affi, self.co.system_fs)
    def _add_reservations(self, person_info, new_person):
        self.register_fagomrade(new_person, person_info)

        # Reservations
        if self.gen_groups:
            should_add = False
            if person_info.has_key('nettpubl'):
                for row in person_info['nettpubl']:
                    if row.get('akseptansetypekode', "") == "NETTPUBL" and row.get(
                            'status_svar', "") == "J":
                        should_add = True

            if should_add:
                # The student has explicitly given us permission to be
                # published in the directory.
                self._add_res(new_person.entity_id)
            else:
                # The student either hasn't registered an answer to
                # the "Can we publish info about you in the directory"
                # question at all, or has given an explicit "I don't
                # want to appear in the directory" answer.
                self._rem_res(new_person.entity_id)

    def register_fagomrade(self, person, person_info):
        """Register 'fagomrade'/'fagfelt' for a person.
        This is stored in trait_fagomrade_fagfelt as a pickled list of strings.
        The trait is not set if no 'fagfelt' is registered.

        @param person:
          Person db proxy associated with a newly created/fetched person.

        @param person_info:
          Dict returned by StudentInfoParser.

        """
        fnr = "%06d%05d" % (int(person_info["fodselsdato"]),
                            int(person_info["personnr"]))

        fagfelt_trait = person.get_trait(trait=self.co.trait_fagomrade_fagfelt)
        fagfelt = []

        # Extract fagfelt from any fagperson rows
        if 'fagperson' in person_info:
            fagfelt = [data.get('fagfelt') for data in person_info['fagperson']
                       if data.get('fagfelt') is not None]
            # Sort alphabetically as the rows are returned in random order
            fagfelt.sort()

        if fagfelt_trait and not fagfelt:
            logger.debug('Removing fagfelt for %s', fnr)
            person.delete_trait(code=self.co.trait_fagomrade_fagfelt)
        elif fagfelt:
            logger.debug('Populating fagfelt for %s', fnr)
            person.populate_trait(
                code=self.co.trait_fagomrade_fagfelt,
                date=mx.DateTime.now(),
                strval=json.dumps(fagfelt))

        person.write_db()


def main():
    db = Factory.get('Database')()
    db.cl_init(change_program='import_fs')
    co = Factory.get('Constants')(db)
    ou = Factory.get('OU')(db)
    group = Factory.get('Group')(db)

    # parsing
    parser = argparse.ArgumentParser()
    parser = add_commit_args(parser, default=True)
    parser.add_argument(
        '-v', '--verbose',
        action='count')
    parser.add_argument(
        '-p', '--person-file',
        dest='personfile',
        default=pj(cereconf.FS_DATA_DIR, "merged_persons.xml"))
    parser.add_argument(
        '-s', '--studieprogram-file',
        dest='studieprogramfile',
        default=pj(cereconf.FS_DATA_DIR, "studieprog.xml"))
    parser.add_argument(
        '-g', '--generate-groups',
        dest='gen_groups',
        action='store_true')
    parser.add_argument(
        '-d', '--include-delete',
        dest='include_delete',
        action='store_true')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    if "system_fs" not in cereconf.SYSTEM_LOOKUP_ORDER:
        raise SystemExit("Check cereconf, SYSTEM_LOOKUP_ORDER is wrong!")

    group_name = cereconf.FS_GROUP_NAME
    group_desc = cereconf.FS_GROUP_DESC
    try:
        group.find_by_name(group_name)
    except Errors.NotFoundError:
        group.clear()
        ac = Factory.get('Account')(db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        group.populate(ac.entity_id, co.group_visibility_internal,
                       group_name, group_desc)
        group.write_db()

    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        logger.warn("Warning: ENABLE_MKTIME_WORKAROUND is set")

    source = 'system_fs'
    rules = [
    ('fagperson', ('_arbeide', '_hjemsted', '_besok_adr')),
    ('aktiv', ('_hjemsted', None)),
    ('evu', ('_job', '_hjem', None)),
    ]
    adr_map = {
    '_arbeide': ('adrlin1_arbeide', 'adrlin2_arbeide', 'adrlin3_arbeide',
                 'postnr_arbeide', 'adresseland_arbeide'),
    '_hjemsted': ('adrlin1_hjemsted', 'adrlin2_hjemsted',
                  'adrlin3_hjemsted', 'postnr_hjemsted',
                  'adresseland_hjemsted'),
    '_semadr': ('adrlin1_semadr', 'adrlin2_semadr', 'adrlin3_semadr',
                'postnr_semadr', 'adresseland_semadr'),
    '_job': ('adrlin1_job', 'adrlin2_job', 'adrlin3_job', 'postnr_job',
             'adresseland_job'),
    '_hjem': ('adrlin1_hjem', 'adrlin2_hjem', 'adrlin3_hjem',
              'postnr_hjem', 'adresseland_hjem'),
    '_besok_adr': ('institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')
    }

    fs_importer = FsImporterNmh(db, co, ou, group, args.gen_groups,
                            args.include_delete, args.commit,
                            args.studieprogramfile, source, rules, adr_map)

    StudentInfo.StudentInfoParser(args.personfile,
                                  fs_importer.process_person_callback,
                                  logger)

    if args.include_delete:
        fs_importer.rem_old_aff()

    if args.commit:
        fs_importer.db.commit()
        logger.info('Changes were committed to the database')
    else:
        fs_importer.db.rollback()
        logger.info('Dry run. Changes to the database were rolled back')

    logger.info("Found %d persons without name.", fs_importer.no_name)
    logger.info("Completed")


if __name__ == '__main__':
    main()
