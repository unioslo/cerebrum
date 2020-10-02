# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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

This is the general class intended to be used by all the instances in addition
to their own specific differences.

"""
from __future__ import unicode_literals

import logging
import os
from functools import reduce

import six

from Cerebrum.Utils import Factory
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules.xmlutils.xml_helper import XMLHelper
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.atomicfile import SimilarSizeWriter

XML_ENCODING = 'utf-8'

logger = logging.getLogger(__name__)
xml = XMLHelper(encoding=XML_ENCODING)


class ImportFromFs(object):
    def __init__(self, fs):
        self.fs = fs

    @staticmethod
    def _ext_cols(db_rows):
        # TBD: One might consider letting xmlify_dbrow handle this
        cols = None
        if db_rows:
            cols = list(db_rows[0].keys())
        return cols, db_rows

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
            self.fix_float(s)
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

        # Aktive fagpersoner
        cols, fagperson = self._ext_cols(
            self.fs.undervisning.list_fagperson_semester())
        for p in fagperson:
            f.write(
                xml.xmlify_dbrow(
                    p, xml.conv_colnames(cols),
                    'fagperson') + "\n")
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
                    ('emailadresse', 'EMAIL'),
                    ('url', 'URL')
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

    def write_netpubl_info(self, netpubl_file):
        """Lager fil med informasjon om status nettpublisering"""
        logger.info("Writing nettpubl info to '%s'", netpubl_file)
        f = SimilarSizeWriter(netpubl_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, nettpubl = self._ext_cols(self.fs.person.list_status_nettpubl())
        for n in nettpubl:
            f.write(xml.xmlify_dbrow(n,
                                     xml.conv_colnames(cols),
                                     'nettpubl') + "\n")
        f.write("</data>\n")
        f.close()

    def write_emne_info(self, emne_info_file):
        """Lager fil med informasjon om alle definerte emner"""
        logger.info("Writing emne info to '%s'", emne_info_file)
        f = SimilarSizeWriter(emne_info_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, dta = self._ext_cols(self.fs.info.list_emner())
        for t in dta:
            f.write(
                xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'emne') + "\n")
        f.write("</data>\n")
        f.close()

    def write_role_info(self, role_file):
        """Lager fil med informasjon om alle roller definer i FS.PERSONROLLE"""
        logger.info("Writing role info to '%s'", role_file)
        f = SimilarSizeWriter(role_file, mode='w', encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, role = self._ext_cols(
            self.fs.undervisning.list_alle_personroller())
        for r in role:
            f.write(
                xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'rolle') + "\n")
        f.write("</data>\n")
        f.close()

    def write_studprog_info(self, studprog_file):
        """Lager fil med informasjon om alle definerte studieprogrammer"""
        logger.info("Writing studprog info to '%s'", studprog_file)
        f = SimilarSizeWriter(studprog_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, dta = self._ext_cols(self.fs.info.list_studieprogrammer())
        for t in dta:
            f.write(
                xml.xmlify_dbrow(
                    t, xml.conv_colnames(cols), 'studprog') + "\n")
        f.write("</data>\n")
        f.close()

    def write_undenh_metainfo(self, undervenh_file):
        """Skriv metadata om undervisningsenheter for inneværende+neste
        semester."""
        logger.info("Writing undenh_meta info to '%s'", undervenh_file)
        f = SimilarSizeWriter(undervenh_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<undervenhet>\n")
        for semester in ('current', 'next'):
            cols, undenh = self._ext_cols(
                self.fs.undervisning.list_undervisningenheter(sem=semester))
            for u in undenh:
                f.write(
                    xml.xmlify_dbrow(u, xml.conv_colnames(cols), 'undenhet') +
                    "\n")
        f.write("</undervenhet>\n")
        f.close()

    def write_evukurs_info(self, evu_kursinfo_file):
        """Skriv data om alle EVU-kurs (vi trenger dette bl.a. for å bygge
        EVU-delen av CF)."""
        logger.info("Writing evukurs info to '%s'", evu_kursinfo_file)
        f = SimilarSizeWriter(evu_kursinfo_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, evukurs = self._ext_cols(self.fs.evu.list_kurs())
        for ek in evukurs:
            f.write(
                xml.xmlify_dbrow(
                    ek, xml.conv_colnames(cols), "evukurs") + "\n")
        f.write("</data>\n")
        f.close()

    def write_undenh_student(self, undenh_student_file):
        """Skriv oversikt over personer oppmeldt til undervisningsenheter.
        Tar med data for alle undervisingsenheter i inneværende+neste
        semester."""
        logger.info("Writing undenh_student info to '%s'",
                    undenh_student_file)
        f = SimilarSizeWriter(undenh_student_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        for semester in ('current', 'next'):
            cols, undenh = self._ext_cols(
                self.fs.undervisning.list_undervisningenheter(sem=semester))
            for u in undenh:
                u_attr = {}
                for k in ('institusjonsnr', 'emnekode', 'versjonskode',
                          'terminnr', 'terminkode', 'arstall'):
                    u_attr[k] = u[k]
                student_cols, student = self._ext_cols(
                    self.fs.undervisning.list_studenter_underv_enhet(**u_attr))
                for s in student:
                    s_attr = u_attr.copy()
                    for k in ('fodselsdato', 'personnr'):
                        s_attr[k] = s[k]
                    f.write(xml.xmlify_dbrow({}, (), 'student',
                                             extra_attr=s_attr) + "\n")
        f.write("</data>\n")
        f.close()

    def write_fnrupdate_info(self, fnr_update_file):
        """Lager fil med informasjon om alle fødselsnummerendringer"""
        logger.info("Writing fnrupdate info to '%s'", fnr_update_file)
        stream = AtomicStreamRecoder(fnr_update_file, mode='w',
                                     encoding=XML_ENCODING)
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level=2,
                                       data_mode=True)
        writer.startDocument(encoding=XML_ENCODING)

        db = Factory.get("Database")()
        const = Factory.get("Constants")(db)

        writer.startElement("data",
                            {"source_system": six.text_type(const.system_fs)})

        data = self.fs.person.list_fnr_endringer()
        for row in data:
            # Make the format resemble the corresponding FS output as close as
            # possible.
            attributes = {
                "type": six.text_type(const.externalid_fodselsnr),
                "new": "%06d%05d" % (row["fodselsdato_naverende"],
                                     row["personnr_naverende"]),
                "old": "%06d%05d" % (row["fodselsdato_tidligere"],
                                     row["personnr_tidligere"]),
                "date": six.text_type(row["dato_foretatt"]),
            }
            writer.emptyElement("external_id", attributes)

        writer.endElement("data")
        writer.endDocument()
        stream.close()

    def write_misc_info(self, misc_file, tag, func_name):
        """Lager fil med data fra gitt funksjon i access_FS"""
        logger.info("Writing misc info to '%s'", misc_file)
        f = SimilarSizeWriter(misc_file, mode='w', encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        func = reduce(
            lambda obj, attr: getattr(obj, attr),
            func_name.split('.'), self.fs)
        cols, dta = self._ext_cols(func())
        for t in dta:
            self.fix_float(t)
            f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), tag) + "\n")
        f.write("</data>\n")
        f.close()

    def write_topic_info(self, topics_file):
        """Lager fil med informasjon om alle XXX"""
        # TODO: Denne filen blir endret med det nye opplegget :-(
        logger.info("Writing topic info to '%s'", topics_file)
        f = SimilarSizeWriter(topics_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, topics = self._ext_cols(self.fs.student.list_eksamensmeldinger())
        for t in topics:
            # The Oracle driver thinks the result of a union of ints is float
            self.fix_float(t)
            f.write(
                xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'topic') + "\n")
        f.write("</data>\n")
        f.close()

    def write_forkurs_info(self, pre_course_file):
        from mx.DateTime import now
        logger.info("Writing pre-course file to '%s'", pre_course_file)
        f = SimilarSizeWriter(pre_course_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        cols, course_attendants = self._ext_cols(self.fs.forkurs.list())
        f.write(xml.xml_hdr + "<data>\n")
        for a in course_attendants:
            f.write(
                '<regkort fodselsdato="{}" personnr="{}" dato_endring="{}" '
                'dato_opprettet="{}"/>\n'.format(a['fodselsdato'],
                                                 a['personnr'],
                                                 str(now()),
                                                 str(now())))
            f.write('<emnestud fodselsdato="{}" personnr="{}" etternavn="{}" '
                    'fornavn="{}" adrlin2_semadr="" postnr_semadr="" '
                    'adrlin3_semadr="" adrlin2_hjemsted="" postnr_hjemsted="" '
                    'adrlin3_hjemsted="" sprakkode_malform="NYNORSK" '
                    'kjonn="X" studentnr_tildelt="{}" personlopenr="{}" '
                    'emnekode="FORGLU" '
                    'versjonskode="1" terminkode="VÅR" arstall="2016" '
                    'telefonlandnr_mobil="{}" telefonnr_mobil="{}"/>\n'.format(
                        a['fodselsdato'],
                        a['personnr'],
                        a['etternavn'],
                        a['fornavn'],
                        a['studentnr_tildelt'],
                        a['personlopenr'],
                        a['telefonlandnr'],
                        a['telefonnr']
                    ))
        f.write("</data>\n")
        f.close()

    def write_edu_info(self, edu_file):
        """Lager en fil med undervisningsinformasjonen til alle studenter.

        For hver student, lister vi opp alle tilknytningene til undenh, undakt,
        evu, kursakt og kull.

        Hovedproblemet i denne metoden er at vi må bygge en enorm dict med all
        undervisningsinformasjon. Denne dicten bruker mye minne.

        Advarsel: vi gjør ingen konsistenssjekk på at undervisningselementer
        nevnt i outfile vil faktisk finnes i andre filer genererert av dette
        skriptet. Mao. det er fullt mulig at en student S er registrert ved
        undakt U1, samtidig som U1 ikke er nevnt i undervisningsaktiveter.xml.

        fs.undervisning.list_studenter_alle_kull()      <- kull deltagelse
        fs.undervisning.list_studenter_alle_undenh()    <- undenh deltagelse
        fs.undervisning.list_studenter_alle_undakt()    <- undakt deltagelse
        fs.evu.list_studenter_alle_kursakt()            <- kursakt deltagelse
        fs.evu.list()                                   <- evu deltagelse
        """
        logger.info("Writing edu info to '%s'", edu_file)
        f = SimilarSizeWriter(edu_file, mode='w', encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")

        for triple in (
                ("kull", None,
                 self.fs.undervisning.list_studenter_alle_kull),
                ("undenh", None,
                 self.fs.undervisning.list_studenter_alle_undenh),
                ("undakt", None,
                 self.fs.undervisning.list_studenter_alle_undakt),
                ("evu", ("fodselsdato",
                         "personnr",
                         "etterutdkurskode",
                         "kurstidsangivelsekode"),
                 self.fs.evu.list),
                ("kursakt", None, self.fs.evu.list_studenter_alle_kursakt)):
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

    def write_regkort_info(self, regkort_file):
        """Lager fil med informasjon om semesterregistreringer for
        inneværende semester"""
        logger.info("Writing regkort info to '%s'", regkort_file)
        f = SimilarSizeWriter(regkort_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, regkort = self._ext_cols(self.fs.student.list_semreg())
        for r in regkort:
            f.write(
                xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'regkort') + "\n")
        f.write("</data>\n")
        f.close()

    def write_betalt_papir_info(self, betalt_papir_file):
        """Lager fil med informasjon om alle som enten har fritak fra å
        betale kopiavgift eller har betalt kopiavgiften"""

        logger.info("Writing betaltpapir info to '%s'", betalt_papir_file)
        f = SimilarSizeWriter(betalt_papir_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, dta = self._ext_cols(
            self.fs.betaling.list_kopiavgift_data(
                kun_fritak=False, semreg=True))
        for t in dta:
            self.fix_float(t)
            f.write(
                xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'betalt') + "\n")
        f.write("</data>\n")
        f.close()

    @staticmethod
    def fix_float(row):
        for n in range(len(row)):
            if isinstance(row[n], float):
                row[n] = int(row[n])


def set_filepath(datadir, filename):
    """Return the string of path to a file. If the given file path is
    relative, the datadir is used as a prefix, otherwise only the file
    path is returned.
    """
    if os.path.isabs(filename):
        return filename
    return os.path.join(datadir, filename)


class AtomicStreamRecoder(AtomicFileWriter):
    """ file writer encoding hack.

    xmlprinter.xmlprinter encodes data in the desired encoding before writing
    to the stream, and AtomicFileWriter *requires* unicode-objects to be
    written.

    This hack turns AtomicFileWriter into a bytestring writer. Just make sure
    the AtomicStreamRecoder is configured to use the same encoding as the
    xmlprinter.

    The *proper* fix would be to retire the xmlprinter module, and replace it
    with something better.
    """

    def write(self, data):
        if isinstance(data, bytes) and self.encoding:
            # will be re-encoded in the same encoding by 'write'
            data = data.decode(self.encoding)
        return super(AtomicStreamRecoder, self).write(data)
