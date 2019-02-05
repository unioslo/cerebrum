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

"""Script for gathering data from FS and put it into XML files for further
processing by other scripts.

"""
from __future__ import unicode_literals
from __future__ import print_function

import os
import sys
import getopt
import logging

import Cerebrum.logutils
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.utils.atomicfile import FileChangeTooBigError
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.modules.fs.import_from_FS import ImportFromFs

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
    --undenh-file: Override undenh_meta file
    --edu-info-file: edu info file (undenh/undakt/kullklass)
    --db-user: Connect with given database username
    --db-service: Connect to given database

    Action:
    -p: Generate person xml file
    -s: Generate studprog xml file
    -r: Generate role xml file
    -e: Generate emne info xml file
    -f: Generate fnr_update xml file
    -o: Generate ou xml file
    -n: Generate netpublication reservation xml file
    -u: Generate undervisningsenhet xml file
    -i: Generate edu info xml file (student at undenh/undakt/kullklasse)
    """ % {'filename': os.path.basename(sys.argv[0]),
           'doc': __doc__})


class ImportFromFsHiof(ImportFromFs):
    def __init__(self, opts, fs):
        super(ImportFromFsHiof, self).__init__(opts, fs)
        self.edu_info_file = "edu-info.xml"

        # Parse arguments
        for o, val in opts:
            if o in ('--edu-info-file',):
                self.edu_info_file = val

    def write_person_info(self, outfile):
        """Lager fil med informasjon om alle personer registrert i FS som
        vi muligens også ønsker å ha med i Cerebrum.  En person kan
        forekomme flere ganger i filen."""

        # TBD: Burde vi cache alle data, slik at vi i stedet kan lage en
        # fil der all informasjon om en person er samlet under en egen
        # <person> tag?

        logger.info("Writing person info to '%s'", outfile)
        f = SimilarSizeWriter(outfile, mode='w', encoding=XML_ENCODING)
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
            f.write(xml.xmlify_dbrow(
                s, xml.conv_colnames(cols), 'eksamen') + "\n")

        # Aktive fagpersoner ved Hiøf
        cols, fagperson = self._ext_cols(
            self.fs.undervisning.list_fagperson_semester())
        for p in fagperson:
            f.write(
                xml.xmlify_dbrow(
                    p, xml.conv_colnames(cols), 'fagperson') + "\n")

        f.write("</data>\n")
        f.close()

    def write_edu_info(self, outfile):
        """Lag en fil med informasjon om alle studentenes 'aktiviteter'
        registrert i FS.

        Spesifikt, lister vi opp alle deltagelser ved:

          - undenh
          - undakt
          - kullklasser
          - kull
        """

        logger.info("Writing edu info for all students")
        f = SimilarSizeWriter(outfile, mode='w', encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")

        for xml_tag, generator in (
                ("undenh",
                 self.fs.undervisning.list_studenter_alle_undenh),
                ("undakt",
                 self.fs.undervisning.list_studenter_alle_undakt),
                ("kullklasse",
                 self.fs.undervisning.list_studenter_alle_kullklasser),
                ("kull",
                 self.fs.undervisning.list_studenter_alle_kull)):
            logger.debug("Processing %s entries", xml_tag)
            for row in generator():
                keys = row.keys()
                f.write(xml.xmlify_dbrow(row, keys, xml_tag) + "\n")

        f.write("</data>\n")
        f.close()


def main():
    Cerebrum.logutils.autoconf('cronjob')
    logger.info("Starting import from FS")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "psrefonui",
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
                                    "undenh-file=",
                                    "edu-info-file=",
                                    "db-user=",
                                    "db-service="
                                    ])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    db_user = None
    db_service = None
    for o, val in opts:
        if o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val

    fs = make_fs(user=db_user, database=db_service)
    fsimporter = ImportFromFsHiof(opts, fs)

    misc_tag = None
    misc_func = None
    for o, val in opts:
        try:
            if o in ('-p',):
                fsimporter.write_person_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.person_file))
            elif o in ('-s',):
                fsimporter.write_studprog_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.studprog_file))
            elif o in ('-r',):
                fsimporter.write_role_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.role_file))
            elif o in ('-e',):
                fsimporter.write_emne_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.emne_info_file))
            elif o in ('-f',):
                fsimporter.write_fnrupdate_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.fnr_update_file))
            elif o in ('-o',):
                fsimporter.write_ou_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.ou_file))
            elif o in ('-n',):
                fsimporter.write_netpubl_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.netpubl_file))
            elif o in ('-u',):
                fsimporter.write_undenh_metainfo(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.undervenh_file))
            elif o in ('-i',):
                fsimporter.write_edu_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, fsimporter.edu_info_file))
            # We want misc-* to be able to produce multiple file in one
            # script-run
            elif o in ('--misc-func',):
                misc_func = val
            elif o in ('--misc-tag',):
                misc_tag = val
            elif o in ('--misc-file',):
                fsimporter.write_misc_info(
                    fsimporter.set_filepath(
                        fsimporter.datadir, val), misc_tag, misc_func)
        except FileChangeTooBigError as msg:
            logger.error("Manual intervention required: %s", msg)
    logger.info("Done with import from FS")


if __name__ == '__main__':
    main()
