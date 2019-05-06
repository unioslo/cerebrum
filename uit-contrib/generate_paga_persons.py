#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
This script converts the Paga XML file to a CSV file.
"""
from __future__ import print_function, unicode_literals

import argparse
import csv
import datetime
import logging
import os
import sys
# import time

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.extlib import xmlprinter


# Define defaults
CHARSEP = ';'

logger = logging.getLogger(__name__)

# define field positions in PAGA csv-data
# First line in PAGA csv file contains field names. Use them.
KEY_AKSJONKODE = 'A.kode'.encode('ISO-8859-1')
KEY_AKSJONDATO = 'A.dato'.encode('ISO-8859-1')
KEY_ANSATTNR = 'Ansattnr'.encode('ISO-8859-1')
KEY_HJEMSTED_ADRESSE = 'Adresse'.encode('ISO-8859-1')
KEY_HJEMSTED_POSTSTED = 'Poststed'.encode('ISO-8859-1')
KEY_HJEMSTED_POSTNR = 'Postnr'.encode('ISO-8859-1')
KEY_AV = 'Av'.encode('ISO-8859-1')
KEY_BRUKERNAVN = 'Brukernavn'.encode('ISO-8859-1')
KEY_DBHKAT = 'DBH stillingskategori'.encode('ISO-8859-1')
KEY_DATOFRA = 'F.lønnsdag'.encode('ISO-8859-1')
KEY_DATOTIL = 'S.lønnsdag'.encode('ISO-8859-1')
KEY_EPOST = 'E-postadresse'.encode('ISO-8859-1')
KEY_ETTERNAVN = 'Etternavn'.encode('ISO-8859-1')
KEY_FNR = 'Fødselsnummer'.encode('ISO-8859-1')
KEY_FORNAVN = 'Fornavn'.encode('ISO-8859-1')
KEY_HOVEDARBFORH = 'HovedAF'.encode('ISO-8859-1')
KEY_KOSTNADSTED = 'K.sted'.encode('ISO-8859-1')
KEY_NR = 'Nr'.encode('ISO-8859-1')
KEY_ORGSTED = 'Org.nr.'.encode('ISO-8859-1')
KEY_PERMISJONKODE = 'P.kode'.encode('ISO-8859-1')
KEY_STANDEL = 'St.andel'.encode('ISO-8859-1')
KEY_STILLKODE = 'St. kode'.encode('ISO-8859-1')
KEY_TITTEL = 'St.bet'.encode('ISO-8859-1')
KEY_TJFORH = 'Tj.forh.'.encode('ISO-8859-1')
KEY_UNIKAT = 'Univkat'.encode('ISO-8859-1')
KEY_UITKAT = 'UITkat'.encode('ISO-8859-1')
KEY_KJONN = 'Kjønn'.encode("iso-8859-1")
KEY_FODSELSDATO = 'Fødselsdato'.encode('ISO-8859-1')
KEY_LOKASJON = 'Lokasjon'.encode('ISO-8859-1')


def parse_date(date_str):
    """
    Parse a date on the strfdate format "%Y-%m-%d".

    :rtype: datetime.date
    :return: Returns the date object, or ``None`` if an invalid date is given.
    """
    if not date_str:
        raise ValueError('Invalid date %r' % (date_str, ))
    args = (int(date_str[0:4]),
            int(date_str[5:7]),
            int(date_str[8:10]))
    return datetime.date(*args)


default_end_date = datetime.date(2070, 1, 1)


def read_csv_file(filename):
    with open(filename, 'r') as f:
        for data in csv.DictReader(f, delimiter=str(CHARSEP)):
            yield data


def parse_paga_csv(pagafile):
    persons = dict()
    tilsettinger = dict()
    permisjoner = dict()
    dupes = list()
    logger.info("Reading %s", pagafile)
    logger.debug('using charsep=%r', CHARSEP)

    today = datetime.date.today()

    for detail in read_csv_file(pagafile):
        ssn = detail[KEY_FNR]
        logger.debug("processing:%s", ssn)
        # some checks
        if detail[KEY_TJFORH] == 'H':
            # these persons are 'honorar' persons. Skip them entirely
            logger.warning("skipping honorar: %s", ssn)
            continue

        if detail[KEY_PERMISJONKODE] not in cereconf.PAGA_PERMKODER_ALLOWED:
            logger.warn("Dropping detail for %s, P.Kode=%s",
                        ssn, detail[KEY_PERMISJONKODE])
            permisjoner[ssn] = detail[KEY_PERMISJONKODE]
            continue
        elif detail[KEY_AKSJONKODE]:
            logger.warning("Detail contains A.Kode for %s, A.Kode=%s",
                           ssn, detail[KEY_AKSJONKODE])

        person_data = {
            'ansattnr': detail[KEY_ANSATTNR],
            'fornavn': detail[KEY_FORNAVN],
            'etternavn': detail[KEY_ETTERNAVN],
            'brukernavn': detail[KEY_BRUKERNAVN],
            'epost': detail[KEY_EPOST],
            'kjonn': detail[KEY_KJONN],
            'fodselsdato': detail[KEY_FODSELSDATO],
            'adresse': detail[KEY_HJEMSTED_ADRESSE],
            'poststed': detail[KEY_HJEMSTED_POSTSTED],
            'postnr': detail[KEY_HJEMSTED_POSTNR],
            'lokasjon': detail[KEY_LOKASJON],
        }
        # tilskey = "%s:%s" % (detail[KEY_NR], detail[KEY_AV])
        tils_data = {
            'stillingskode': detail[KEY_STILLKODE],
            'tittel': detail[KEY_TITTEL],
            'stillingsandel': detail[KEY_STANDEL],
            'kategori': detail[KEY_UITKAT],
            'hovedkategori': detail[KEY_UNIKAT],
            'tjenesteforhold': detail[KEY_TJFORH],
            'dato_fra': detail[KEY_DATOFRA],
            'dato_til': detail[KEY_DATOTIL],
            'dbh_kat': detail[KEY_DBHKAT],
            'hovedarbeidsforhold': detail[KEY_HOVEDARBFORH],
            'forhold_nr': detail[KEY_NR],
            'forhold_av': detail[KEY_AV],
            'permisjonskode': detail[KEY_PERMISJONKODE],
        }
        stedkode = detail[KEY_ORGSTED]

        if persons.get(ssn, None):
            dupes.append(ssn)
            if tils_data['hovedarbeidsforhold'] == 'H':
                logger.debug("person %s already exists in dataset, but this "
                             "instance has hovedarbeidsforhold == H. Update "
                             "person data", ssn)
                persons[ssn] = person_data
        else:
            persons[ssn] = person_data

        # tilsettinger we have seen before
        current = tilsettinger.get(ssn, dict())

        if not current:
            # sted not seen before, insert
            tilsettinger[ssn] = {stedkode: tils_data}
        else:
            tmp = current.get(stedkode)
            if tmp:
                logger.warn("Several tilsettinger to same place for %s", ssn)

                # Several tilsettinger to same place. Keep the first one of:
                #
                # - Get affiliation where hovedarbeidsforhold == H and where
                #   dato_til is in the future
                # - Get affiliation where dato_fra is in the past and where
                #   dato_fra is later than dato_til in already registered
                #   affiliation and where dato_til is in the future
                # - Get affiliation where permisjonskode is being changed from
                #   somevalue to 0 (zero)

                insert_person = False

                if tils_data['dato_til']:
                    dato_til = parse_date(tils_data['dato_til'])
                else:
                    dato_til = default_end_date

                if tmp['dato_til']:
                    tmp_til = parse_date(tmp['dato_til'])
                else:
                    tmp_til = default_end_date

                dato_fra = parse_date(tils_data['dato_fra'])

                if (tils_data['hovedarbeidsforhold'] == 'H' and
                        dato_til > today):
                    logger.debug("on_hovedarbeidsforhold: inserting person:%s",
                                 tils_data)
                    insert_person = True

                elif (tmp['hovedarbeidsforhold'] == 'H' and tmp_til < today):
                    if (dato_fra < today and
                            dato_fra >= tmp_til and
                            dato_til > today):
                        logger.error("generating person object with ssn:%s, "
                                     "based on dato_fra/dato_til. Verify this",
                                     ssn)
                        insert_person = True

                elif (tmp['permisjonskode'] != '0' and
                      tils_data['permisjonskode'] == '0'):
                    logger.debug("on_permisjonskode: inserting person:%s",
                                 tils_data)
                    insert_person = True

                if insert_person:
                    tilsettinger[ssn][stedkode] = tils_data
                else:
                    logger.info("Skipped aff at same place for %s, data: %s",
                                ssn, tils_data)
            else:
                logger.info("adding tilsetting for %s" % (ssn))
                tilsettinger[ssn][stedkode] = tils_data

    return persons, tilsettinger, permisjoner


class PagaPersonsXml:

    def __init__(self, out_file):
        self.out_file = out_file

    def create(self, persons, affiliations, permisjoner):
        """
        Build a xml that import_lt should process:

        <person tittel_personlig=""
        fornavn=""
        etternavn=""
        fnr=""
        fakultetnr_for_lonnsslip=""
        instituttnr_for_lonnsslip=""
        gruppenr_for_lonnsslip=""
        #adresselinje1_privatadresse=""
        #poststednr_privatadresse=""
        #poststednavn_privatadresse=""
        #uname=""
        >
        <bilag stedkode=""/>
        </person>
        """

        stream = open(self.out_file, "wb")
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level=2,
                                       data_mode=True,
                                       input_encoding="latin1")
        writer.startDocument(encoding="iso8859-1")
        writer.startElement("data")

        for fnr, person_data in persons.iteritems():
            affs = affiliations.get(fnr)
            aff_keys = affs.keys()
            person_data['fnr'] = fnr

            temp_tils = list()
            for sted in aff_keys:
                aff = affs.get(sted)
                # use . instead of , as decimal char.
                st_andel = aff.get('stillingsandel', '').replace(',', '.')
                if st_andel == '':
                    logger.error("ST.andel for fnr %s er tom", fnr)
                tils_dict = {
                    'hovedkategori': aff['hovedkategori'],
                    'stillingskode': aff['stillingskode'],
                    'tittel': aff['tittel'],
                    'stillingsandel': st_andel,
                    'fakultetnr_utgift': sted[0:2],
                    'instituttnr_utgift': sted[2:4],
                    'gruppenr_utgift': sted[4:6],
                    'dato_fra': aff['dato_fra'],
                    'dato_til': aff['dato_til'],
                    'dbh_kat': aff['dbh_kat'],
                    'hovedarbeidsforhold': aff['hovedarbeidsforhold'],
                    'tjenesteforhold': aff['tjenesteforhold'],
                }
                temp_tils.append(tils_dict)
            writer.startElement("person", person_data)
            for tils in temp_tils:
                writer.emptyElement("tils", tils)
            writer.endElement("person")
        writer.endElement("data")
        writer.endDocument()
        stream.close()


default_outfile = os.path.join(
    sys.prefix, 'var/cache/employees',
    'paga_persons_{date}.xml'.format(
        date=datetime.date.today().strftime('%Y-%m-%d')))
default_infile = os.path.join(
    sys.prefix, 'var/cache/paga', 'uit_paga_last.csv')
default_log_preset = getattr(cereconf, 'DEFAULT_LOGGER_TARGET', 'console')


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Convert CSV-file from Paga to XML file for import")

    parser.add_argument(
        '-p', '--paga-file',
        dest='infile',
        default=default_infile,
        help='Read and parse data from csv-file %(metavar)s',
        metavar='file',
    )
    parser.add_argument(
        '-o', '--out-file',
        dest='outfile',
        default=default_outfile,
        help='Write output to XML-file %(metavar)s',
        metavar='file',
    )
    parser.add_argument(
        '-s', '--show',
        help='Show data for a person with ssn %(metavar)s and exit',
        metavar='ssn',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(default_log_preset, args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    out_file = args.outfile
    paga_file = args.infile
    show_person = args.show

    pers, tils, perms = parse_paga_csv(paga_file)
    logger.debug("File parsed. Got %d persons", len(pers))

    if show_person is not None:
        if show_person in pers:
            print("*** Personinfo ***")
            print(pers[show_person])
            print("")
        if show_person in tils:
            print("*** Tilsettingsinfo ***")
            print(tils[show_person])
            print("")
        if show_person in perms:
            print("*** Permisjonsinfo ***")
            print(perms[show_person])
            print("")
    else:
        xml = PagaPersonsXml(out_file)
        xml.create(pers, tils, perms)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
