#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2018 University of Oslo, Norway
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
import argparse
import csv
import logging
import os
import sys

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.argutils
import Cerebrum.utils.csvutils
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.utils.atomicfile import SimilarSizeWriter

logger = logging.getLogger(__name__)


class KvernfileDialect(csv.excel):
    """Specifying the CSV output dialect the script uses.

    See the module `csv` for a description of the settings.
    """
    delimiter = '$'
    lineterminator = '\n'

    # TODO: Agree on escaping/quoting with ofk -- as we currently don't produce
    # an actual parseable CSV file...


class CsvUnicodeWriter(Cerebrum.utils.csvutils.UnicodeDictWriter):
    pass


def format_email(row):
    return '{local_part}@{domain}'.format(**dict(row))


class PersonLookup(object):

    def __init__(self, db):
        """ Cache data for this iterable object. """
        co = Factory.get('Constants')(db)
        ac = Factory.get('Account')(db)
        pe = Factory.get('Person')(db)
        ou = Factory.get('OU')(db)
        et = Email.EmailTarget(db)

        self.db = db

        logger.debug("caching spreads ...")
        self.account_spreads = set((
            row['entity_id']
            for row in ac.list_all_with_spread(co.spread_oid_acc)))
        self.ou_spreads = set((
            row['entity_id']
            for row in ou.list_all_with_spread(co.spread_oid_ou)))

        logger.debug("... email addresses ...")
        self.account_id_to_email = dict(
            (int(row['target_entity_id']),
             format_email(row))
            for row in et.list_email_target_primary_addresses())

        logger.debug("... names ...")
        self.person_id_to_name = pe.getdict_persons_names(
            source_system=co.system_cached,
            name_types=(co.name_first, co.name_last))

        logger.debug("... external ids ...")
        self.person_id_to_extid = dict(
            (int(row['entity_id']), row['external_id'])
            for row in pe.search_external_ids(id_type=co.externalid_fodselsnr,
                                              fetchall=False))

        logger.debug("... auth data ...")
        self.account_id_to_auth = dict()
        for row in ac.list_account_authentication(
                auth_type=(co.auth_type_md4_nt,
                           co.auth_type_plaintext)):
            account_id = int(row['account_id'])
            if row['method'] is None:
                continue
            if account_id not in self.account_id_to_auth:
                self.account_id_to_auth[account_id] = [row['entity_name'],
                                                       dict()]
            self.account_id_to_auth[account_id][1].setdefault(
                int(row['method']),
                row['auth_data'])

        logger.debug("... account data ...")
        self.person_id_to_account_id = dict(
            (int(row['person_id']), int(row['account_id']))
            for row in ac.list_accounts_by_type(primary_only=True))

        logger.debug("... ou data ...")
        self.ou_id_to_name = dict(
            (r["entity_id"], r["name"])
            for r in ou.search_name_with_language(
                entity_type=co.entity_ou,
                name_variant=co.ou_name_acronym,
                name_language=co.language_nb))
        logger.debug("... done caching data")

    def _person_iterator(self):
        """ Returns a generator that iterates over exportable persons. """
        co = Factory.get('Constants')(self.db)
        pe = Factory.get('Person')(self.db)

        for row in pe.list_affiliations():
            person_id = int(row['person_id'])
            ou_id = int(row['ou_id'])

            account_id = self.person_id_to_account_id.get(person_id, None)

            if account_id is None:
                # no user
                logger.info("No user found for %r", person_id)
                continue

            ext_id = self.person_id_to_extid.get(person_id, None)
            if ext_id is None:
                logger.warning("Fnr not found for %r", person_id)
                continue

            uname, auth_data = self.account_id_to_auth.get(account_id,
                                                           [None, dict()])
            if uname is None:
                # No username
                logger.warning("ptf: No user found for person %r", person_id)
                continue

            if auth_data:
                pwd = auth_data[int(co.auth_type_plaintext)]
            else:
                pwd = ""

            names = self.person_id_to_name.get(person_id, dict())
            if not all(int(name_variant) in names
                       for name_variant in (co.name_first, co.name_last)):
                logger.warning("Names not found for person id=%r", person_id)
                continue
            first = names[int(co.name_first)]
            last = names[int(co.name_last)]

            ou_name = self.ou_id_to_name.get(ou_id, None)
            if ou_name is None:
                logger.warning("OU name not found for %r", ou_id)
                continue

            email_addr = self.account_id_to_email.get(account_id, None)
            if email_addr is None:
                logger.warning("Mail-addr not found for %r, %r",
                               person_id, uname)
                continue

            yield {
                'ext_id': ext_id,
                'username': uname,
                'password': pwd,
                'email': email_addr,
                'ou': ou_name,
                'firstname': first,
                'lastname': last,
            }

    def __iter__(self):
        return iter(self._person_iterator())


def write_csv_export(stream, iterator):
    fields = ['ext_id', 'username', 'password',
              'email', 'ou', 'firstname', 'lastname', ]
    # writer = CsvUnicodeWriter(stream,
    #                           dialect=KvernfileDialect,
    #                           fieldnames=fields)
    delim = six.text_type(KvernfileDialect.delimiter)
    linesep = six.text_type(KvernfileDialect.lineterminator)
    count = 0
    for count, user in enumerate(iterator, 1):
        line = delim.join((user[field] for field in fields))
        stream.write(line + linesep)
        # writer.writerow(user)
    logger.info("Wrote %d users", count)


DEFAULT_EXPORT_DIR = os.path.join(sys.prefix, 'var/cache/txt')
DEFAULT_FILENAME = 'ofk.txt'
DEFAULT_ENCODING = 'latin1'


def writable_dir_type(value):
    value = os.path.abspath(value)
    if not all((os.path.isdir(value),
                os.access(value, os.R_OK | os.X_OK))):
        raise ValueError("not a writable directory")
    return value


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)

    # TODO: change to the actual filename...
    parser.add_argument(
        '-t', '--txt-path',
        dest='export_dir',
        type=writable_dir_type,
        default=DEFAULT_EXPORT_DIR,
        metavar='DIR',
        help='Write export data to %(metavar)s')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=Cerebrum.utils.argutils.codec_type,
        help="output file encoding, defaults to %(default)s")

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    filename = os.path.join(args.export_dir, DEFAULT_FILENAME)

    db = Factory.get('Database')()

    persons = PersonLookup(db)

    # Dump OFK info
    with SimilarSizeWriter(filename,
                           mode="w",
                           encoding=args.codec.name) as f:
        f.max_pct_change = 10
        write_csv_export(f, persons)

    logger.info('Report written to %s', filename)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
