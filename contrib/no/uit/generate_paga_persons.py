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
from pprint import pprint

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.extlib import xmlprinter

logger = logging.getLogger(__name__)

default_charsep = ';'
default_encoding = 'iso-8859-1'
default_end_date = datetime.date(2070, 1, 1)


# define field positions in PAGA csv-data
# First line in PAGA csv file contains field names. Use them.
KEY_AKSJONKODE = 'A.kode'
KEY_AKSJONDATO = 'A.dato'
KEY_ANSATTNR = 'Ansattnr'
KEY_HJEMSTED_ADRESSE = 'Adresse'
KEY_HJEMSTED_POSTSTED = 'Poststed'
KEY_HJEMSTED_POSTNR = 'Postnr'
KEY_AV = 'Av'
KEY_BRUKERNAVN = 'Brukernavn'
KEY_DBHKAT = 'DBH stillingskategori'
KEY_DATOFRA = 'F.lønnsdag'
KEY_DATOTIL = 'S.lønnsdag'
KEY_EPOST = 'E-postadresse'
KEY_ETTERNAVN = 'Etternavn'
KEY_FNR = 'Fødselsnummer'
KEY_FORNAVN = 'Fornavn'
KEY_HOVEDARBFORH = 'HovedAF'
KEY_KOSTNADSTED = 'K.sted'
KEY_NR = 'Nr'
KEY_ORGSTED = 'Org.nr.'
KEY_PERMISJONKODE = 'P.kode'
KEY_STANDEL = 'St.andel'
KEY_STILLKODE = 'St. kode'
KEY_TITTEL = 'St.bet'
KEY_TJFORH = 'Tj.forh.'
KEY_UNIKAT = 'Univkat'
KEY_UITKAT = 'UITkat'
KEY_KJONN = 'Kjønn'
KEY_FODSELSDATO = 'Fødselsdato'
KEY_LOKASJON = 'Lokasjon'
KEY_NATIONAL_ID_TYPE = 'edag_int_id_type'
KEY_NATIONAL_ID = 'edag_id_nr'
KEY_NATIONAL_LAND = 'edag_id_land'


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


def read_csv_file(filename,
                  encoding=default_encoding,
                  charsep=default_charsep):
    logger.info("reading csv file=%r (encoding=%r, charsep=%r)",
                filename, encoding, charsep)
    with open(filename, mode='r') as f:
        for data in csv.DictReader(f, delimiter=charsep.encode(encoding)):
            yield {k.decode(encoding): v.decode(encoding)
                   for k, v in data.items()}


def parse_paga_csv(pagafile):
    persons = dict()
    tilsettinger = dict()
    permisjoner = dict()
    dupes = list()

    today = datetime.date.today()

    for detail in read_csv_file(pagafile):
        ssn = detail[KEY_FNR]
        logger.debug("processing: %r", ssn)
        # some checks
        if detail[KEY_TJFORH] == 'H':
            # these persons are 'honorar' persons. Skip them entirely
            logger.warning("skipping honorar: %r", ssn)
            continue

        if detail[KEY_PERMISJONKODE] not in cereconf.PAGA_PERMKODER_ALLOWED:
            logger.warn("Dropping detail for %r, P.Kode=%r",
                        ssn, detail[KEY_PERMISJONKODE])
            permisjoner[ssn] = detail[KEY_PERMISJONKODE]
            continue
        elif detail[KEY_AKSJONKODE]:
            logger.warning("Detail contains A.Kode for %r, A.Kode=%r",
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
            'country': detail[KEY_NATIONAL_LAND],
            'edag_id_nr': detail[KEY_NATIONAL_ID],
            'edag_id_type': detail[KEY_NATIONAL_ID_TYPE],
        }
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
                national_id_type=""
                national_id=""
                country=""
                fakultetnr_for_lonnsslip=""
                instituttnr_for_lonnsslip=""
                gruppenr_for_lonnsslip=""
                #adresselinje1_privatadresse=""
                #poststednr_privatadresse=""
                #poststednavn_privatadresse=""
                #uname="">
            <bilag stedkode=""/>
        </person>
        """
        stream = open(self.out_file, "wb")
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level=2,
                                       data_mode=True)
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

    show_person = args.show
    pers, tils, perms = parse_paga_csv(args.infile)
    logger.info('Read %d persons from %r', len(pers), args.infile)

    if show_person is not None:
        if show_person in pers:
            print("*** Personinfo ***")
            pprint(pers[show_person])
            print("")
        if show_person in tils:
            print("*** Tilsettingsinfo ***")
            pprint(tils[show_person])
            print("")
        if show_person in perms:
            print("*** Permisjonsinfo ***")
            pprint(perms[show_person])
            print("")
    else:
        xml = PagaPersonsXml(args.outfile)
        xml.create(pers, tils, perms)
        logger.info('Wrote output to %r', args.outfile)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
