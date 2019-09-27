#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
Script for gathering data from FS and put it into XML files for further
processing by other scripts.

"""
from __future__ import unicode_literals
from __future__ import print_function

import os
import sys
import getopt
import logging

import cereconf

import Cerebrum.logutils
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.utils.atomicfile import FileChangeTooBigError
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.modules.fs.import_from_FS import ImportFromFs, set_filepath

XML_ENCODING = 'utf-8'

logger = logging.getLogger(__name__)
xml = XMLHelper(encoding=XML_ENCODING)


def usage():
    print("""Usage: %(filename)s [options]

    %(doc)s

    Settings:
    --datadir: Override the directory where all files should be put.
               Default: see cereconf.FS_DATA_DIR

               Note that the datadir can be overriden by the file path
               options, if these are absolute paths.
    --studprog-file: Override studprog xml filename.
                     Default: studieprogrammer.xml
    --personinfo-file: Override person xml filename.
                       Default: person.xml.
    --roleinfo-file: Override role xml filename.
                     Default: roles.xml.
    --emneinfo-file: Override emne info xml filename.
                     Default: emner.xml.
    --fnr-update-file: Override fnr-update xml filename.
                       Default: fnr_update.xml.
    --netpubl-file: Override netpublication filename.
                    Default: nettpublisering.xml.
    --ou-file: Override ou xml filename.
               Default: ou.xml.
    --misc-func: Name of extra function in access_FS to call. Will be called
                 at the next given --misc-file.
    --misc-file: Name of output file for previous set misc-func and misc-tag
                 arguments. Note that a relative filename could be used for
                 putting it into the set datadir.
    --misc-tag: Tag to use in the next given --misc-file argument.
    --topics-file: Override topics xml filename.
                   Default: topics.xml.
    --pre-course-file: Name of output file for pre course information.
                       Default: pre_course.xml.
    --regkort-file: Override regkort xml filename.
                    Default: regkort.xml.
    --betalt-papir-file: Override betalt-papir xml filename.
                         Default: betalt_papir.xml.
    --edu-file: Override edu-info xml filename.
                Default edu_info.xml.
    --db-user: connect with given database username
    --db-service: connect to given database
    --institution: Override institution number.
                   Default: see cereconf.DEFAULT_INSTITUSJONSNR

    Action:
    -p: Generate person xml file
    -s: Generate studprog xml file
    -r: Generate role xml file
    -e: Generate emne info xml file
    -f: Generate fnr_update xml file
    -o: Generate ou xml file
    -n: Generate netpublication reservation xml file
    -t: Generate topics xml file
    -b: Generate betalt-papir xml file
    -R: Generate regkort xml file
    -d: Gemerate edu info xml file
    -P: Generate a pre-course xml file
    """ % {'filename': os.path.basename(sys.argv[0]),
           'doc': __doc__})


class FilePaths(object):
    def __init__(self, opts):
        # Default filepaths
        self.datadir = cereconf.FS_DATA_DIR
        self.person_file = os.path.join(self.datadir, "person.xml")
        self.role_file = os.path.join(self.datadir, "roles.xml")
        self.studprog_file = os.path.join(self.datadir, "studieprog.xml")
        self.ou_file = os.path.join(self.datadir, "ou.xml")
        self.emne_info_file = os.path.join(self.datadir, "emner.xml")
        self.fnr_update_file = os.path.join(self.datadir, "fnr_update.xml")
        self.netpubl_file = os.path.join(self.datadir, "nettpublisering.xml")
        self.undervenh_file = os.path.join(self.datadir, "underv_enhet.xml")
        self.undenh_student_file = os.path.join(self.datadir,
                                                "student_undenh.xml")
        self.evu_kursinfo_file = os.path.join(self.datadir, "evu_kursinfo.xml")
        self.misc_file = None
        # Uio Extras
        self.topics_file = os.path.join(self.datadir, "topics.xml")
        self.regkort_file = os.path.join(self.datadir, "regkort.xml")
        self.betalt_papir_file = os.path.join(self.datadir, "betalt_papir.xml")
        self.edu_file = os.path.join(self.datadir, "edu_info.xml")
        self.pre_course_file = os.path.join(self.datadir, "pre_course.xml")

        # Parse arguments
        for o, val in opts:
            if o in ('--datadir',):
                self.datadir = val
        for o, val in opts:
            if o in ('--emneinfo-file',):
                self.emne_info_file = set_filepath(self.datadir, val)
            elif o in ('--personinfo-file',):
                self.person_file = set_filepath(self.datadir, val)
            elif o in ('--studprog-file',):
                self.studprog_file = set_filepath(self.datadir, val)
            elif o in ('--roleinfo-file',):
                self.role_file = set_filepath(self.datadir, val)
            elif o in ('--fnr-update-file',):
                self.fnr_update_file = set_filepath(self.datadir, val)
            elif o in ('--ou-file',):
                self.ou_file = set_filepath(self.datadir, val)
            elif o in ('--netpubl-file',):
                self.netpubl_file = set_filepath(self.datadir, val)
            elif o in ('--undenh-file',):
                self.undervenh_file = set_filepath(self.datadir, val)
            elif o in ('--student-undenh-file',):
                self.undenh_student_file = set_filepath(self.datadir, val)
            elif o in ('--evukursinfo-file',):
                self.evu_kursinfo_file = set_filepath(self.datadir, val)
            # Uio Extras
            elif o in ('--topics-file',):
                self.topics_file = set_filepath(self.datadir, val)
            elif o in ('--regkort-file',):
                self.regkort_file = set_filepath(self.datadir, val)
            elif o in ('--betalt-papir-file',):
                self.betalt_papir_file = set_filepath(self.datadir, val)
            elif o in ('--edu-file',):
                self.edu_file = set_filepath(self.datadir, val)
            elif o in ('--pre-course-file',):
                self.pre_course_file = set_filepath(self.datadir, val)


class ImportFromFsUio(ImportFromFs):
    def __init__(self, fs):
        super(ImportFromFsUio, self).__init__(fs)

    def write_person_info(self, person_file):
        """Lager fil med informasjon om alle personer registrert i FS som
        vi muligens også ønsker å ha med i Cerebrum.  En person kan
        forekomme flere ganger i filen."""

        # TBD: Burde vi cache alle data, slik at vi i stedet kan lage en
        # fil der all informasjon om en person er samlet under en egen
        # <person> tag?

        logger.info("Writing person info to '%s'", person_file)
        f = SimilarSizeWriter(person_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")

        # Aktive studenter
        cols, students = self._ext_cols(self.fs.student.list_aktiv())
        for s in students:
            f.write(
                xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'aktiv') + "\n")

        # Eksamensmeldinger
        cols, students = self._ext_cols(
            self.fs.student.list_eksamensmeldinger())
        for s in students:
            f.write(
                xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'eksamen') + "\n")

        # EVU students
        # En del EVU studenter vil være gitt av søket over
        cols, students = self._ext_cols(self.fs.evu.list())
        for e in students:
            f.write(
                xml.xmlify_dbrow(e, xml.conv_colnames(cols), 'evu') + "\n")

        # Privatister, privatistopptak til studieprogram eller emne-privatist
        cols, students = self._ext_cols(self.fs.student.list_privatist())
        for s in students:
            self.fix_float(s)
            f.write(
                xml.xmlify_dbrow(
                    s, xml.conv_colnames(cols),
                    'privatist_studieprogram') + "\n")
        cols, students = self._ext_cols(self.fs.student.list_privatist_emne())
        for s in students:
            f.write(
                xml.xmlify_dbrow(
                    s, xml.conv_colnames(cols), 'privatist_emne') + "\n")

        # Drgradsstudenter med opptak
        cols, drstudents = self._ext_cols(self.fs.student.list_drgrad())
        for d in drstudents:
            f.write(
                xml.xmlify_dbrow(d, xml.conv_colnames(cols), 'drgrad') + "\n")

        # Fagpersoner
        cols, fagpersoner = self._ext_cols(
            self.fs.undervisning.list_fagperson_semester())
        for p in fagpersoner:
            f.write(
                xml.xmlify_dbrow(
                    p, xml.conv_colnames(cols), 'fagperson') + "\n")

        # Studenter med opptak, privatister (=opptak i studiepgraommet
        # privatist) og Alumni
        cols, students = self._ext_cols(self.fs.student.list())
        for s in students:
            # The Oracle driver thinks the result of a union of ints is float
            self.fix_float(s)
            f.write(
                xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'opptak') + "\n")

        # Aktive emnestudenter
        cols, students = self._ext_cols(self.fs.student.list_aktiv_emnestud())
        for s in students:
            f.write(
                xml.xmlify_dbrow(
                    s, xml.conv_colnames(cols), 'emnestud') + "\n")

        # Semester-registrering
        cols, students = self._ext_cols(self.fs.student.list_semreg())
        for s in students:
            f.write(
                xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'regkort') + "\n")

        # Studenter i permisjon (ogs� dekket av GetStudinfOpptak)
        cols, permstud = self._ext_cols(self.fs.student.list_permisjon())
        for p in permstud:
            f.write(
                xml.xmlify_dbrow(
                    p, xml.conv_colnames(cols), 'permisjon') + "\n")

        #
        # STA har bestemt at personer med tilbud ikke skal ha tilgang til noen
        # IT-tjenester inntil videre. Derfor slutter vi på nåværende tidspunkt
        # å hente ut informasjon om disse. Ettersom det er usikkert om dette
        # vil endre seg igjen i nær fremtid lar vi koden ligge for nå.
        #
        # # Personer som har fått tilbud
        # cols, tilbudstud = self._ext_cols(fs.student.list_tilbud())
        # for t in tilbudstud:
        #     f.write(
        #         xml.xmlify_dbrow(
        #             t, xml.conv_colnames(cols), 'tilbud') + "\n")

        f.write("</data>\n")
        f.close()

    def write_ou_info(self, institution_number, ou_file):
        """Lager fil med informasjon om alle OU-er"""
        logger.info("Writing OU info to '%s'", ou_file)
        f = SimilarSizeWriter(ou_file, mode='w', encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, ouer = self._ext_cols(
            self.fs.info.list_ou(institution_number))
        for o in ouer:
            sted = {}
            for fs_col, xml_attr in (
                    ('faknr', 'fakultetnr'),
                    ('instituttnr', 'instituttnr'),
                    ('gruppenr', 'gruppenr'),
                    ('stedakronym', 'akronym'),
                    ('stedakronym', 'forkstednavn'),
                    ('stednavn_bokmal', 'stednavn'),
                    ('faknr_org_under', 'fakultetnr_for_org_sted'),
                    ('instituttnr_org_under', 'instituttnr_for_org_sted'),
                    ('gruppenr_org_under', 'gruppenr_for_org_sted'),
                    ('adrlin1', 'adresselinje1_intern_adr'),
                    ('adrlin2', 'adresselinje2_intern_adr'),
                    ('postnr', 'poststednr_intern_adr'),
                    ('adrlin1_besok', 'adresselinje1_besok_adr'),
                    ('adrlin2_besok', 'adresselinje2_besok_adr'),
                    ('postnr_besok', 'poststednr_besok_adr')):
                if o[fs_col] is not None:
                    sted[xml_attr] = xml.escape_xml_attr(o[fs_col])
            komm = []
            for fs_col, typekode in (
                    ('telefonnr', 'EKSTRA TLF'),
                    ('faxnr', 'FAX'),
            ):
                if o[fs_col]:  # Skip NULLs and empty strings
                    komm.append(
                        {'kommtypekode': xml.escape_xml_attr(typekode),
                         'kommnrverdi': xml.escape_xml_attr(o[fs_col])})
            # TODO: Kolonnene 'url' og 'bibsysbeststedkode' hentes ut fra
            # FS, men tas ikke med i outputen herfra.
            f.write('<sted ' +
                    ' '.join(["%s=%s" % item for item in sted.items()]) +
                    '>\n')
            for k in komm:
                f.write('<komm ' +
                        ' '.join(["%s=%s" % item for item in k.items()]) +
                        ' />\n')
            f.write('</sted>\n')
        f.write("</data>\n")
        f.close()


def main():
    Cerebrum.logutils.autoconf('cronjob')
    logger.info("Starting import from FS")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "psrefontbRdP",
                                   ["datadir=",
                                    "personinfo-file=",
                                    "studprog-file=",
                                    "roleinfo-file=",
                                    "emneinfo-file=",
                                    "fnr-update-file=",
                                    "netpubl-file=",
                                    "ou-file=",
                                    "misc-func=",
                                    "misc-file=",
                                    "misc-tag=",
                                    "topics-file=",
                                    "betalt-papir-file=",
                                    "regkort-file=",
                                    "edu-file=",
                                    "pre-course-file=",
                                    "db-user=",
                                    "db-service=",
                                    "institution="
                                    ])
    except getopt.GetoptError as error:
        print(error)
        usage()
        sys.exit(2)

    db_user = None
    db_service = None
    institution_number = cereconf.DEFAULT_INSTITUSJONSNR
    for o, val in opts:
        if o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val
        elif o in ('--institution',):
            institution_number = val
    fs = make_fs(user=db_user, database=db_service)
    file_paths = FilePaths(opts)
    fsimporter = ImportFromFsUio(fs)

    misc_tag = None
    misc_func = None
    for o, val in opts:
        try:
            if o in ('-p',):
                fsimporter.write_person_info(file_paths.person_file)
            elif o in ('-s',):
                fsimporter.write_studprog_info(file_paths.studprog_file)
            elif o in ('-r',):
                fsimporter.write_role_info(file_paths.role_file)
            elif o in ('-e',):
                fsimporter.write_emne_info(file_paths.emne_info_file)
            elif o in ('-f',):
                fsimporter.write_fnrupdate_info(file_paths.fnr_update_file)
            elif o in ('-o',):
                fsimporter.write_ou_info(institution_number,
                                         file_paths.ou_file)
            elif o in ('-n',):
                fsimporter.write_netpubl_info(file_paths.netpubl_file)
            elif o in ('-t',):
                fsimporter.write_topic_info(file_paths.topics_file)
            elif o in ('-b',):
                fsimporter.write_betalt_papir_info(
                    file_paths.betalt_papir_file)
            elif o in ('-R',):
                fsimporter.write_regkort_info(file_paths.regkort_file)
            elif o in ('-d',):
                fsimporter.write_edu_info(file_paths.edu_file)
            elif o in ('-P',):
                fsimporter.write_forkurs_info(file_paths.pre_course_file)
            # We want misc-* to be able to produce multiple file in one
            # script-run
            elif o in ('--misc-func',):
                misc_func = val
            elif o in ('--misc-tag',):
                misc_tag = val
            elif o in ('--misc-file',):
                misc_file = set_filepath(file_paths.datadir, val)
                fsimporter.write_misc_info(misc_file, misc_tag, misc_func)
        except FileChangeTooBigError as msg:
            logger.error("Manual intervention required: %s", msg)
    logger.info("Done with import from FS")


if __name__ == '__main__':
    main()
