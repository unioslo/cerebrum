#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2005-2019 University of Oslo, Norway
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
Remove external id from a given source system

This script removes a given type of external ids from a provided source
system for all persons who has the same type of external_id
from one of the systems defined in cereconf.SYSTEM_LOOKUP_ORDER.

The script may be run for removing externalid_fodselsnr from MIGRATE
if a person at the same time has externalid_fodselsnr from e.g. SAP.

Example:

  python remove_src_extid.py -s system_fs -e externalid_fodselsnr
"""
import argparse
import logging
import sys
import time

from six import text_type
from functools import partial

from Cerebrum import Errors
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.csvutils import CerebrumDialect, UnicodeWriter

from cereconf import SYSTEM_LOOKUP_ORDER as SLO

logger = logging.getLogger(__name__)


class RemoveSrcExtid(object):
    def __init__(self, co, pe, ssys, external_id_type):
        self.co = co
        self.pe = pe
        self.ssys = ssys
        self.external_id_type = external_id_type
        self.other_ssys = [co.human2constant(s) for s in SLO if s != self.ssys]
        # self.dump = ['Removed {ext} from {ssys} for person_id:'.format(
        #     ssys=self.ssys, ext=self.external_id_type)]
        self.dump = []
        self.stream = None

    def get_persons(self):
        """
        :return generator:
            A generator that yields persons with the given id types.
        """
        logger.debug('get_persons ...')
        for row in self.pe.search_external_ids(source_system=self.ssys,
                                             id_type=self.external_id_type,
                                             entity_type=self.co.entity_person,
                                             fetchall=False):
            yield {
                'entity_id': int(row['entity_id']),
                'ext_id': int(row['external_id']),
            }

    def in_other_ssys(self):
        """
        :return bool:
            True iff external id exists in any other relevant source system
        """
        for o_ssys in self.other_ssys:
            if self.pe.get_external_id(o_ssys, self.external_id_type):
                return True
        return False

    def remover(self):
        """
        delete external id from source system if it exists in
        """
        logger.debug('start remover ...')
        i = 1
        for person in self.get_persons():
            self.pe.clear()
            self.pe.find(person['entity_id'])
            if self.in_other_ssys():
                self.pe._delete_external_id(self.ssys, self.external_id_type)
                self.dump.append(person)
            if not i%10000:
                logger.debug(' remover: Treated {} entities'.format(i))
            i += 1


    def get_output_stream(self, filename, codec):
        """ Get a unicode-compatible stream to write. """
        if filename == '-':
            self.stream = sys.stdout
        else:
            self.stream = AtomicFileWriter(filename,
                                           mode='w',
                                           encoding=codec.name)


    def write_csv_report(self):
        """ Write a CSV report to a stream.

        :param stream: file-like object that can write unicode strings
        :param persons: iterable with mappings that has keys ('ext_id', 'name')
        """
        writer = UnicodeWriter(self.stream, dialect=CerebrumDialect)
        for person in self.dump:
            writer.writerow((person['ext_id'],
                             person['entity_id'],
                             time.strftime('%m/%d/%Y %H:%M:%S')))
        self.stream.flush()
        if self.stream is not sys.stdout:
            self.stream.close()



def main(inargs=None):
    doc = (__doc__ or '').strip().split('\n')

    parser = argparse.ArgumentParser(
        description=doc[0],
        epilog='\n'.join(doc[1:]),
        formatter_class=argparse.RawTextHelpFormatter)
    source_arg = parser.add_argument(
        '-s', '--source-system',
        default='SAP',
        metavar='SYSTEM',
        help='Source system to remove id number from')
    id_type_arg = parser.add_argument(
        '-e', '--external-id-type',
        default='NO_BIRTHNO',
        metavar='IDTYPE',
        help='External ID type')
    parser.add_argument(
        '-c', '--commit',
        action='store_true',
        dest='commit',
        default=False,
        help='Commit changes (default: log changes, do not commit)'
    )
    parser.add_argument(
        '-o', '--output',
        metavar='FILE',
        default='-',
        help='The file to print the report to, defaults to stdout')
    parser.add_argument(
        '--codec',
        dest='codec',
        default='utf-8',
        type=argutils.codec_type,
        help="Output file encoding, defaults to %(default)s")

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)
    db.cl_init(change_program='remove_src_fnrs')

    get_const = partial(argutils.get_constant, db, parser)
    ssys = get_const(co.AuthoritativeSystem,
                     args.source_system,
                     source_arg)
    external_id_type = get_const(co.EntityExternalId,
                                 args.external_id_type,
                                 id_type_arg)
    logutils.autoconf('cronjob', args)
    logger.info('Start of script {}'.format(parser.prog))
    logger.debug('args: {}'.format(args))
    logger.info('source_system: {}'.format(text_type(ssys)))
    logger.info('external_id_type: {}'.format(text_type(external_id_type)))
    RSE = RemoveSrcExtid(co, pe, ssys, external_id_type)
    RSE.remover()
    RSE.get_output_stream(args.output, args.codec)
    RSE.write_csv_report()
    logger.info('Report written to %s', RSE.stream.name)
    if args.commit:
        db.commit()
        logger.debug('Committed all changes')
    else:
        db.rollback()
        logger.debug('Rolled back all changes')
    logger.info('Done with script %s', parser.prog)

if __name__ == '__main__':
    main()
