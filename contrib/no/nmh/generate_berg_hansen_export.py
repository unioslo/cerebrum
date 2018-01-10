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

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter

logger = Factory.get_logger('cronjob')


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


def _get_ssn(db, pe, ssn_type, source_system):
    ssns = pe.get_external_id(id_type=ssn_type,
                              source_system=source_system)
    return None if not ssns else ssns[0]['external_id']


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


def get_person_info(db, person, ssn_type, source_system,
                    telephone_types):
    """Collect information about `person`.

    :param Cerebrum.database.Database db: DB connection object.
    :param Cerebrum.Constants._EntityExternalIdCode ssn_type: External id type
        to filter by.
    :param Cerebrum.Constants._AuthoritativeSystemCode source_system: Source
        system to filter by.
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
        'phone': _get_phone(db, pe, source_system, telephone_types),
        'ssn': _get_ssn(db, pe, ssn_type, source_system)
    }


def write_file(filename, persons, skip_incomplete, skip_header=False):
    """Exports info in `persons' and generates file export `filename'.

    :param bool skip_incomplete: Don't write persons without all fields.
    :param bool skip_header: Do not write field header. Default: write header.
    :param [dict()] persons: Person information to write.
    :param basestring filename: The name of the file to write."""
    from string import Template
    f = AtomicFileWriter(filename)
    i = 0
    if not skip_header:
        f.write(
            'title;firstname;lastname;feide_id;'
            'email_address;phone;ssn\n')
    for person in persons:
        if skip_incomplete and not all(person.values()):
            continue
        person = dict(map(lambda (x, y): (x, '' if y is None else y),
                          person.iteritems()))
        f.write(
            Template('$title;$firstname;$lastname;$feide_id;'
                     '$email_address;$phone;$ssn\n').substitute(person))
        i += 1
    f.close()
    logger.info('Wrote %d users to file %s', i, filename)


def main(args=None):
    """Main script runtime.

    This parses arguments, handles the database transaction and performes the
    export.

    :param list args: List of arguments used to configure
    """
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-f', '--file',
                        dest='filename',
                        required=True,
                        metavar='filename',
                        help='Write export data to <filename>')

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
    parser.add_argument('--ssn-type',
                        dest='ssn_type',
                        required=True,
                        metavar='ssn-type',
                        help='SSN type to select. I.e NO_BIRTHNO')
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

    args = parser.parse_args(args)

    logger.info("START with args: %s" % str(args.__dict__))

    db = Factory.get('Database')()

    write_file(args.filename,
               (get_person_info(
                   db, pid,
                   _parse_codes(db, args.ssn_type),
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
