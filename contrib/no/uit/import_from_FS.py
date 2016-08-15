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

import os
import sys
import getopt

import cerebrum_path
import cereconf

from Cerebrum import Database
from Cerebrum.extlib import xmlprinter
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.atomicfile import MinimumSizeWriter
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.modules.no.uit.access_FS_obsolete import UiTFS
from Cerebrum.modules.no.uit.access_FS import FS
from Cerebrum.modules.no.uit import access_FS
from Cerebrum.Utils import Factory

dumpdir = os.path.join(cereconf.DUMPDIR,"FS")
default_person_file = os.path.join(dumpdir,'person.xml')
default_role_file = os.path.join(dumpdir,'roles.xml')
default_undvenh_file = os.path.join(dumpdir,'underv_enhet.xml')
default_undenh_student_file = os.path.join(dumpdir,'student_undenh.xml')
default_studieprogram_file = os.path.join(dumpdir,'studieprog.xml')
default_ou_file = os.path.join(dumpdir,'ou.xml')
default_emne_file = os.path.join(dumpdir,'emner.xml')
default_fnr_update_file = os.path.join(dumpdir,'fnr_update.xml')
default_undakt_file = os.path.join(dumpdir,'undakt.xml')
default_undakt_student_file = os.path.join(dumpdir,'student_undakt.xml')

xml = XMLHelper()
fs = uitfs = None

KiB = 1024
MiB = KiB**2


def _ext_cols(db_rows):
    # TBD: One might consider letting xmlify_dbrow handle this
    cols = None
    if db_rows:
        cols = list(db_rows[0].keys())
    return cols, db_rows


def write_uit_person_info(outfile):
    f = MinimumSizeWriter(outfile)
    f.min_size = 500*KiB
    f.write(xml.xml_hdr + "<data>\n")

    # Studenter med opptak
    cols, students = _ext_cols(fs.student.list())
    for s in students:
    # The Oracle driver thinks the result of a union of ints is float
        fix_float(s)
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'opptak') + "\n")

    # Fagpersoner
    cols, fagpersoner = _ext_cols(fs.undervisning.list_fagperson_semester())
    for p in fagpersoner:
        f.write(xml.xmlify_dbrow(p, xml.conv_colnames(cols), 'fagperson') + "\n")

    #Aktive ordinære studenter ved Uit
    cols, uitaktiv = uitfs.GetAktive()
    for a in uitaktiv:
        fix_float(a)
        f.write(xml.xmlify_dbrow(a,xml.conv_colnames(cols),'aktiv') + "\n")

    #Privatister ved Uit
    cols, uitprivatist = uitfs.GetPrivatist()
    for p in uitprivatist:
        f.write(xml.xmlify_dbrow(p,xml.conv_colnames(cols),'privatist_studieprogram') + "\n")

    #Personer som har tilbud om opptak ved Uit
    cols, uittilbud = uitfs.GetTilbud(cereconf.DEFAULT_INSTITUSJONSNR)
    for t in uittilbud:
        f.write(xml.xmlify_dbrow(t,xml.conv_colnames(cols),'tilbud') + "\n")

    #Personer som har drgrad opptak ved Uit
    cols,uitdrgrad = _ext_cols(fs.student.list_drgrad())
    for p in uitdrgrad:
        f.write(xml.xmlify_dbrow(p,xml.conv_colnames(cols),'drgrad') + "\n")
    
    #EVU-studenter ved Uit
    cols, uitevu = uitfs.GetDeltaker()
    for e in uitevu:
        f.write(xml.xmlify_dbrow(e,xml.conv_colnames(cols),'evu') + "\n")

    f.write("</data>\n")
    f.close()

def write_ou_info(outfile):
    """Lager fil med informasjon om alle OU-er"""
    f = MinimumSizeWriter(outfile)
    f.min_size = 5*KiB
    f.write(xml.xml_hdr + "<data>\n")
    cols, ouer = uitfs.GetAlleOUer(cereconf.DEFAULT_INSTITUSJONSNR)  # TODO
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

def write_role_info(outfile):
    f = MinimumSizeWriter(outfile)
    f.min_size = 1
    f.write(xml.xml_hdr + "<data>\n")
    cols, role = uitfs.GetAllePersonRoller(cereconf.DEFAULT_INSTITUSJONSNR)
    for r in role:
        f.write(xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'rolle') + "\n")
    f.write("</data>\n")
    f.close()


def  write_undakt_info(outfile):
    f = MinimumSizeWriter(outfile)
    f.min_size = 1
    f.write(xml.xml_hdr + "<data>\n")
    
    this, next = access_FS.get_semester(uppercase=True)    
    for semester in (this,next):
        cols,akt = _ext_cols(fs.undervisning.list_aktiviteter(*semester))
        for r in akt:
            f.write(xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'undakt') + "\n")
    f.write("</data>\n")    
    f.close()
    

def write_undenh_metainfo(outfile):
    "Skriv metadata om undervisningsenheter for inneværende+neste semester."
    f = MinimumSizeWriter(outfile)
    f.min_size = 150*KiB
    f.write(xml.xml_hdr + "<undervenhet>\n")
    for semester in access_FS.get_semester(uppercase=True):
        semester_aar, semester_sem = semester
        cols,undenh = _ext_cols(fs.undervisning.list_undervisningenheter(year=semester_aar, sem=semester_sem))
        for u in undenh:
            f.write(xml.xmlify_dbrow(u,xml.conv_colnames(cols),"undenhet") + '\n')
    f.write("</undervenhet>\n")
    f.close()

    

def write_undenh_student(outfile):
    """Skriv oversikt over personer oppmeldt til undervisningsenheter.

    Tar med data for alle undervisingsenheter i inneværende+neste
    semester."""
    f = MinimumSizeWriter(outfile)

    f.min_size = 600*KiB
    f.write(xml.xml_hdr + "<data>\n")
    
    for semester in access_FS.get_semester(uppercase=True):
        semester_aar, semester_sem = semester
        undenh = fs.undervisning.list_undervisningenheter(year=semester_aar, sem=semester_sem)
        for u in undenh:
            u_attr = {}
            for k in ['institusjonsnr', 'emnekode', 'versjonskode',
                      'terminkode', 'arstall', 'terminnr']:
                u_attr[k] = u[k]
            student = fs.undervisning.list_studenter_underv_enhet(**u_attr)
            s_attr = {}
            for s in student:
                s_attr = u_attr.copy()
                for k in ('fodselsdato', 'personnr'):
                    s_attr[k] = int(s[k])
                f.write(xml.xmlify_dbrow({}, (), 'student',
                                         extra_attr=s_attr)
                        + "\n")

    f.write("</data>\n")
    f.close()
    
    
    
def write_undakt_student(outfile):
    """Skriv oversikt over personer oppmeldt til undervisningsaktivityeter.

    Tar med data for alle undervisingsaktiveter i inneværende+neste
    semester."""
    f = MinimumSizeWriter(outfile)

    f.min_size = 2*KiB
    f.write(xml.xml_hdr + "<data>\n")
    
    this, next = access_FS.get_semester(uppercase=True)    
    for semester in (this,next):
        cols,akt = _ext_cols(fs.undervisning.list_aktiviteter(*semester))
        for a in akt:
            a_attr = {}
            # oversett kolonnenavn fra list_aktiviteter til parameternavn i list_aktivitet()
            trans = (('institusjonsnr','Instnr'), 
                    ('emnekode','emnekode'),
                    ('versjonskode','versjon'),
                    ('terminkode','termk'),
                    ('arstall','aar'),
                    ('terminnr','termnr'),
                    ('aktivitetkode','aktkode'))
            for k1,k2 in trans:
                a_attr[k2] = a[k1]
            student_cols, student = _ext_cols(fs.undervisning.list_aktivitet(**a_attr))
            for s in student:
                #s_attr = a_attr.copy()
                s_attr = dict()
                for k1,k2 in trans:
                    s_attr[k1]=a[k1]
                for k in ('fodselsdato', 'personnr'):
                    s_attr[k] = s[k]
                f.write(xml.xmlify_dbrow({}, (), 'undakt', extra_attr=s_attr)
                        + "\n")
    f.write("</data>\n")
    f.close()

def write_studprog_info(outfile):
    """Lager fil med informasjon om alle definerte studieprogrammer"""
    f = MinimumSizeWriter(outfile)
    f.min_size = 50*KiB
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = uitfs.GetStudieproginf()
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'studprog')
                + "\n")

    f.write("</data>\n")
    f.close()

def write_emne_info(outfile):
    """Lager fil med informasjon om alle definerte emner"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = uitfs.GetAlleEmner()
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

    junk, data = uitfs.GetFnrEndringer()
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

def fix_float(row):
    for n in range(len(row)):
        if isinstance(row[n], float):
            row[n] = int(row[n])

def usage(exitcode=0):
    print """Usage: [options]
    --studprog-file name: override studprog xml filename
    --uit-personinfo-file: override uit person xml filename
    --uit-roleinfo-file: override role xml filename
    --uit-undenh-file: override 'topics' file
    --uit-emneinfo-file: override emne info
    --uit-student-undenh-file: override student on UE file
    --uit-undakt-file: override undervisningsaktiveter on UE file
    --uit-student-undakt-file: override student on UE file
    --uit-fnr-update-file: override fnr_update file
    --ou-file name: override ou xml filename
    --db-user name: connect with given database username
    --db-service name: connect to given database
    -s: generate studprog xml file
    -o: generate ou xml (sted.xml) file
    -p: generate person file
    -r: generate role file
    -f: generate fnr_update file
    -e: generate emne info file
    -u: generate undervisningsenhet xml file
    -U: generate student on UE xml file
    -x: generate undervisningsaktivitet xml file
    -X: generate student on UA xml file
    """
    sys.exit(exitcode)

def assert_connected(user="CEREBRUM", service="FSUIT.uio.no"):
    global uitfs, fs, nofs
    if fs is None or uitfs is None:
        db = Database.connect(user=user, service=service,
                              DB_driver='Oracle')
        uitfs = UiTFS(db)
        fs = FS(db)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "fpsruUoexX",
                                   ["uit-personinfo-file=", "studprog-file=", 
                                    "uit-roleinfo-file=", "uit-undenh-file=",
                                    "uit-student-undenh-file=",
                                    "uit-emneinfo-file=",
                                    "uit-fnr-update-file=",
                                    "uit-undakt-file=",
                                    "uit-student-undakt-file=",
                                    "ou-file=", "db-user=", "db-service="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    person_file = default_person_file
    studprog_file = default_studieprogram_file
    ou_file = default_ou_file
    role_file = default_role_file
    undervenh_file = default_undvenh_file
    emne_info_file = default_emne_file 
    fnr_update_file = default_fnr_update_file
    undenh_student_file = default_undenh_student_file
    undakt_file = default_undakt_file
    undakt_student_file = default_undakt_student_file
    db_user = None         # TBD: cereconf value?
    db_service = None      # TBD: cereconf value?
    for o, val in opts:
        if o in ('--uit-personinfo-file',):
            person_file = val
        elif o in ('--studprog-file',):
            studprog_file = val
        elif o in ('--uit-roleinfo-file',):
            role_file = val
        elif o in ('--uit-undenh-file',):
            undervenh_file = val
        elif o in ('--uit-student-undenh-file',):
            undenh_student_file = val
        elif o in ('--uit-undakt-file',):
            undakt_file = val
        elif o in ('--uit-student-undakt-file',):
            undakt_student_file = val
        elif o in ('--uit-undakt-file',):
            undakt_file = val
        elif o in ('--uit-fnr-update-file',):
            fnr_update_file = val
        elif o in ('--uit-emneinfo-file',):
            emne_info_file = val
        elif o in ('--ou-file',):
            ou_file = val
        elif o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val
    assert_connected(user=db_user, service=db_service)
    for o, val in opts:
        if o in ('-p',):
            write_uit_person_info(person_file)
        elif o in ('-s',):
            write_studprog_info(studprog_file)
        elif o in ('-r',):
            write_role_info(role_file)
        elif o in ('-u',):
            write_undenh_metainfo(undervenh_file)
        elif o in ('-U',):
            write_undenh_student(undenh_student_file)
        elif o in ('-e',):
            write_emne_info(emne_info_file)
        elif o in ('-f',):
            write_fnrupdate_info(fnr_update_file)
        elif o in ('-o',):
            write_ou_info(ou_file)
        elif o in ('-x',):
            write_undakt_info(undakt_file)
        elif o in ('-X',):
            write_undakt_student(undakt_student_file)


if __name__ == '__main__':
    main()
