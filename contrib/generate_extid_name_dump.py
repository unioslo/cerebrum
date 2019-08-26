#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2018 University of Oslo, Norway
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
""" Generate a CSV report over names and external IDs from a source system.

The dump is colon-separated data with the external ID and name of the person
tied to the ID. Each line ends with the date and time for when the file was
generated, as required by Datavarehus.

Eg. To dump all employee-numbers from SAP:
    <scipt name> -s SAP -t NO_SAPNO

will produce a file:
    9831;Ola Normann;15/04/2013 09:01:43
    7321;Kari Normann;15/04/2013 09:01:44
    <employee_no>;<employee_name>;<date_time>
    ...

"""
import argparse
import functools
import logging
import sys
import time

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.argutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.csvutils import CerebrumDialect, UnicodeWriter


logger = logging.getLogger(__name__)


def make_name_cache(db):
    """ Make a cache of person names.

    :return callable:
        A callable that takes an entity_id and returns a string or None.
    """
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)

    cache = pe.getdict_persons_names(
        source_system=co.system_cached,
        name_types=co.name_full)

    def get_name(person_id):
        return cache.get(person_id, {}).get(int(co.name_full))
    return get_name


def get_external_ids(db, source_system, id_type):
    """
    :param db:
    :param source_system: source system to fetch persons from
    :param id_type: id type to fetch persons with

    :return generator:
        A generator that yields persons with the given id types.
    """
    pe = Factory.get('Person')(db)
    co = Factory.get('Constants')(db)
    for row in pe.search_external_ids(
            source_system=source_system,
            id_type=id_type,
            entity_type=co.entity_person,
            fetchall=False):
        yield {
            'entity_id': row['entity_id'],
            'ext_id': row['external_id'],
        }


def get_persons(db, source_system, id_type):
    """ Fetch persons to export. """
    logger.debug('get_persons ...')
    logger.debug('caching names...')
    get_name = make_name_cache(db)
    logger.debug('fetching persons...')
    for person_info in get_external_ids(db, source_system, id_type):
        person_info['name'] = get_name(person_info['entity_id'])
        if not person_info['name']:
            logger.warn("No name for person with external_id=%r. "
                        "Excluded from list.", person_info['ext_id'])
            continue
        yield person_info
    logger.debug('... get_persons done')


def get_output_stream(filename, codec):
    """ Get a unicode-compatible stream to write. """
    if filename == '-':
        stream = sys.stdout
    else:
        stream = AtomicFileWriter(filename, mode='w', encoding=codec.name)
    return stream


def write_csv_report(stream, persons):
    """ Write a CSV report to a stream.

    :param stream: file-like object that can write unicode strings
    :param persons: iterable with mappings that has keys ('ext_id', 'name')
    """
    writer = UnicodeWriter(stream, dialect=CerebrumDialect)
    for person in sorted(persons, key=lambda x: x['ext_id']):
        writer.writerow((
            person['ext_id'],
            person['name'],
            time.strftime('%m/%d/%Y %H:%M:%S'),
        ))


DEFAULT_ENCODING = 'utf-8'
DEFAULT_SOURCE_SYSTEM = 'SAP'
DEFAULT_EXTERNAL_ID = 'NO_SAPNO'


def main(inargs=None):
    doc = (__doc__ or '').strip().split('\n')

    parser = argparse.ArgumentParser(
        description=doc[0],
        epilog='\n'.join(doc[1:]),
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        default='-',
        help='The file to print the report to, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=Cerebrum.utils.argutils.codec_type,
        help="Output file encoding, defaults to %(default)s")
    source_arg = parser.add_argument(
        '-s', '--source-system',
        metavar='SYSTEM',
        default=DEFAULT_SOURCE_SYSTEM,
        help='Source system to fetch data from, defaults to %(default)s')
    id_type_arg = parser.add_argument(
        '-t', '--id-type',
        metavar='IDTYPE',
        default=DEFAULT_EXTERNAL_ID,
        help='External ID type, defaults to %(default)s')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    get_const = functools.partial(
        Cerebrum.utils.argutils.get_constant, db, parser)
    source_system = get_const(
        co.AuthoritativeSystem, args.source_system, source_arg)
    id_type = get_const(co.EntityExternalId, args.id_type, id_type_arg)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)
    logger.info("source_system: %s", six.text_type(source_system))
    logger.info("id_type: %s", six.text_type(id_type))

    persons = list(get_persons(db, source_system, id_type))
    if not persons:
        logger.error('Found nothing to write to file')
        raise SystemExit('Found nothing to write to file')
    else:
        logger.info("Writing id and name of %d persons", len(persons))

    stream = get_output_stream(args.output, args.codec)
    write_csv_report(stream, persons)

    stream.flush()
    if stream is not sys.stdout:
        stream.close()

    logger.info('Report written to %s', stream.name)
    logger.info('Done with script %s', parser.prog)


if __name__ == "__main__":
    main()
