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
Convert OU files.

This file reads ou data from a csv file, compares the stedkode
code with what already exists in FS and inserts right ou information from
that file.  For stedkoder who doesnt exist in FS, default data is inserted.
"""
from __future__ import unicode_literals

import argparse
import io
import logging
import os

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.extlib import xmlprinter
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.utils.atomicfile import SimilarSizeStreamRecoder

logger = logging.getLogger(__name__)


def format_int(value, fmt='02d'):
    return format(int(value), fmt)


class OuGenerator(object):

    defaults = {
        'telefonnr': '0',
        'adrlin1': 'Universitetet i Tromsø',
        'postnr': '9037',
        'adrlin3': 'Tromsø',
    }

    def __init__(self, fs, ou_files):
        self.fs = fs
        self.ou_files = ou_files

    def get_fs_ou(self):
        """ Collect data about all active ou's from FS. """
        logger.info("Reading OU's from FS")
        fs_data = {}

        ouer = self.fs.ou.list_ou(institusjonsnr=186)

        poststednr_besok_adr = ''
        # poststednr_alternativ_adr = ''

        for i in ouer:
            temp_inst_nr = "%02d%02d%02d" % (i['faknr'],
                                             i['instituttnr'],
                                             i['gruppenr'])
            for key in i.keys():
                if i[key] is None:
                    i[key] = ''
                else:
                    i[key] = six.text_type(i[key])

            postnr = six.text_type(i['postnr'])
            # postnr_besok = six.text_type(i['postnr_besok'])

            if postnr.isdigit():
                poststednr_besok_adr = postnr

            # if postnr_besok.isdigit():
            #     poststednr_alternativ_adr = postnr_besok

            for key in self.defaults:
                if not i[key]:
                    i[key] = self.defaults[key]

            if not 'adrlin2':
                i['adrlin2'] = i['stednavn_bokmal']

            fs_data[temp_inst_nr] = {
                'fakultetnr': format_int(i['faknr']),
                'instituttnr': format_int(i['instituttnr']),
                'gruppenr': format_int(i['gruppenr']),
                'stednavn': i['stednavn_bokmal'],
                'forkstednavn': i['stedkortnavn'],
                'akronym': i['stedakronym'],
                'stedkortnavn_bokmal': i['stedkortnavn'],
                'stedlangnavn_bokmal': i['stednavn_bokmal'],
                'fakultetnr_for_org_sted': format_int(i['faknr_org_under']),
                'instituttnr_for_org_sted': format_int(
                    i['instituttnr_org_under']),
                'gruppenr_for_org_sted': format_int(i['gruppenr_org_under']),
                'opprettetmerke_for_oppf_i_kat': 'X',
                'telefonnr': i['telefonnr'],
                'innvalgnr': '00',
                'linjenr': i['telefonnr'],
                'adrtypekode_besok_adr': 'INT',
                'adresselinje1_besok_adr': i['adrlin1'],
                'adresselinje2_besok_adr': i['adrlin2'],
                'poststednr_besok_adr': poststednr_besok_adr,
                'poststednavn_besok_adr': ' '.join((
                    six.text_type(i['adrlin1_besok']),
                    six.text_type(i['adrlin2_besok']),
                    '',
                )),
                'adresselinje1_intern_adr': i['adrlin1'],
                'adresselinje2_intern_adr': i['adrlin2'],
                'poststednr_intern_adr': i['postnr'],
                'poststednavn_intern_adr': i['adrlin3'],
            }

        return fs_data

    def _parse_line(self, line):
        """
        Parse a single line of csv data.
        """
        # TODO: Use the csv module to parse csv data...

        # positions in file
        field_sko = 0
        field_acronym = 1
        # field_location = 2
        field_shortname = 3
        field_fullname = 4
        num_fields = 5

        items = line.split(";")

        if len(items) != num_fields:
            raise ValueError(
                'Incorrect number of fields, got %d, expected %d' %
                (len(items), num_fields))

        def get_field(field):
            return items[field].strip('"').strip()

        sko = get_field(field_sko)
        faknr = sko[0:2]
        instnr = sko[2:4]
        avdnr = sko[4:6]
        fulltnavn = get_field(field_fullname)
        akronym = get_field(field_acronym)
        kortnavn = get_field(field_shortname)

        if avdnr == '00' and instnr == '00':
            # we have a faculty, must reference the institution
            faknr_org_under = '00'
            instituttnr_org_under = '00'
            gruppenr_org_under = '00'

        elif avdnr != '00' and instnr != '00':
            # we have a group, must reference the institute
            faknr_org_under = faknr
            instituttnr_org_under = instnr
            gruppenr_org_under = '00'

        else:
            # we have either a institute or a group directly under a
            # faculty. in either case it should reference he faculty
            faknr_org_under = faknr
            instituttnr_org_under = '00'
            gruppenr_org_under = '00'

        ou_dict = {
            'fakultetnr': faknr.zfill(2),
            'instituttnr': instnr.zfill(2),
            'gruppenr': avdnr.zfill(2),
            'stednavn': fulltnavn,
            'display_name': fulltnavn,
            'forkstednavn': kortnavn,
            'akronym': akronym,
            'stedlangnavn_bokmal': fulltnavn,
            'fakultetnr_for_org_sted': faknr_org_under,
            'instituttnr_for_org_sted': instituttnr_org_under,
            'gruppenr_for_org_sted': gruppenr_org_under,
            'adresselinje1_intern_adr': 'Universitetet i Tromso',
            'adresselinje2_intern_adr': fulltnavn,
            'poststednr_intern_adr': '9037',
            'poststednavn_intern_adr': 'Tromso',
            'opprettetmerke_for_oppf_i_kat': 'F',
            'telefonnr': '77644000',
            'sort_key': "1",
        }

        return sko, ou_dict

    def get_authoritative_ou(self):
        authoritative_ou = {}

        for filename in self.ou_files:
            logger.info("Reading authoritative OU file %r", filename)
            with io.open(filename, mode='r', encoding='utf-8') as fileobj:
                for lineno, line in enumerate(fileobj, 1):
                    line = line.strip()
                    if not line or any(line.startswith(char) for char in ';#'):
                        continue
                    try:
                        sko, ou_dict = self._parse_line(line)
                        authoritative_ou[sko] = ou_dict
                    except Exception:
                        logger.error('Unable to parse %r line %d: %r',
                                     filename, lineno, line, exc_info=True)
        return authoritative_ou

    def generate_ou(self, fs_ou, auth_ou):
        result_ou = dict()
        for a_ou, a_ou_data in auth_ou.items():
            f_ou = fs_ou.get(a_ou, None)
            if f_ou:
                # fill in OU data elemnts from FS where we have no
                # eqivalent data in authoritative ou file
                for k, v in f_ou.items():
                    if k not in a_ou_data:
                        # logger.debug("sko=%r in input files is missing %r, "
                        #              "using fs value=%r", a_ou, k, v)
                        a_ou_data[k] = v
                del fs_ou[a_ou]
            else:
                # logger.warn("sko=%r not in fs, using ou from input files",
                #             a_ou)
                pass

            result_ou[a_ou] = a_ou_data

        # log remaining FS ou's as errors
        # for f_ou, f_ou_data in fs_ou.items():
        #     logger.error("sko=%r in fs missing from input files (%s)",
        #                  f_ou, f_ou_data['stednavn'])
        return result_ou

    def print_ou(self, final_ou, out_file):
        logger.info("Writing OU file %s", out_file)
        encoding = 'iso-8859-1'
        with SimilarSizeStreamRecoder(out_file, "w",
                                      encoding=encoding) as stream:
            writer = xmlprinter.xmlprinter(stream,
                                           indent_level=2,
                                           data_mode=True)
            writer.startDocument(encoding=encoding)
            writer.startElement("data")

            for ou, ou_data in final_ou.items():
                writer.emptyElement("sted", ou_data)
            writer.endElement("data")
            writer.endDocument()


def _parse_ou_files(values):
    for value in (values or ()):
        for filename in value.split(','):
            if os.path.exists(filename):
                yield filename
            else:
                logger.warning("OU file %r does not exist", filename)
                continue


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Convert OU files",
    )
    parser.add_argument(
        '--ou-source',
        dest='sources',
        action='append',
        required=True,
        help='Read OUs from source file %(metavar)s',
        metavar='<file>',
    )
    parser.add_argument(
        '--out-file',
        dest='output',
        required=True,
        help='Write output a %(metavar)s XML file',
        metavar='<file>',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %r', parser.prog)
    logger.debug("args: %r", args)

    ou_files = list(_parse_ou_files(args.sources or ()))
    logger.debug("sources: %r", ou_files)

    if not ou_files:
        logger.error('No valid ou-source files (args=%r, valid=%r)',
                     args.sources, ou_files)
        parser.error('No valid ou-source files')

    output = args.output
    logger.debug('output: %r', output)

    fs = make_fs()
    my_ou = OuGenerator(fs, ou_files)

    logger.info('fetching ous from fs...')
    fs_ou = my_ou.get_fs_ou()
    logger.info('found %d ous in fs', len(fs_ou))

    logger.info('parsing ous from files...')
    auth_ou = my_ou.get_authoritative_ou()
    logger.info('found %d ous in files', len(auth_ou))

    logger.info('merging ou data...')
    final_ou = my_ou.generate_ou(fs_ou, auth_ou)
    logger.info('ended up with %d ous', len(final_ou))

    my_ou.print_ou(final_ou, output)
    logger.info('Output written to %r', output)
    logger.info('Done %r', parser.prog)


if __name__ == '__main__':
    main()
