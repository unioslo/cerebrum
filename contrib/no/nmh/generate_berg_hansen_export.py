#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2018 University of Oslo, Norway
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

"""Generate CSV-export with users that should be imported into Berg-Hansens
travel-portal.

The output format: title, first name, last name, FEIDE id, e-mail address,
telephone number, social security number (or equivalent)."""
import argparse
import csv
import logging

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.argutils
import Cerebrum.utils.csvutils as _csvutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter

logger = logging.getLogger(__name__)


class BergHansenDialect(csv.excel):
    """Specifying the CSV output dialect the script uses.

    See the module `csv` for a description of the settings.

    """
    delimiter = ';'
    lineterminator = '\n'


def _parse_codes(db, codes):
    co = Factory.get('Constants')(db)
    if codes is None:
        return None
    elif isinstance(codes, basestring):
        return co.human2constant(codes)
    else:
        return [co.human2constant(x) for x in codes]


def _strip_n_parse_source_system(db, codes):
    co = Factory.get('Constants')(db)

    def _fuck_it(code):
        if ':' in code:
            (ss, c) = code.split(':')
            return (co.human2constant(ss), _parse_codes(db, c))
        else:
            return (None, _parse_codes(db, code))

    if codes is None:
        return None
    elif isinstance(codes, basestring):
        return _fuck_it(codes)
    else:
        return [_fuck_it(x) for x in codes]


def _construct_feide_id(db, pe):
    from Cerebrum import Errors
    ac = Factory.get('Account')(db)
    try:
        ac.find(pe.get_primary_account())
    except Errors.NotFoundError:
        return None
    return '%s@%s' % (ac.account_name, cereconf.INSTITUTION_DOMAIN_NAME)


def _get_primary_emailaddress(db, pe):
    from Cerebrum import Errors
    ac = Factory.get('Account')(db)
    try:
        ac.find(pe.get_primary_account())
        return ac.get_primary_mailaddress()
    except Errors.NotFoundError:
        return None


def _get_phone(db, pe, source_system, telephone_types):
    phones = []
    for (ss, tt) in telephone_types:
        phones.extend(
            pe.get_contact_info(
                source=ss, type=tt))

    if telephone_types:
        sort_map = dict(
            zip([int(t) for t in set([t for (s, t) in telephone_types])],
                range(len(telephone_types))))

        phones.sort(key=lambda x: sort_map[x['contact_type']])
    return None if not phones else phones[0]['contact_value']


def get_affiliated(db, source_system, affiliations):
    """Collect entity ids of persons matching filter criterias.

    :param Cerebrum.database.Database db: DB connection object.
    :param Cerebrum.Constants._AuthoritativeSystemCode source_system: Source
        system to filter by.
    :param Cerebrum.Constants._PersonAffiliationCode affiliations: Filter by
        affiliation types."""
    pe = Factory.get('Person')(db)
    for row in pe.list_affiliations(source_system=source_system,
                                    affiliation=affiliations):
        yield row['person_id']


def get_person_info(db, person, source_system,
                    telephone_types):
    """Collect information about `person`.

    :param Cerebrum.database.Database db: DB connection object.
    :param Cerebrum.Constants._EntityExternalIdCode ssn_type: External id type
        to filter by.
    :param Cerebrum.Constants._ContactInfoCode telephone_types: Filter
        telephone entries by type."""
    if isinstance(person, (int, long)):
        pe = Factory.get('Person')(db)
        pe.find(person)
    else:
        pe = person

    co = Factory.get('Constants')(db)

    return {
        'firstname': pe.get_name(source_system, co.name_first),
        'lastname': pe.get_name(source_system, co.name_last),
        'title': 'Mr' if pe.gender == co.gender_male else 'Ms',
        'feide_id': _construct_feide_id(db, pe),
        'email_address': _get_primary_emailaddress(db, pe),
        'phone': _get_phone(db, pe, source_system, telephone_types)
    }


def write_file(filename, codec, persons, skip_incomplete, skip_header=False):
    """Exports info in `persons' and generates file export `filename'.

    :param bool skip_incomplete: Don't write persons without all fields.
    :param bool skip_header: Do not write field header. Default: write header.
    :param [dict()] persons: Person information to write.
    :param basestring filename: The name of the file to write.
    """
    fields = ['title', 'firstname', 'lastname', 'feide_id', 'email_address',
              'phone']
    i = 0
    with AtomicFileWriter(filename,
                          mode='w',
                          encoding=codec.name) as stream:
        writer = _csvutils.UnicodeDictWriter(stream, fields,
                                             dialect=BergHansenDialect)

        if not skip_header:
            writer.writeheader()

        for i, person in enumerate(persons, 1):
            if skip_incomplete and not all(person.values()):
                continue
            person = dict(map(lambda t: (t[0], '' if t[1] is None else t[1]),
                              person.items()))
            writer.writerow(person)
    logger.info('Wrote %d users to file %s', i, filename)


DEFAULT_ENCODING = 'latin1'


def main(inargs=None):
    """Main script runtime.

    This parses arguments, handles the database transaction and performes the
    export.

    :param list args: List of arguments used to configure
    """
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        '-f', '--file',
        dest='filename',
        required=True,
        metavar='<filename>',
        help='Write export data to %(metavar)s')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=Cerebrum.utils.argutils.codec_type,
        help="output file encoding, defaults to %(default)s")

    parser.add_argument('-a', '--affiliations',
                        nargs='*',
                        metavar='affiliation',
                        required=True,
                        help='Affiliations to select users by')
    parser.add_argument('--source-system',
                        dest='source_system',
                        metavar='source-system',
                        help='Source systems to select name and SSN from')
    parser.add_argument('--telephone-types',
                        nargs='*',
                        metavar='phone-type',
                        help='Telephone types to export, in prioritized '
                             'order. An authorative system can be defined as '
                             'a number-source. I.e: SAP:MOBILE')
    parser.add_argument('--skip-incomplete',
                        dest='skip_incomplete',
                        action='store_true',
                        default=False,
                        help='Do not export persons that does not have all '
                             'fields')
    parser.add_argument('--skip-header',
                        dest='skip_header',
                        action='store_true',
                        default=False,
                        help='Do not write field description in export-file')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    db = Factory.get('Database')()

    logger.info("START with args: %r", args)

    write_file(args.filename,
               args.codec,
               (get_person_info(
                   db, pid,
                   _parse_codes(db, args.source_system),
                   _strip_n_parse_source_system(db, args.telephone_types))
                   for pid in set(get_affiliated(
                       db,
                       _parse_codes(db, args.source_system),
                       _parse_codes(db, args.affiliations)))),
               args.skip_incomplete,
               args.skip_header)

    logger.info("DONE")


if __name__ == '__main__':
    main()
