#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2012 University of Oslo, Norway
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
processing by other scripts. This job is for UiO's FS.

"""
from __future__ import unicode_literals
import os
import sys
import getopt

import cerebrum_path
import cereconf

from Cerebrum.Utils import XMLHelper
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.extlib import xmlprinter
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.utils.atomicfile import FileChangeTooBigError
from Cerebrum.Utils import Factory

xml = XMLHelper()
fs = None

logger = Factory.get_logger("cronjob")

def usage(exitcode=0):
    print """Usage: %(filename)s [options]

    %(doc)s

    Settings:

    --datadir           Override the directory where all files should be put.
                        Default: see cereconf.FS_DATA_DIR

                        Note that the datadir can be overriden by the file path
                        options, if these are absolute paths.

    --person-file       Override person xml filename. Default: persons.xml.

    --topics-file       Override topics xml filename. Default: topics.xml.

    --studprog-file     Override studprog xml filename. Default:
                        studieprogrammer.xml

    --emne-file         Override emne xml filename. Default: emner.xml.

    --regkort-file      Override regkort xml filename. Default: regkort.xml.

    --fnr-update-file   Override fnr-update xml filename. Default:
                        fnr_update.xml.

    --betalt-papir-file Override betalt-papir xml filename. Default:
                        betalt_papir.xml.

    --ou-file           Override ou xml filename. Default: ou.xml.

    --role-file         Override person role xml filename. Default: roles.xml.

    --netpubl-file      Override netpublication filename. Default:
                        nettpublisering.xml.

    --misc-func func:   Name of extra function in access_FS to call. Will be
                        called at the next given --misc-file.

    --misc-tag tag:     Tag to use in the next given --misc-file argument.

    --misc-file name:   Name of output file for previous set misc-func and
                        misc-tag arguments. Note that a relative filename could
                        be used for putting it into the set datadir.

    --pre-course-file name: Name of output file for pre course information.
                        Default: pre_course.xml.

    Action:

    -p              Generate person xml file

    -t              Generate topics xml file

    -e              Generate emne xml file

    -b              Generate betalt-papir xml file

    -f              Generate fnr xml update file

    -s              Generate studprog xml file

    -r              Generate regkort xml file

    -k              Generate person role xml file

    -o              Generate ou xml file

    -n              Generate netpublication reservation xml file

    --pre-course    Generate a pre-course xml file

    Other:

    -h, --help      Show this and quit.

    """ % {'filename': os.path.basename(sys.argv[0]),
           'doc': __doc__}
    sys.exit(exitcode)

def _ext_cols(db_rows):
    # TBD: One might consider letting xmlify_dbrow handle this
    cols = None
    if db_rows:
        cols = list(db_rows[0].keys())
    return cols, db_rows


def write_edu_info(outfile):
    """Lager en fil med undervisningsinformasjonen til alle studenter.

    For hver student, lister vi opp alle tilknytningene til undenh, undakt,
    evu, kursakt og kull.

    Hovedproblemet i denne metoden er at vi må bygge en enorm dict med all
    undervisningsinformasjon. Denne dicten bruker mye minne.

    Advarsel: vi gj�r ingen konsistenssjekk på at undervisningselementer nevnt
    i outfile vil faktisk finnes i andre filer genererert av dette
    skriptet. Mao. det er fullt mulig at en student S er registrert ved undakt
    U1, samtidig som U1 ikke er nevnt i undervisningsaktiveter.xml.

    fs.undervisning.list_studenter_alle_kull()      <- kull deltagelse
    fs.undervisning.list_studenter_alle_undenh()    <- undenh deltagelse
    fs.undervisning.list_studenter_alle_undakt()    <- undakt deltagelse
    fs.evu.list_studenter_alle_kursakt()            <- kursakt deltagelse
    fs.evu.list()                                   <- evu deltagelse
    """

    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")

    for triple in (("kull", None, fs.undervisning.list_studenter_alle_kull),
                   ("undenh", None, fs.undervisning.list_studenter_alle_undenh),
                   ("undakt", None, fs.undervisning.list_studenter_alle_undakt),
                   ("evu", ("fodselsdato",
                            "personnr",
                            "etterutdkurskode",
                            "kurstidsangivelsekode"),
                    fs.evu.list),
                   ("kursakt", None, fs.evu.list_studenter_alle_kursakt)):
        kind, fields, selector = triple
        logger.debug("Processing %s entries", kind)
        for row in selector():
            if fields is None:
                tmp_row = row
                keys = row.keys()
            else:
                tmp_row = dict((f, row[f]) for f in fields)
                keys = fields

            f.write(xml.xmlify_dbrow(tmp_row, keys, kind) + '\n')

    f.write("</data>\n")
    f.close()
# end write_edu_info


def write_forkurs_info(outfile):
    from mx.DateTime import now
    logger.info("Writing pre-course file to '{}'".format(outfile))
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    cols, course_attendants = _ext_cols(fs.forkurs.list())
    f.write(xml.xml_hdr + "<data>\n")
    for a in course_attendants:
        f.write('<regkort fodselsdato="{}" personnr="{}" dato_endring="{}" dato_opprettet="{}"/>\n'.format(a['fodselsdato'], a['personnr'], str(now()), str(now())))
        f.write('<emnestud fodselsdato="{}" personnr="{}" etternavn="{}" fornavn="{}" adrlin2_semadr="" postnr_semadr="" adrlin3_semadr="" adrlin2_hjemsted="" postnr_hjemsted="" adrlin3_hjemsted="" sprakkode_malform="NYNORSK" kjonn="X" studentnr_tildelt="{}" emnekode="FORGLU" versjonskode="1" terminkode="V�R" arstall="2016" telefonlandnr_mobil="{}" telefonnr_mobil="{}"/>\n'.format(
                    a['fodselsdato'],
                    a['personnr'],
                    a['etternavn'],
                    a['fornavn'],
                    a['studentnr_tildelt'],
                    a['telefonlandnr'],
                    a['telefonnr']
                ))
    f.write("</data>\n")
    f.close()


def write_person_info(outfile):
    """Lager fil med informasjon om alle personer registrert i FS som
    vi muligens også ønsker å ha med i Cerebrum.  En person kan
    forekomme flere ganger i filen."""

    # TBD: Burde vi cache alle data, slik at vi i stedet kan lage en
    # fil der all informasjon om en person er samlet under en egen
    # <person> tag?

    logger.info("Writing person info to '%s'" % outfile)

    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
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
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'aktiv') + "\n")

    # Aktive emnestudenter
    cols, students = _ext_cols(fs.student.list_aktiv_emnestud())
    for s in students:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'emnestud') + "\n")

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
    # En del EVU studenter vil v�re gitt av s�ket over

    cols, evustud = _ext_cols(fs.evu.list())
    for e in evustud:
        f.write(xml.xmlify_dbrow(e, xml.conv_colnames(cols), 'evu') + "\n")

    # Studenter i permisjon (ogs� dekket av GetStudinfOpptak)
    cols, permstud = _ext_cols(fs.student.list_permisjon())
    for p in permstud:
        f.write(xml.xmlify_dbrow(p, xml.conv_colnames(cols), 'permisjon') + "\n")

##
## STA har bestemt at personer med tilbud ikke skal ha tilgang til noen IT-tjenester
## inntil videre. Derfor slutter vi på nåværende tidspunkt å hente ut informasjon om
## disse. Ettersom det er usikkert om dette vil endre seg igjen i nær fremtid lar vi
## koden ligge for nå.
##
##    # Personer som har fått tilbud
##    cols, tilbudstud = _ext_cols(fs.student.list_tilbud())
##    for t in tilbudstud:
##        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'tilbud') + "\n")

    f.write("</data>\n")
    f.close()

def write_ou_info(outfile):
    """Lager fil med informasjon om alle OU-er"""
    logger.info("Writing OU info to '%s'" % outfile)

    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
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
    f.close()

def write_topic_info(outfile):
    """Lager fil med informasjon om alle XXX"""
    # TODO: Denne filen blir endret med det nye opplegget :-(
    logger.info("Writing topic info to '%s'" % outfile)
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    cols, topics = _ext_cols(fs.student.list_eksamensmeldinger())
    for t in topics:
        # The Oracle driver thinks the result of a union of ints is float
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'topic') + "\n")
    f.write("</data>\n")
    f.close()

def write_regkort_info(outfile):
    """Lager fil med informasjon om semesterregistreringer for
    innev�rende semester"""
    logger.info("Writing regkort info to '%s'" % outfile)
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    cols, regkort = _ext_cols(fs.student.list_semreg())
    for r in regkort:
        f.write(xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'regkort') + "\n")
    f.write("</data>\n")
    f.close()

def write_netpubl_info(outfile):
    """Lager fil med informasjon om status nettpublisering"""
    logger.info("Writing nettpubl info to '%s'" % outfile)
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    cols, nettpubl = _ext_cols(fs.person.list_status_nettpubl())
    for n in nettpubl:
        f.write(xml.xmlify_dbrow(n, xml.conv_colnames(cols), 'nettpubl') + "\n")
    f.write("</data>\n")
    f.close()

def write_studprog_info(outfile):
    """Lager fil med informasjon om alle definerte studieprogrammer"""
    logger.info("Writing studprog info to '%s'" % outfile)
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.info.list_studieprogrammer())
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'studprog') + "\n")
    f.write("</data>\n")
    f.close()

def write_emne_info(outfile):
    """Lager fil med informasjon om alle definerte emner"""
    logger.info("Writing emne info to '%s'" % outfile)
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.info.list_emner())
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'emne') + "\n")
    f.write("</data>\n")
    f.close()

def write_personrole_info(outfile):
    """Lager fil med informasjon om alle roller definer i FS.PERSONROLLE"""
    logger.info("Writing personrolle info to '%s'" % outfile)
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.undervisning.list_alle_personroller())
    for t in dta:
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'rolle') + "\n")
    f.write("</data>\n")
    f.close()

def write_misc_info(outfile, tag, func_name):
    """Lager fil med data fra gitt funksjon i access_FS"""
    logger.info("Writing misc info to '%s'" % outfile)
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    # It's still not foolproof, but hopefully much more sane than simply
    # eval'ing.
    components = func_name.split(".")
    next = fs
    for c in components:
        next = getattr(next, c)
    cols, dta = _ext_cols(next())
    for t in dta:
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), tag) + "\n")
    f.write("</data>\n")
    f.close()

def write_fnrupdate_info(outfile):
    """Lager fil med informasjon om alle f�dselsnummerendringer"""
    logger.info("Writing fnrupdate info to '%s'" % outfile)
    stream = AtomicFileWriter(outfile, 'w')
    writer = xmlprinter.xmlprinter(stream,
                                   indent_level = 2,
                                   # Human-readable output
                                   data_mode = True,
                                   input_encoding = "utf-8")
    writer.startDocument(encoding = "utf-8")

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    writer.startElement("data", {"source_system" : unicode(const.system_fs)})

    data = fs.person.list_fnr_endringer()
    for row in data:
        # Make the format resemble the corresponding FS output as close as
        # possible.
        attributes = { "type" : unicode(const.externalid_fodselsnr),
                       "new"  : "%06d%05d" % (row["fodselsdato_naverende"],
                                              row["personnr_naverende"]),
                       "old"  : "%06d%05d" % (row["fodselsdato_tidligere"],
                                              row["personnr_tidligere"]),
                       "date" : unicode(row["dato_foretatt"]),
                     }

        writer.emptyElement("external_id", attributes)
    # od

    writer.endElement("data")
    writer.endDocument()
    stream.close()
# end get_fnr_update_info



def write_betalt_papir_info(outfile):
    """Lager fil med informasjon om alle som enten har fritak fra å
    betale kopiavgift eller har betalt kopiavgiften"""

    logger.info("Writing betaltpapir info to '%s'" % outfile)
    f = SimilarSizeWriter(outfile, "w")
    f.max_pct_change = 50
    f.write(xml.xml_hdr + "<data>\n")
    cols, dta = _ext_cols(fs.betaling.list_kopiavgift_data(kun_fritak=False, semreg=True))
    for t in dta:
        fix_float(t)
        f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'betalt') + "\n")
    f.write("</data>\n")
    f.close()

def fix_float(row):
    for n in range(len(row)):
        if isinstance(row[n], float):
            row[n] = int(row[n])

def set_filepath(datadir, file):
    """Return the string of path to a file. If the given file path is relative,
    the datadir is used as a prefix, otherwise only the file path is returned.

    """
    if os.path.isabs(file):
        return file
    return os.path.join(datadir, file)

def main():
    logger.info("Starting import from FS")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "ptsroefbknd",
                                   ["datadir=",
                                    "person-file=", "topics-file=",
                                    "studprog-file=", "regkort-file=",
                                    'emne-file=', "ou-file=",
                                    'fnr-update-file=', 'betalt-papir-file=',
                                    'role-file=', 'netpubl-file=',
                                    'edu-file=',
                                    "misc-func=", "misc-file=", "misc-tag=",
                                    "pre-course", "pre-course-file="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    datadir = cereconf.FS_DATA_DIR
    person_file = 'persons.xml'
    topics_file = 'topics.xml'
    studprog_file = 'studieprogrammer.xml'
    regkort_file = 'regkort.xml'
    emne_file = 'emner.xml'
    ou_file = 'ou.xml'
    role_file = 'roles.xml'
    fnrupdate_file = 'fnr_update.xml'
    betalt_papir_file = 'betalt_papir.xml'
    netpubl_file = 'nettpublisering.xml'
    edu_file = 'edu_info.xml'
    pre_course_file = 'pre_course.xml'

    for o, val in opts:
        if o in ('--datadir',):
            datadir = val
        elif o in ('--person-file',):
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
        elif o in('--netpubl-file',):
            netpubl_file = val
        elif o in ('--edu-file',):
            edu_file = val
        elif o in ('--pre-course-file',):
            pre_course_file = val

    global fs
    fs = make_fs()

    for o, val in opts:
        try:
            if o in ('-p',):
                write_person_info(set_filepath(datadir, person_file))
            elif o in ('-t',):
                write_topic_info(set_filepath(datadir, topics_file))
            elif o in ('-b',):
                write_betalt_papir_info(set_filepath(datadir,
                                                     betalt_papir_file))
            elif o in ('-s',):
                write_studprog_info(set_filepath(datadir, studprog_file))
            elif o in ('-f',):
                write_fnrupdate_info(set_filepath(datadir, fnrupdate_file))
            elif o in ('-e',):
                write_emne_info(set_filepath(datadir, emne_file))
            elif o in ('-r',):
                write_regkort_info(set_filepath(datadir, regkort_file))
            elif o in ('-o',):
                write_ou_info(set_filepath(datadir, ou_file))
            elif o in ('-k',):
                write_personrole_info(set_filepath(datadir, role_file))
            elif o in ('-n',):
                write_netpubl_info(set_filepath(datadir, netpubl_file))
            elif o in ('-d',):
                write_edu_info(set_filepath(datadir, edu_file))
            elif o in ('--pre-course',):
                write_forkurs_info(set_filepath(datadir, pre_course_file))
            # We want misc-* to be able to produce multiple file in one script-run
            elif o in ('--misc-func',):
                misc_func = val
            elif o in ('--misc-tag',):
                misc_tag = val
            elif o in ('--misc-file',):
                write_misc_info(set_filepath(datadir, val), misc_tag, misc_func)
        except FileChangeTooBigError as msg:
            logger.error("Manual intervention required: %s", msg)

    logger.info("Import from FS done")


if __name__ == '__main__':
    main()

