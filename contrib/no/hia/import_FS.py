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
import datetime
from os.path import join as pj

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.fs.import_fs import FsImporter
from Cerebrum.modules.no.uio.AutoStud import StudentInfo
from Cerebrum.utils.argutils import add_commit_args

import cereconf

# Globals
logger = logging.getLogger(__name__)


class FsImporterUia(FsImporter):
    def _get_person_data(self, person_info, fnr):
        etternavn = None
        fornavn = None
        studentnr = None
        birth_date = None
        affiliations = []
        aktiv_sted = []

        # Iterate over all person_info entries and extract relevant data
        for dta_type in person_info.keys():
            x = person_info[dta_type]
            p = x[0]
            if isinstance(p, basestring):
                continue
            if dta_type not in ('tilbud', 'eksamen', 'evu'):
                if 'studentnr_tildelt' in p:
                    studentnr = p['studentnr_tildelt']
                else:
                    logger.info("\n%s mangler studentnr!", fnr)
            # Get name
            if dta_type in ('aktiv',
                            'tilbud',
                            'evu',
                            'privatist_studieprogram',
                            ):
                etternavn = p['etternavn']
                fornavn = p['fornavn']

            if not birth_date and 'dato_fodt' in p:
                birth_date = datetime.datetime.strptime(p['dato_fodt'],
                                                        "%Y-%m-%d %H:%M:%S.%f")

            # Get affiliations
            if dta_type in ('aktiv',):
                for row in x:
                    # aktiv_sted is necessary in order to avoid different
                    # affiliation statuses to a same 'stedkode' to be
                    # overwritten e.i. if a person has both affiliations status
                    # 'tilbud' and aktive to a single stedkode we want to
                    # register the  status 'aktive' in cerebrum
                    if self.studieprog2sko[row['studieprogramkode']] is not \
                            None:
                        aktiv_sted.append(
                            int(self.studieprog2sko[row['studieprogramkode']]))
                        self._process_affiliation(
                            self.co.affiliation_student,
                            self.co.affiliation_status_student_aktiv,
                            affiliations,
                            self.studieprog2sko[row['studieprogramkode']])
            elif dta_type in ('evu',):
                for row in x:
                    self._process_affiliation(
                        self.co.affiliation_student,
                        self.co.affiliation_status_student_evu,
                        affiliations,
                        self._get_sko(p, 'faknr_adm_ansvar',
                                      'instituttnr_adm_ansvar',
                                      'gruppenr_adm_ansvar'))
            elif dta_type in ('privatist_studieprogram',):
                for row in x:
                    self._process_affiliation(
                        self.co.affiliation_student,
                        self.co.affiliation_status_student_privatist,
                        affiliations, self.studieprog2sko[
                            row['studieprogramkode']])
            elif dta_type in ('tilbud',):
                for row in x:
                    subtype = self.co.affiliation_status_student_tilbud
                    if self.studieprog2sko[row['studieprogramkode']] in \
                            aktiv_sted:
                        subtype = self.co.affiliation_status_student_aktiv
                    self._process_affiliation(self.co.affiliation_student,
                                              subtype, affiliations,
                                              self.studieprog2sko[
                                                  row['studieprogramkode']])
        return (etternavn, fornavn, studentnr, birth_date, affiliations,
                aktiv_sted)


def main():
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

    source = 'system_lt'
    rules = [
        ('tilbud', ('_kontakt', '_hjemsted', None)),
        ('aktiv', ('_semadr', '_hjemsted', None)),
        ('evu', ('_job', '_hjem', None)),
        ('privatist_studieprogram', ('_semadr', '_hjemsted', None)),
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
        '_kontakt': ('adrlin1_kontakt', 'adrlin2_kontakt', 'adrlin3_kontakt',
                     'postnr_kontakt', 'adresseland_kontakt'),
        '_besok_adr': ('institusjonsnr', 'faknr', 'instituttnr', 'gruppenr')
    }
    reservation_query = ('tilbud', 'aktiv', 'privatist_studieprogram', 'evu',)
    fs_importer = FsImporterUia(args.gen_groups,
                                args.include_delete, args.commit,
                                args.studieprogramfile, source, rules, adr_map,
                                find_person_by='studentnr',
                                reservation_query=reservation_query)

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
