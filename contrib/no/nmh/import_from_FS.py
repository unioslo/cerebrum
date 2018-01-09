#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003 University of Oslo, Norway
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

import sys
import os
import getopt

import cerebrum_path
import cereconf

from Cerebrum import database
from Cerebrum.extlib import xmlprinter
from Cerebrum.Utils import Factory
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.atomicfile import MinimumSizeWriter
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules.no.nmh.access_FS import FS

xml = XMLHelper()
fs = None

KiB = 1024
MiB = KiB**2

def _ext_cols(db_rows):
    # TBD: One might consider letting xmlify_dbrow handle this
    cols = None
    if db_rows:
        cols = list(db_rows[0].keys())
    return cols, db_rows

def write_person_info(outfile):
    f = SimilarSizeWriter(outfile)
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")

    # Aktive fagpersoner ved NMH
    cols, fagperson = _ext_cols(fs.undervisning.list_fagperson_semester())
    for p in fagperson:
        f.write(xml.xmlify_dbrow(p, xml.conv_colnames(cols), 'fagperson') + "\n")
    # Aktive ordinære studenter ved NMH
    cols, student = _ext_cols(fs.student.list_aktiv())
    for a in student:
        f.write(xml.xmlify_dbrow(a, xml.conv_colnames(cols), 'aktiv') + "\n")
    # Eksamensmeldinger
    cols, student = _ext_cols(fs.student.list_eksamensmeldinger())
    for s in student:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'eksamen') + "\n")
    # EVU-studenter ved NMH
    cols, student = _ext_cols(fs.evu.list())
    for e in student:
        f.write(xml.xmlify_dbrow(e, xml.conv_colnames(cols), 'evu') + "\n")

    f.write("</data>\n")
    f.close()

def write_netpubl_info(outfile):
    """Lager fil med informasjon om status nettpublisering"""
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    cols, nettpubl = _ext_cols(fs.person.list_status_nettpubl())
    for n in nettpubl:
        f.write(xml.xmlify_dbrow(n, xml.conv_colnames(cols), 'nettpubl') + "\n")
    f.write("</data>\n")
    f.close()

def write_ou_info(outfile):
    """Lager fil med informasjon om alle OU-er"""
    f = MinimumSizeWriter(outfile)
    f.min_size = 0
    f.write(xml.xml_hdr + "<data>\n")
    cols, ouer = _ext_cols(fs.info.list_ou(cereconf.DEFAULT_INSTITUSJONSNR))
    for o in ouer:
        sted = {}
        for fs_col, xml_attr in (
            ('faknr', 'fakultetnr'),
            ('instituttnr', 'instituttnr'),
            ('gruppenr', 'gruppenr'),
            ('stedakronym', 'akronym'),
            ('stedakronym', 'forkstednavn'),
            ('stednavn_bokmal', 'stednavn'),
            ('stedkode_konv', 'stedkode_konv'),
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
            ('emailadresse','EMAIL'),
            ('url', 'URL')):
            if o[fs_col]:               # Skip NULLs and empty strings
                komm.append({'kommtypekode': xml.escape_xml_attr(typekode),
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

def write_evukurs_info(outfile):
    """Skriv data om alle EVU-kurs"""
    f = MinimumSizeWriter(outfile)
    f.min_size = 1*KiB
    f.write(xml.xml_hdr + "<data>\n")
    cols, evukurs = _ext_cols(fs.evu.list_kurs())
    for ek in evukurs:
        f.write(xml.xmlify_dbrow(ek, xml.conv_colnames(cols), "evukurs") + "\n")
    f.write("</data>\n")
    f.close()
    # end write_evukurs_info

def write_role_info(outfile):
    """Skriv data om alle registrerte roller"""
    f = MinimumSizeWriter(outfile)
    f.min_size = KiB/4
    f.write(xml.xml_hdr + "<data>\n")
    cols, role = _ext_cols(fs.undervisning.list_alle_personroller())
    for r in role:
        f.write(xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'rolle') + "\n")
    f.write("</data>\n")
    f.close()

def write_undenh_metainfo(outfile):
    "Skriv metadata om undervisningsenheter for inneværende+neste semester."
    f = MinimumSizeWriter(outfile)
    f.min_size = 5*KiB
    f.write(xml.xml_hdr + "<undervenhet>\n")
    for semester in ('current', 'next'):
        cols, undenh = _ext_cols(fs.undervisning.list_undervisningenheter(sem=semester))
        for u in undenh:
            f.write(xml.xmlify_dbrow(u, xml.conv_colnames(cols), 'undenhet')
                    + "\n")
    f.write("</undervenhet>\n")
    f.close()

def write_undenh_student(outfile):
    """Skriv oversikt over personer oppmeldt til undervisningsenheter.
    Tar med data for alle undervisingsenheter i inneværende+neste
    semester."""
    f = MinimumSizeWriter(outfile)
    f.min_size = 5*KiB
    f.write(xml.xml_hdr + "<data>\n")
    for semester in ('current', 'next'):
        cols, undenh = _ext_cols(fs.undervisning.list_undervisningenheter(sem=semester))
        for u in undenh:
            u_attr = {}
            for k in ('institusjonsnr', 'emnekode', 'versjonskode',
                      'terminnr', 'terminkode', 'arstall'):
                u_attr[k] = u[k]
            student_cols, student = _ext_cols(fs.undervisning.list_studenter_underv_enhet(**u_attr))
            for s in student:
                s_attr = u_attr.copy()
                for k in ('fodselsdato', 'personnr'):
                    s_attr[k] = s[k]
                f.write(xml.xmlify_dbrow({}, (), 'student',
                                         extra_attr=s_attr)
                        + "\n")
    f.write("</data>\n")
    f.close()

def write_studprog_info(outfile):
    """Lager fil med informasjon om alle definerte studieprogrammer"""
    f = MinimumSizeWriter(outfile)
    f.min_size = 10*KiB
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.info.list_studieprogrammer())
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'studprog')
                + "\n")
    f.write("</data>\n")
    f.close()

def write_emne_info(outfile):
    """Lager fil med informasjon om alle definerte emner"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta =_ext_cols(fs.info.list_emner())
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'emne') + "\n")
    f.write("</data>\n")


def write_fnrupdate_info(outfile):
    """Lager fil med informasjon om alle fødselsnummerendringer"""
    stream = AtomicFileWriter(outfile, 'w')
    writer = xmlprinter.xmlprinter(stream,
                                   indent_level = 2,
                                   # Human-readable output
                                   data_mode = True,
                                   input_encoding = "latin1")
    writer.startDocument(encoding = "iso8859-1")

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    writer.startElement("data", {"source_system" : str(const.system_fs)})

    data = fs.person.list_fnr_endringer()
    for row in data:
        # Make the format resemble the corresponding FS output as close as
        # possible.
        attributes = { "type" : str(const.externalid_fodselsnr),
                       "new"  : "%06d%05d" % (row["fodselsdato_naverende"],
                                              row["personnr_naverende"]),
                       "old"  : "%06d%05d" % (row["fodselsdato_tidligere"],
                                              row["personnr_tidligere"]),
                       "date" : str(row["dato_foretatt"]),
                     }

        writer.emptyElement("external_id", attributes)
    # od

    writer.endElement("data")
    writer.endDocument()
    stream.close()
# end get_fnr_update_info

def write_misc_info(outfile, tag, func_name):
    """Lager fil med data fra gitt funksjon i access_FS"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(eval("fs.%s" % func_name)())
    for t in dta:
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), tag) + "\n")
    f.write("</data>\n")

def fix_float(row):
    for n in range(len(row)):
        if isinstance(row[n], float):
            row[n] = int(row[n])

def usage(exitcode=0):
    print """Usage: [options]

    --datadir DIR           Override the directory where all files should be
                            put. Not used if a file path is absolute.

    --studprog-file name: override studprog xml filename
    --personinfo-file: override person xml filename
    --roleinfo-file: override role xml filename
    --undenh-file: override 'topics' file
    --emneinfo-file: override emne info
    --student-undenh-file: override student on UE file
    --fnr-update-file: override fnr_update file
    --netpubl-file: override netpublication filename
    --misc-func func: name of function in access_FS to call
    --misc-file name: name of output file for misc-func
    --misc-tag tag: tag to use in misc-file
    --ou-file name: override ou xml filename
    --evukursinfo-file: override evu-kurs xml filename
    --db-user name: connect with given database username
    --db-service name: connect to given database
    -s: generate studprog xml file
    -o: generate ou xml (sted.xml) file
    -p: generate person file
    -r: generate role file
    -f: generate fnr_update file
    -e: generate emne info file
    -u: generate undervisningsenhet xml file
    -E: generate evu_kurs xml file
    -U: generate student on UE xml file
    -n: generate netpublication reservation xml file
    """
    sys.exit(exitcode)

def assert_connected(user="CEREBRUM", service="FSNMH.uio.no"):
    global fs
    if fs is None:
        DB_driver = getattr(cereconf, 'DB_DRIVER_ORACLE', 'cx_Oracle')
        db = database.connect(user=user, service=service, DB_driver=DB_driver)
        fs = FS(db)

def set_filepath(datadir, file):
    """Return the string of path to a file. If the given file path is relative,
    the datadir is used as a prefix, otherwise only the file path is returned.

    """
    if os.path.isabs(file):
        return file
    return os.path.join(datadir, file)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "fpsruUoeEn",
                                   ["personinfo-file=", "studprog-file=",
                                    "roleinfo-file=", "undenh-file=",
                                    "datadir=",
                                    "student-undenh-file=",
                                    "emneinfo-file=",
                                    "netpubl-file=",
                                    "evukursinfo-file=",
                                    "fnr-update-file=", "misc-func=",
                                    "misc-file=", "misc-tag=",
                                    "ou-file=", "db-user=", "db-service="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    datadir = '/cerebrum/var/cache/FS/'
    person_file = 'person.xml'
    studprog_file = 'studieprog.xml'
    ou_file = 'ou.xml'
    role_file = 'roles.xml'
    undervenh_file = 'underv_enhet.xml'
    emne_info_file = 'emner.xml'
    evu_kursinfo_file = 'evu_kursinfo.xml'
    fnr_update_file = 'fnr_update.xml'
    undenh_student_file = 'student_undenh.xml'
    nettpubl_file = 'nettpublisering.xml'

    db_user = None         # TBD: cereconf value?
    db_service = None      # TBD: cereconf value?
    for o, val in opts:
        if o in ('--emneinfo-file',):
            emne_info_file = val
        elif o in ('--personinfo-file',):
            person_file = val
        elif o in ('--datadir',):
            datadir = val
        elif o in ('--evukursinfo-file',):
            evu_kursinfo_file = val
        elif o in ('--studprog-file',):
            studprog_file = val
        elif o in ('--roleinfo-file',):
            role_file = val
        elif o in ('--undenh-file',):
            undervenh_file = val
        elif o in ('--student-undenh-file',):
            undenh_student_file = val
        elif o in ('--fnr-update-file',):
            fnr_update_file = val
        elif o in ('--ou-file',):
            ou_file = val
        elif o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val
    assert_connected(user=db_user, service=db_service)
    for o, val in opts:
        if o in ('-p',):
            write_person_info(set_filepath(datadir, person_file))
        elif o in ('-s',):
            write_studprog_info(set_filepath(datadir, studprog_file))
        elif o in ('-r',):
            write_role_info(set_filepath(datadir, role_file))
        elif o in ('-u',):
            write_undenh_metainfo(set_filepath(datadir, undervenh_file))
        elif o in ('-U',):
            write_undenh_student(set_filepath(datadir, undenh_student_file))
        elif o in ('-e',):
            write_emne_info(set_filepath(datadir, emne_info_file))
        elif o in ('-f',):
            write_fnrupdate_info(set_filepath(datadir, fnr_update_file))
        elif o in ('-o',):
            write_ou_info(set_filepath(datadir, ou_file))
        elif o in ('-E',):
            write_evukurs_info(set_filepath(datadir, evu_kursinfo_file))
        elif o in ('-n',):
            write_netpubl_info(set_filepath(datadir, nettpubl_file))
        # We want misc-* to be able to produce multiple file in one script-run
        elif o in ('--misc-func',):
            misc_func = val
        elif o in ('--misc-tag',):
            misc_tag = val
        elif o in ('--misc-file',):
            write_misc_info(set_filepath(val), misc_tag, misc_func)

if __name__ == '__main__':
    main()
