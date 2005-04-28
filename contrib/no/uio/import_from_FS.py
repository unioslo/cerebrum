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

import cerebrum_path

import re
import os
import sys
import getopt
import cereconf

from Cerebrum import Database
from Cerebrum import Errors
from Cerebrum.Utils import XMLHelper
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.extlib import xmlprinter
from Cerebrum.Utils import AtomicFileWriter
from Cerebrum.Utils import Factory

default_person_file = "/cerebrum/dumps/FS/persons.xml"
default_emne_file = "/cerebrum/dumps/FS/emner.xml"
default_role_file = "/cerebrum/dumps/FS/roles.xml"
default_topics_file = "/cerebrum/dumps/FS/topics.xml"
default_studieprogram_file = "/cerebrum/dumps/FS/studieprogrammer.xml"
default_regkort_file = "/cerebrum/dumps/FS/regkort.xml"
default_ou_file = "/cerebrum/dumps/FS/ou.xml"
default_fnrupdate_file = "/cerebrum/dumps/FS/fnr_udpate.xml"
default_betalt_papir_file = "/cerebrum/dumps/FS/betalt_papir.xml"

xml = XMLHelper()
fs = None

def _ext_cols(db_rows):
    # TBD: One might consider letting xmlify_dbrow handle this
    cols = None
    if db_rows:
        cols = list(db_rows[0]._keys())
    return cols, db_rows

def write_person_info(outfile):
    """Lager fil med informasjon om alle personer registrert i FS som
    vi muligens også ønsker å ha med i Cerebrum.  En person kan
    forekomme flere ganger i filen."""

    # TBD: Burde vi cache alle data, slik at vi i stedet kan lage en
    # fil der all informasjon om en person er samlet under en egen
    # <person> tag?
    
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    # Fagpersoner
    cols, fagpersoner = _ext_cols(fs.undervisning.list_fagperson_semester())
    for p in fagpersoner:
        f.write(xml.xmlify_dbrow(p, xml.conv_colnames(cols), 'fagperson') + "\n")

    # Studenter med opptak, privatister (=opptak i studiepgraommet
    # privatist) og Alumni
    cols, students = _ext_cols(fs.student.list())
    for s in students:
	# The Oracle driver thinks the result of a union of ints is float
        fix_float(s)
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'opptak') + "\n")
    # Studenter med alumni opptak til et studieprogram
    cols, students = _ext_cols(fs.alumni.list())
    for s in students:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'alumni') + "\n")

    # Privatister, privatistopptak til studieprogram eller emne-privatist
    cols, students = _ext_cols(fs.student.list_privatist())
    for s in students:
        fix_float(s)
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'privatist_studieprogram') + "\n")
    cols, students = _ext_cols(fs.student.list_privatist_emne())
    for s in students:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'privatist_emne') + "\n")

    # Aktive studenter
    cols, students = _ext_cols(fs.student.list_aktiv())
    for s in students:
        # The Oracle driver thinks the result of a union of ints is float
        fix_float(s)
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'aktiv') + "\n")

    # Semester-registrering
    cols, students = _ext_cols(fs.student.list_semreg())
    for s in students:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'regkort') + "\n")

    # Eksamensmeldinger
    cols, students = _ext_cols(fs.student.list_eksamensmeldinger())
    for s in students:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'eksamen') + "\n")

    # Drgradsstudenter med opptak
    cols, drstudents = _ext_cols(fs.student.list_drgrad())
    for d in drstudents:
        f.write(xml.xmlify_dbrow(d, xml.conv_colnames(cols), 'drgrad') + "\n")

    # EVU students
    # En del EVU studenter vil være gitt av søket over

    cols, evustud = _ext_cols(fs.evu.list())
    for e in evustud:
        f.write(xml.xmlify_dbrow(e, xml.conv_colnames(cols), 'evu') + "\n")

    # Studenter i permisjon (også dekket av GetStudinfOpptak)
    cols, permstud = _ext_cols(fs.student.list_permisjon())
    for p in permstud:
        f.write(xml.xmlify_dbrow(p, xml.conv_colnames(cols), 'permisjon') + "\n")

    # Personer som har fått tilbud
    cols, tilbudstud = _ext_cols(fs.student.list_tilbud())
    for t in tilbudstud:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'tilbud') + "\n")
    
    f.write("</data>\n")

def write_ou_info(outfile):
    """Lager fil med informasjon om alle OU-er"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, ouer = _ext_cols(fs.info.list_ou(cereconf.DEFAULT_INSTITUSJONSNR))  # TODO
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
            ('faxnr', 'FAX')):
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

def write_topic_info(outfile):
    """Lager fil med informasjon om alle XXX"""
    # TODO: Denne filen blir endret med det nye opplegget :-(
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, topics = _ext_cols(fs.student.list_eksamensmeldinger())
    for t in topics:
        # The Oracle driver thinks the result of a union of ints is float
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'topic') + "\n")
    f.write("</data>\n")

def write_regkort_info(outfile):
    """Lager fil med informasjon om semesterregistreringer for
    inneværende semester"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, regkort = _ext_cols(fs.student.list_semreg())
    for r in regkort:
        f.write(xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'regkort') + "\n")
    f.write("</data>\n")

def write_studprog_info(outfile):
    """Lager fil med informasjon om alle definerte studieprogrammer"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.info.list_studieprogrammer())
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'studprog') + "\n")
    f.write("</data>\n")

def write_emne_info(outfile):
    """Lager fil med informasjon om alle definerte emner"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.info.list_emner())
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'emne') + "\n")
    f.write("</data>\n")

def write_personrole_info(outfile):
    """Lager fil med informasjon om alle roller definer i FS.PERSONROLLE"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.undervisning.list_alle_personroller())
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'rolle') + "\n")
    f.write("</data>\n")

def write_misc_info(outfile, tag, func_name):
    """Lager fil med data fra gitt funksjon i access_FS"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(eval("fs.%s" % func_name)())
    for t in dta:
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), tag) + "\n")
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



def write_betalt_papir_info(outfile):
    """Lager fil med informasjon om alle som har betalt papirpenger"""
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.betaling.list_betalt_papiravgift())
    for t in dta:
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'betalt') + "\n")
    f.write("</data>\n")

def fix_float(row):
    for n in range(len(row)):
        if isinstance(row[n], float):
            row[n] = int(row[n])

def usage(exitcode=0):
    print """Usage: [options]
    --person-file name: override person xml filename
    --topics-file name: override topics xml filename
    --studprog-file name: override studprog xml filename
    --emne-file name: override emne xml filename
    --regkort-file name: override regkort xml filename
    --fnr-update-file name: override fnr-update xml filename
    --betalt-papir-file name: override betalt-papir xml filename
    --misc-func func: name of function in access_FS to call
    --misc-file name: name of output file for misc-func
    --misc-tag tag: tag to use in misc-file
    --ou-file name: override ou xml filename
    --db-user name: connect with given database username
    --db-service name: connect to given database
    --role-file name: override person role xml filename
    -p: generate person xml file
    -t: generate topics xml file
    -e: generate emne xml file
    -b: generate betalt-papir xml file
    -f: generate fnr xml update file
    -s: generate studprog xml file
    -r: generate regkort xml file
    -k: generate person role xml file
    -o: generate ou xml file

    """
    sys.exit(exitcode)

def assert_connected(user="ureg2000", service="FSPROD.uio.no"):
    global fs
    if fs is None:
        db = Database.connect(user=user, service=service,
                              DB_driver='Oracle')
        fs = FS(db)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ptsroefbk",
                                   ["person-file=", "topics-file=",
                                    "studprog-file=", "regkort-file=",
                                    'emne-file=', "ou-file=", "db-user=",
                                    'fnr-update-file=', 'betalt-papir-file=',
				    'role-file=', "db-service=", "misc-func=", 
                                    "misc-file=", "misc-tag="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    person_file = default_person_file
    topics_file = default_topics_file
    studprog_file = default_studieprogram_file
    regkort_file = default_regkort_file
    emne_file = default_emne_file
    ou_file = default_ou_file
    role_file = default_role_file
    fnrupdate_file = default_fnrupdate_file
    betalt_papir_file = default_betalt_papir_file
    db_user = None         # TBD: cereconf value?
    db_service = None      # TBD: cereconf value?
    for o, val in opts:
        if o in ('--person-file',):
            person_file = val
        elif o in ('--topics-file',):
            topics_file = val
        elif o in ('--emne-file',):
            emne_file = val
        elif o in ('--studprog-file',):
            studprog_file = val
        elif o in ('--regkort-file',):
            regkort_file = val
        elif o in ('--ou-file',):
            ou_file = val
        elif o in ('--fnr-update-file',):
            fnrupdate_file = val
        elif o in ('--betalt-papir-file',):
            betalt_papir_file = val
	elif o in('--role-file',):
	    role_file = val
        elif o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val
    assert_connected(user=db_user, service=db_service)
    for o, val in opts:
        if o in ('-p',):
            write_person_info(person_file)
        elif o in ('-t',):
            write_topic_info(topics_file)
        elif o in ('-b',):
            write_betalt_papir_info(betalt_papir_file)
        elif o in ('-s',):
            write_studprog_info(studprog_file)
        elif o in ('-f',):
            write_fnrupdate_info(fnrupdate_file)
        elif o in ('-e',):
            write_emne_info(emne_file)
        elif o in ('-r',):
            write_regkort_info(regkort_file)
        elif o in ('-o',):
            write_ou_info(ou_file)
	elif o in ('-k',):
	    write_personrole_info(role_file)
        # We want misc-* to be able to produce multiple file in one script-run
        elif o in ('--misc-func',):
            misc_func = val
        elif o in ('--misc-tag',):
            misc_tag = val
        elif o in ('--misc-file',):
            write_misc_info(val, misc_tag, misc_func)

if __name__ == '__main__':
    main()

# arch-tag: b636897f-ceaf-4c53-bb7c-71652b7140e0
