#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2002-2007 University of Oslo, Norway
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

import argparse
import logging
import datetime
from os.path import join as pj

import Cerebrum.logutils
import Cerebrum.logutils.options
import cereconf
from Cerebrum.modules.fs.import_fs import FsImporter
from Cerebrum.modules.no.uio.AutoStud import StudentInfo
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)

"""Importerer personer fra FS iht. fs_import.txt."""


class FsImporterUit(FsImporter):
    def __init__(self, gen_groups, include_delete, commit,
                 studieprogramfile, source, rules, adr_map, emnefile,
                 rule_map, reg_fagomr=False,
                 reservation_query=None):

        super(FsImporterUit, self).__init__(
            gen_groups, include_delete, commit, studieprogramfile, source,
            rules, adr_map, rule_map=rule_map, reg_fagomr=reg_fagomr,
            reservation_query=reservation_query)

        self._init_emne2sko(emnefile)

    def _init_emne2sko(self, emnefile):
        self.emne2sko = {}
        for e in StudentInfo.EmneDefParser(emnefile):
            self.emne2sko[e['emnekode']] = self._get_sko(
                e,
                'faknr_reglement',
                'instituttnr_reglement',
                'gruppenr_reglement')

    def _init_aff_status_pri_order(self):
        aff_status_pri_order = [  # Most significant first
            self.co.affiliation_status_student_drgrad,
            self.co.affiliation_status_student_aktiv,
            self.co.affiliation_status_student_emnestud,
            self.co.affiliation_status_student_evu,
            self.co.affiliation_status_student_privatist,
            self.co.affiliation_status_student_opptak,
            self.co.affiliation_status_student_alumni,
            self.co.affiliation_status_student_soker
        ]
        aff_status_pri_order = dict(
            (int(status), index) for index, status in
            enumerate(aff_status_pri_order))

        self.aff_status_pri_order = aff_status_pri_order

    def _filter_affiliations(self, affiliations):
        """The affiliation list with cols (ou, affiliation, status) may
        contain multiple status values for the same (ou, affiliation)
        combination, while the db-schema only allows one.  Return a list
        where duplicates are removed, preserving the most important
        status.  """

        affiliations.sort(
            lambda x, y: (
                self.aff_status_pri_order.get(int(y[2]), 99) -
                self.aff_status_pri_order.get(int(x[2]), 99)))
        aktiv = False

        for ou, aff, aff_status in affiliations:
            if (
                aff_status == int(self.co.affiliation_status_student_aktiv) or
                aff_status == int(self.co.affiliation_status_student_drgrad) or
                aff_status == int(self.co.affiliation_status_student_evu)
            ):
                aktiv = True

        ret = {}
        for ou, aff, aff_status in affiliations:
            if aff_status == int(
                    self.co.affiliation_status_student_emnestud) and aktiv:
                logger.debug("Dropping emnestud-affiliation")
                continue
            else:
                ret[(ou, aff)] = aff_status
        return [(ou, aff, aff_status) for (ou, aff), aff_status in ret.items()]

    def _get_person_data(self, person_info, fnr):
        etternavn = None
        fornavn = None
        birth_date = None
        studentnr = None
        affiliations = []
        aktiv_sted = []

        # Iterate over all person_info entries and extract relevant data
        if 'aktiv' in person_info:
            for row in person_info['aktiv']:
                if self.studieprog2sko[row['studieprogramkode']] is not None:
                    aktiv_sted.append(
                        int(self.studieprog2sko[row['studieprogramkode']]))
                    logger.debug("App2akrivts")

        for dta_type in person_info.keys():
            x = person_info[dta_type]
            p = x[0]
            if isinstance(p, str):
                continue
            # Get name
            if dta_type in (
                    'fagperson',
                    'opptak',
                    'tilbud',
                    'evu',
                    'privatist_emne',
                    'privatist_studieprogram',
                    'alumni',
                    'emnestud',):
                etternavn = p['etternavn']
                fornavn = p['fornavn']

                if not birth_date and 'dato_fodt' in p:
                    birth_date = datetime.datetime.strptime(
                        p['dato_fodt'],
                        "%Y-%m-%d %H:%M:%S.%f")
            if 'studentnr_tildelt' in p:
                studentnr = p['studentnr_tildelt']
            # Get affiliations
            if dta_type in ('fagperson',):
                self._process_affiliation(
                    self.co.affiliation_tilknyttet,
                    self.co.affiliation_tilknyttet_fagperson,
                    affiliations,
                    self._get_sko(p,
                                  'faknr',
                                  'instituttnr',
                                  'gruppenr',
                                  'institusjonsnr'))
            elif dta_type in ('opptak',):
                for row in x:
                    subtype = self.co.affiliation_status_student_opptak
                    if (self.studieprog2sko[row['studieprogramkode']] in
                            aktiv_sted):
                        subtype = self.co.affiliation_status_student_aktiv
                    elif row['studierettstatkode'] == 'EVU':
                        subtype = self.co.affiliation_status_student_evu
                    elif row['studierettstatkode'] == 'FULLFØRT':
                        subtype = self.co.affiliation_status_student_alumni
                    elif int(row['studienivakode']) >= 980:
                        subtype = self.co.affiliation_status_student_drgrad
                    self._process_affiliation(
                        self.co.affiliation_student,
                        subtype,
                        affiliations,
                        self.studieprog2sko[row['studieprogramkode']])
            elif dta_type in ('emnestud',):
                for row in x:
                    subtype = self.co.affiliation_status_student_emnestud
                    # We may have some situations here where students get
                    # emnestud and aonther affiliation to the same sko,
                    # but this seems to work for now.
                    try:
                        sko = self.emne2sko[row['emnekode']]
                    except KeyError:
                        logger.warn("Fant ingen emner med koden %s",
                                    p['emnekode'])
                        continue
                    if sko in aktiv_sted:
                        subtype = self.co.affiliation_status_student_aktiv
                    self._process_affiliation(self.co.affiliation_student,
                                              subtype,
                                              affiliations,
                                              sko)
            elif dta_type in ('privatist_studieprogram',):
                self._process_affiliation(
                    self.co.affiliation_student,
                    self.co.affiliation_status_student_privatist,
                    affiliations,
                    self.studieprog2sko[p['studieprogramkode']])
            elif dta_type in ('privatist_emne',):
                try:
                    sko = self.emne2sko[p['emnekode']]
                except KeyError:
                    logger.warn(
                        "Fant ingen emner med koden %s" % p['emnekode'])
                    continue
                self._process_affiliation(
                    self.co.affiliation_student,
                    self.co.affiliation_status_student_privatist,
                    affiliations,
                    sko)
            elif dta_type in ('perm',):
                self._process_affiliation(
                    self.co.affiliation_student,
                    self.co.affiliation_status_student_aktiv,
                    affiliations,
                    self.studieprog2sko[p['studieprogramkode']])
            elif dta_type in ('tilbud',):
                for row in x:
                    self._process_affiliation(
                        self.co.affiliation_student,
                        self.co.affiliation_status_student_tilbud,
                        affiliations,
                        self.studieprog2sko[row['studieprogramkode']])
            elif dta_type in ('evu',):
                self._process_affiliation(
                    self.co.affiliation_student,
                    self.co.affiliation_status_student_evu,
                    affiliations,
                    self._get_sko(p,
                                  'faknr_adm_ansvar',
                                  'instituttnr_adm_ansvar',
                                  'gruppenr_adm_ansvar'))
            else:
                logger.debug("No such affiliation type: %s, skipping",
                             dta_type)

        rv = {'fnr': fnr,
              'etternavn': etternavn,
              'fornavn':  fornavn,
              'studentnr':  studentnr,
              'birth_date':  birth_date,
              'affiliations':  affiliations,
              'aktiv_sted': aktiv_sted}
        return rv

    #TODO: for some reason this code block causes some people not to be imported
    #def _db_add_person(self, person, person_info, pd):
    #    try:
    #        db_deceased = person.deceased_date
    #    except AttributeError:
    #        pass
    #    else:
    #        if db_deceased is not None:
    #            logger.warn("Person is deceased")
    #    super(FsImporterUit, self)._db_add_person(person, person_info, pd)

def main():
    parser = argparse.ArgumentParser()
    parser = add_commit_args(parser, default=True)
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='Be extra verbose in the logs.')
    parser.add_argument(
        '-p', '--person-file',
        dest='personfile',
        default=pj(cereconf.FS_DATA_DIR, "merged_persons.xml"),
        help='Specify where the person file is located.')
    parser.add_argument(
        '-s', '--studieprogram-file',
        dest='studieprogramfile',
        default=pj(cereconf.FS_DATA_DIR, "studieprogrammer.xml"),
        help='Specify where the study programs file is located.')
    parser.add_argument(
        '-e', '--emne-file',
        dest='emnefile',
        default=pj(cereconf.FS_DATA_DIR, "emner.xml"),
        help='Specify where the course file is located.')
    parser.add_argument(
        '-g', '--generate-groups',
        dest='gen_groups',
        action='store_true',
        help="""If set, the group for accept for being published at uio.no
             gets populated with the students.""")
    parser.add_argument(
        '-d', '--include-delete',
        dest='include_delete',
        action='store_true',
        help="""If set, old person affiliations are deleted from the students
             that should not have this anymore.""")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args()
    Cerebrum.logutils.autoconf('cronjob', args)

    source = 'system_fs'
    rules = [
        ('fagperson', ('_arbeide', '_hjemsted', '_besok_adr')),
        ('aktiv', ('_semadr', '_hjemsted', None)),
        ('emnestud', ('_semadr', '_hjemsted', None)),
        ('evu', ('_job', '_hjem', None)),
        ('drgrad', ('_semadr', '_hjemsted', None)),
        ('privatist_emne', ('_semadr', '_hjemsted', None)),
        ('privatist_studieprogram', ('_semadr', '_hjemsted', None)),
        ('opptak', (None, '_hjemsted', None)),
    ]
    rule_map = {
        'aktiv': 'opptak'
    }
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

    fsimporter = FsImporterUit(args.gen_groups,
                               args.include_delete,
                               args.commit,
                               args.studieprogramfile,
                               source,
                               rules,
                               adr_map,
                               args.emnefile,
                               rule_map)
    StudentInfo.StudentInfoParser(args.personfile,
                                  fsimporter.process_person_callback,
                                  logger)
    if args.include_delete:
        fsimporter.rem_old_aff(spare_active_account_affs=True)

    if args.commit:
        fsimporter.db.commit()
        logger.info('Changes were committed to the database')
    else:
        fsimporter.db.rollback()
        logger.info('Dry run. Changes to the database were rolled back')

    logger.info("Found %d persons without name." % fsimporter.no_name)
    logger.info("Completed")


if __name__ == '__main__':
    main()
