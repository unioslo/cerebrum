#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
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

import csv
import getopt
import os
import sys

import mx.DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory


progname = __file__.split("/")[-1]
__doc__ = """Usage: %s [options]
    Generate file with paganr, username and e-mail

    options:
    -o | --out_file   : file to store output
    -p | --paga-file  : file to read from
    -h | --help       : show this
    --logger-name     : name of logger to use
    --logger-level    : loglevel to use

""" % progname

# Define defaults
TODAY = mx.DateTime.today().strftime("%Y-%m-%d")
CHARSEP = ';'
dumpdir_paga = os.path.join(cereconf.DUMPDIR, "paga")
default_paga_file = 'uit_paga_last.csv'

default_out_path = os.path.join(cereconf.DUMPDIR, "pagaweb")
default_out_file = 'last.csv'
export_marker_file = 'copy_to_paga'

# some common vars
db = Factory.get('Database')()
logger = Factory.get_logger("cronjob")

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


def parse_paga_csv(pagafile):
    persons = {}

    logger.info("Loading paga file...")
    for detail in csv.DictReader(open(pagafile, 'r'),
                                 delimiter=CHARSEP):
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
    paga_extid = co.externalid_paga_ansattnr
    paga_source = co.system_paga
    fnr_extid = co.externalid_fodselsnr

    personid_ansattnr = {}
    logger.info("Caching person ids...")
    for ansattnr in persons.keys():
        pe.clear()
        try:
            pe.find_by_external_id(paga_extid, ansattnr)
            persons[ansattnr]['fnr'] = pe.get_external_id(
                source_system=paga_source,
                id_type=fnr_extid
            )[0]['external_id']
            personid_ansattnr[pe.entity_id] = ansattnr
        except Errors.NotFoundError:
            logger.error("Person not found in BAS ansattnr:%s" % ansattnr)
            continue

    logger.info("Caching e-mails...")
    uname_mail = ac.getdict_uname2mailaddr()

    logger.info("Loading accounts...")
    for row in ac.search(expire_start=None):
        if row['name'][3:5] == '99':
            logger.debug("Skipping 999 account: %s" % (row['name']))
            continue
        elif row['name'].endswith(cereconf.USERNAME_POSTFIX['sito']):
            # elif row['name'][6:8] == '-s':
            logger.debug("Skipping sito account:%s" % (row['name']))
            continue
        pid = row['owner_id']
        if (pid in personid_ansattnr and
                personid_ansattnr[pid] in persons.keys()):
            persons[personid_ansattnr[pid]]['brukernavn'] = row['name']
            if row['name'] in uname_mail:
                persons[personid_ansattnr[pid]]['epost'] = \
                    uname_mail[row['name']]
            else:
                logger.warn("E-mail not found for ansatt: %s" % row['name'])
    return persons


def main():
    out_file = os.path.join(default_out_path, default_out_file)
    paga_file = os.path.join(dumpdir_paga, default_paga_file)
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'hp:o:',
            ['paga-file=', 'out-file=', 'help'])
    except getopt.GetoptError as m:
        usage(1, m)

    for opt, val in opts:
        if opt in ('-o', '--out-file'):
            out_file = val
        if opt in ('-p', '--paga-file'):
            paga_file = val
        if opt in ('-h', '--help'):
            usage()

    pers = parse_paga_csv(paga_file)
    logger.debug("Information collected. Processed %d persons", len(pers))

    # Før filen skrives, hent sist sendte sekvens. Starter på 1 og teller
    # oppover for hver fil
    try:
        fp = open(out_file, 'r')
        lines = csv.reader(fp, delimiter=';')
        sequence = int(lines.next()[3]) + 1
        fp.close()
    except IOError:
        # Sekvens starter på 1 for nye filer
        logger.error("Output file (%s) not found, "
                     "defaulting to sequence number 1",
                     out_file)
        sequence = 1

    fp = open(out_file, 'w')
    fp.write("00; UiT; %s; %s" % (TODAY, sequence))
    count = 0
    for ansattnr in pers.keys():
        if pers[ansattnr].get('brukernavn', None) is None:
            logger.error("Username empty: %s", ansattnr)

        if pers[ansattnr].get('epost', None) is None:
            logger.warning("E-post empty: %s (%s)", ansattnr,
                           pers[ansattnr].get('brukernavn', 'N/A'))

        if pers[ansattnr].get('fnr', None) is None:
            logger.error("FNR empty: %s (%s)", ansattnr,
                         pers[ansattnr].get('brukernavn', 'N/A'))

        fp.write("\n10; UiT; %s; %s; %s; %s" % (
            ansattnr,
            pers[ansattnr].get('fnr', ''),
            pers[ansattnr].get('brukernavn', ''),
            pers[ansattnr].get('epost', '')))
        count += 1

    fp.write("\n99; UiT; %s; %s" % (TODAY, count))
    fp.close()
    logger.debug("File written.")

    # This file will be deleted by the SCP script to ensure that files aren't
    # repeatedly copied with the same sequence number
    fp = open(out_file + '.new', 'w')
    fp.close()


def usage(exit_code=0, msg=None):
    if msg:
        print msg
    print __doc__
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
