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
Export employees from Paga to BlueGarden CSV file.

BlueGarden file format:

Startrecord
    00, UiT, 2010-02-11, 1

Datarecords
    10, UiT, ansattnr, fodselsnr, email, brukernavn

Sluttrecord
    99, UiT, 2010-02-11, num datarecords

History
-------
kbj005 2015.02.25: Copied from Leetah.
"""
from __future__ import print_function, unicode_literals

import argparse
import csv
import datetime
import io
import logging
import os
import shutil
import sys

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
from Cerebrum.Utils import Factory

logger = logging.getLogger(__name__)

# Define defaults
default_in_charsep = ';'
default_in_encoding = 'iso-8859-1'
default_out_encoding = 'iso-8859-1'

# define field positions in PAGA csv-data
# First line in PAGA csv file contains field names. Use them.
KEY_AKSJONKODE = 'A.kode'
KEY_AKSJONDATO = 'A.dato'
KEY_ANSATTNR = 'Ansattnr'
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


def read_csv_file(filename, encoding, charsep):
    logger.info("reading csv file=%r (encoding=%r, charsep=%r)",
                filename, encoding, charsep)
    with open(filename, mode='r') as f:
        for data in csv.DictReader(f, delimiter=charsep.encode(encoding)):
            yield {k.decode(encoding): v.decode(encoding)
                   for k, v in data.items()}


def parse_paga_csv(db, pagafile):
    persons = {}
    sito_postfix = cereconf.USERNAME_POSTFIX['sito']

    for detail in read_csv_file(pagafile,
                                encoding=default_in_encoding,
                                charsep=default_in_charsep):
        # De vi ønsker skal overføres er alle med ansattforhold:
        #  E (engasjert)
        #  F (fast)
        #  K (kvalifisering)
        #  U (utdanningsstilling)
        #  V (vikar)
        #  Å (åremål).
        #  P (permisjon)
        #  B (bistilling)
        #  ÅP (postdoc)
        #  L (lærling)
        #  T (timelønnet)
        if (detail[KEY_HOVEDARBFORH] == 'H' and
                detail[KEY_TJFORH].upper() in ['E', 'F', 'K', 'U', 'V',
                                               'Å', 'P', 'B', 'ÅP', 'L', 'T']):
            persons[detail[KEY_ANSATTNR]] = {}

    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    personid_ansattnr = {}
    logger.info("Caching person ids...")
    for ansattnr in persons.keys():
        pe.clear()
        try:
            pe.find_by_external_id(co.externalid_paga_ansattnr, ansattnr)
            personid_ansattnr[pe.entity_id] = ansattnr
        except Errors.NotFoundError:
            logger.error("Person not found in BAS with ansattnr=%r", ansattnr)
            continue

        for key, extid_type in (('fnr', co.externalid_fodselsnr),
                                ('passnr', co.externalid_pass_number)):
            try:
                persons[ansattnr][key] = pe.get_external_id(
                    source_system=co.system_paga,
                    id_type=extid_type,
                )[0]['external_id']
            except IndexError:
                logger.error("No id_type=%s for entity_id=%r, ansattnr=%r",
                             extid_type, pe.entity_id, ansattnr)
                continue
            else:
                logger.debug("Using id_type=%s for entity_id=%r, ansattnr=%r",
                             extid_type, pe.entity_id, ansattnr)
                break

    logger.info("Caching e-mails...")
    uname_mail = ac.getdict_uname2mailaddr()

    logger.info("Loading accounts...")
    for row in ac.search(expire_start=None):
        if row['name'][3:5] == '99':
            logger.debug("Skipping 999 account id=%r, name=%r",
                         row['account_id'], row['name'])
            continue
        elif row['name'].endswith(sito_postfix):
            logger.debug("Skipping sito account id=%r, name=%r",
                         row['account_id'], row['name'])
            continue
        pid = row['owner_id']
        if (pid in personid_ansattnr and
                personid_ansattnr[pid] in persons.keys()):
            persons[personid_ansattnr[pid]]['brukernavn'] = row['name']
            if row['name'] in uname_mail:
                persons[personid_ansattnr[pid]]['epost'] = \
                    uname_mail[row['name']]
            else:
                logger.warning("E-mail not found for account id=%r, name=%r",
                               row['account_id'], row['name'])
    return persons


def get_file_sequence(filename):
    """
    Fetch output file sequence number.
    """
    delim = ';'.encode(default_out_encoding)
    try:
        with open(filename, 'r') as fp:
            lines = csv.reader(fp, delimiter=delim)
            sequence = int(lines.next()[3])
        logger.info('Got sequence %r from %r', sequence, filename)
    except IOError:
        # Sekvens starter på 1 for nye filer
        logger.error("No output file=%r, starting sequence at 1",
                     filename)
        sequence = 0
    return sequence + 1


def write_persons(filename, pers, sequence, encoding=default_out_encoding):
    """
    Write person dicts to a cvs file.
    """
    today = datetime.date.today().strftime("%Y-%m-%d")

    with io.open(filename, mode='w', encoding=encoding) as fp:
        fp.write("00; UiT; %s; %s" % (today, sequence))
        count = 0
        for ansattnr in pers.keys():
            if pers[ansattnr].get('brukernavn', None) is None:
                logger.error("Username empty: %s", ansattnr)

            if pers[ansattnr].get('epost', None) is None:
                logger.warning("E-post empty: %s (%s)", ansattnr,
                               pers[ansattnr].get('brukernavn', 'N/A'))

            if pers[ansattnr].get('fnr', None) is None:
                logger.warning("FNR empty: %s (%s)", ansattnr,
                               pers[ansattnr].get('brukernavn', 'N/A'))

            fp.write("\n10; UiT; %s; %s; %s; %s" % (
                ansattnr,
                pers[ansattnr].get('fnr', ''),
                pers[ansattnr].get('brukernavn', ''),
                pers[ansattnr].get('epost', '')))
            count += 1

        fp.write("\n99; UiT; %s; %s" % (today, count))
        fp.close()


default_infile = os.path.join(sys.prefix, 'var/cache/paga',
                              'uit_paga_last.csv')
default_outfile = os.path.join(sys.prefix, 'var/cache/pagaweb', 'last.csv')
default_log_preset = getattr(cereconf, 'DEFAULT_LOGGER_TARGET', 'console')


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Generate file with paganr, username and e-mail")

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
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(default_log_preset, args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    pers = parse_paga_csv(db, args.infile)
    logger.debug("Information collected. Processed %d persons", len(pers))

    # Før filen skrives, hent sist sendte sekvens. Starter på 1 og teller
    # oppover for hver fil
    sequence = get_file_sequence(args.outfile)
    write_persons(args.outfile, pers, sequence)
    logger.info('Wrote output to %r', args.outfile)

    new_copy = args.outfile + '.new'
    shutil.copyfile(args.outfile, new_copy)
    logger.info('Wrote copy to %r', new_copy)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
