#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2018 University of Oslo, Norway""
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
""" Generate an HTML report on persons with a specific affiliation. """
from __future__ import unicode_literals

import argparse
import datetime
import logging
import os
import sys

import jinja2
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type, get_constant
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)
now = datetime.datetime.now


def make_sko_lookup(db):
    ou = Factory.get(b'OU')(db)
    co = Factory.get(b'Constants')(db)

    @memoize
    def sko_lookup(ou_id):
        ou.clear()
        ou.find(ou_id)
        sko = "{:02d}{:02d}{:02d}".format(ou.fakultet,
                                          ou.institutt,
                                          ou.avdeling)
        try:
            name = ou.get_name_with_language(name_variant=co.ou_name_acronym,
                                             name_language=co.language_nb)
        except NotFoundError:
            name = '<no acronym in nb_no>'
        return sko, name
    return sko_lookup


def persons_with_aff_status(db, status):
    co = Factory.get(b'Constants')(db)
    pe = Factory.get(b'Person')(db)
    ac = Factory.get(b'Account')(db)
    ou_info = make_sko_lookup(db)

    def _u(db_value):
        if db_value is None:
            return text_type('')
        if isinstance(db_value, bytes):
            return db_value.decode(db.encoding)
        return text_type(db_value)

    logger.debug('caching employee ids ...')
    pe2sapid = dict(
        (r['entity_id'], r['external_id'])
        for r in pe.search_external_ids(source_system=co.system_sap,
                                        id_type=co.externalid_sap_ansattnr,
                                        fetchall=False))

    logger.debug('caching non-expired accounts ...')
    ac2name = dict((r['account_id'], r['name']) for r in ac.search())

    logger.debug('finding persons with aff=%s...', text_type(status))
    unique = set()
    affiliations = 0
    for row in pe.list_affiliations(status=status):
        person_id = row['person_id']
        ou_id = row['ou_id']
        pe.clear()
        pe.find(person_id)

        primary = pe.get_primary_account()
        if primary not in ac2name:
            continue

        sap_id = pe2sapid.get(person_id)
        account_name = ac2name[primary]
        full_name = pe.get_name(source_system=co.system_cached,
                                variant=co.name_full)
        birth = pe.birth_date.strftime('%Y-%m-%d')
        sko, ou_name = ou_info(ou_id)

        unique.add(primary)
        affiliations += 1
        yield {
            'account_name': _u(account_name),
            'person_name': _u(full_name),
            'birth': text_type(birth),
            'sap_id': _u(sap_id),
            'affiliation': text_type(status),
            'ou_sko': text_type(sko),
            'ou_name': _u(ou_name),
        }

    logger.info('Found %d affiliations', affiliations)
    logger.info('Found %d unique persons', len(unique))


def write_html_report(stream, codec, person_data, aff_status):
    output = codec.streamwriter(stream)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                       'templates')))
    template = env.get_template('simple_list_overview.html')

    iso_timestamp = now().strftime('%Y-%m-%d %H:%M:%S')
    title = 'List of persons with affiliation {aff} ({timestamp})'.format(
        timestamp=iso_timestamp, aff=text_type(aff_status))

    output.write(
        template.render(
            encoding=codec.name,
            headers=(
                ('account_name', 'Account name'),
                ('person_name', 'Name'),
                ('birth', 'Birth date'),
                ('sap_id', "SAP Id"),
                # ('affiliation', 'Affiliation'),
                ('ou_sko', 'OU'),
                ('ou_name', 'OU acronym')),
            title=title,
            prelist='<h3>{}</h3>'.format(title),
            items=person_data,
        )
    )
    output.write("\n")


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='output file for report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")
    aff_arg = parser.add_argument(
        '--aff-status',
        dest='status',
        required=True,
        help='Lists persons with this affiliation status')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get(b'Database')()
    co = Factory.get(b'Constants')(db)

    aff_status = get_constant(db, parser, co.PersonAffStatus, args.status,
                              aff_arg)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)
    logger.info("aff-status: %s", text_type(aff_status))

    persons = persons_with_aff_status(db, aff_status)
    sorted_persons = sorted(persons,
                            key=lambda x: (x['ou_sko'],
                                           x['account_name']))

    write_html_report(args.output, args.codec, sorted_persons, aff_status)

    args.output.flush()
    if args.output is not sys.stdout:
        args.output.close()

    logger.info('Report written to %s', args.output.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == "__main__":
    main()
