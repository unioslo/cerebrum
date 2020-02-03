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
from __future__ import print_function, unicode_literals

import getopt
import logging
import os
import sys

import cereconf
import Cerebrum.logutils

from Cerebrum.modules.fs.import_from_FS import ImportFromFs, set_filepath
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.modules.xmlutils.xml_helper import XMLHelper
from Cerebrum.utils.atomicfile import FileChangeTooBigError

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
    --undenh-file: Override 'topics' file
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
    --student-undenh-file: Override student on UE file
    --evukursinfo-file: Override evu-kurs xml filename
    --db-user: Connect with given database username
    --db-service: Connect to given database
    --institution: Override insitution number.
                   Default: see cereconf.DEFAULT_INSTITUSJONSNR

    Action:
    -p: Generate person xml file
    -s: Generate studprog xml file
    -r: Generate role xml file
    -e: Generate emne info xml file
    -f: Generate fnr_update xml file
    -o: Generate ou xml file
    -n: Generate netpublication reservation xml file
    -u: Generate undervisningsenhet xml file
    -E: Generate evu_kurs xml file
    -U: Generate student on UE xml file
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
            elif o in ('--institution',):
                self.institution_number = set_filepath(self.datadir, val)


class ImportFromFsNmh(ImportFromFs):
    def __init__(self, fs):
        super(ImportFromFsNmh, self).__init__(fs)


def main():
    Cerebrum.logutils.autoconf('cronjob')
    logger.info("Starting import from FS")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "psrefonuUE",
                                   ["datadir=",
                                    "personinfo-file=",
                                    "studprog-file=",
                                    "roleinfo-file=",
                                    "undenh-file=",
                                    "emneinfo-file=",
                                    "fnr-update-file=",
                                    "netpubl-file=",
                                    "ou-file=",
                                    "misc-func=",
                                    "misc-file=",
                                    "misc-tag=",
                                    "evukursinfo-file=",
                                    "student-undenh-file=",
                                    "db-user=",
                                    "db-service=",
                                    "institution="
                                    ])
    except getopt.GetoptError:
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
    filepaths = FilePaths(opts)
    fsimporter = ImportFromFsNmh(fs)

    misc_tag = None
    misc_func = None
    for o, val in opts:
        try:
            if o in ('-p',):
                fsimporter.write_person_info(filepaths.person_file)
            elif o in ('-s',):
                fsimporter.write_studprog_info(filepaths.studprog_file)
            elif o in ('-r',):
                fsimporter.write_role_info(filepaths.role_file)
            elif o in ('-e',):
                fsimporter.write_emne_info(filepaths.emne_info_file)
            elif o in ('-f',):
                fsimporter.write_fnrupdate_info(filepaths.fnr_update_file)
            elif o in ('-o',):
                fsimporter.write_ou_info(institution_number, filepaths.ou_file)
            elif o in ('-n',):
                fsimporter.write_netpubl_info(filepaths.netpubl_file)
            elif o in ('-u',):
                fsimporter.write_undenh_metainfo(filepaths.undervenh_file)
            elif o in ('-E',):
                fsimporter.write_evukurs_info(filepaths.evu_kursinfo_file)
            elif o in ('-U',):
                fsimporter.write_undenh_student(filepaths.undenh_student_file)
            # We want misc-* to be able to produce multiple file in one
            # script-run
            elif o in ('--misc-func',):
                misc_func = val
            elif o in ('--misc-tag',):
                misc_tag = val
            elif o in ('--misc-file',):
                misc_file = set_filepath(filepaths.datadir, val)
                fsimporter.write_misc_info(misc_file, misc_tag, misc_func)
        except FileChangeTooBigError as msg:
            logger.error("Manual intervention required: %s", msg)
    logger.info("Done with import from FS")


if __name__ == '__main__':
    main()
