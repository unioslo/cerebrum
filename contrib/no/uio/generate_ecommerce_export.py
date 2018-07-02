#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2018 University of Oslo, Norway
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
""" Generate CSV data for IP Basware.

This file is part of the Cerebrum framework. It produces a set of CSV
files used to provision IP Basware.
"""
from __future__ import unicode_literals

import argparse
import collections
import csv
import datetime
import itertools
import io
import logging
import os
import sys

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.argutils
from Cerebrum import Errors
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import Factory
# from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.utils.csvutils import UnicodeDictWriter
from Cerebrum.utils.context import ContextPool


class BaswareDialect(csv.Dialect):
    """Describe the BASWARE CSV dialect.

    The dialect does *not* use quoting, and only applies a backslash escape
    char to the default delimiter, ';'.
    """
    # The csv module requires these to be bytestrings. Shouldn't cause any
    # problems as long as they are ascii-bytestrings.
    delimiter = str(';')
    escapechar = str('\\')
    lineterminator = str('\n')
    quoting = csv.QUOTE_NONE


logger = logging.getLogger(__name__)


DEFAULT_ENCODING = 'utf-8'
# DEFAULT_ENCODING = 'latin1'
DEFAULT_ERRORS = 'replace'


ordered_people_keys = ['use_uid', 'use_home_oun_id', 'use_supervisor_uid',
                       'use_name', 'use_domain', 'use_full_name',
                       'use_email_address', 'use_language_code',
                       'use_approval_limit', 'use_approve_own',
                       'use_send_email', 'use_move_to_substitute',
                       'use_substitute_uid', 'use_substitute_start_date',
                       'use_substitute_end_date', 'use_client_type',
                       'use_inherit_delivery_address', 'use_delivery_add_id',
                       'use_change_delivery_addr', 'use_edit_delivery_addr',
                       'use_inherit_invoicing_address', 'use_invoicing_add_id',
                       'use_change_invoicing_addr',  'use_edit_invoicing_addr',
                       'use_inherit_cost_center', 'use_cce_id',
                       'use_change_cost_center', 'use_ugr_id', 'use_enabled',
                       'use_superadmin', 'use_personnel_number',
                       'use_view_abstract_suplier', 'use_plan_approval_limit',
                       'use_t1', 'use_t2']

# user fields that should be empty
ordered_people_keys.extend(['_unused_field_%d' % i for i in range(38)])

ordered_org_keys = ['oun_id', 'oun_name', 'oun_parent_id', 'oun_type',
                    'oun_party_id', 'oun_default_delivery_party',
                    'oun_default_invoicing_party',
                    'oun_default_delivery_address',
                    'oun_default_invoice_address',
                    'oun_default_cost_center_id',
                    'oun_default_acc_currency', 'oun_acc_cur_rate',
                    'oun_acc_cur_rate_method',
                    '_unused_org_field']

ordered_role_keys = ['uro_user_uid', 'uro_id', 'uro_oun_id', 'uro_is_self',
                     '_unused_role_field']

ordered_addr_keys_1 = ['add_id_1', 'add_oun_id_1', 'add_title_1',
                       'add_is_invoicing_1', 'add_is_delivery_1',
                       '_unused_adr_field']
ordered_addr_keys_2 = ['add_id_2', 'add_oun_id_2', 'add_title_2',
                       'add_is_invoicing_2', 'add_is_delivery_2',
                       '_unused_adr_field']

ordered_addr_part_keys = ['apa_add_id', 'apa_id', 'apa_type', 'apa_text']

DEFAULT_ORG_OU_ID = 999999
DEFAULT_ORG_DATA = {
    'add_id_1': '831',
    'add_id_2': '832',
    'add_is_delivery_1': '1',
    'add_is_delivery_2': '1',
    'add_is_invoicing_1': '0',
    'add_is_invoicing_2': '0',
    'add_oun_id_1': '83',
    'add_oun_id_2': '83',
    # TODO: wrong titles? shouldn't it be add_title_1=besøk, add_title_2=post?
    'add_title_1': '83 (Toppnivå-post)',
    'add_title_2': '83 (Toppnivå-besøk)',
    'oun_acc_cur_rate': '1',
    'oun_acc_cur_rate_method': '0',
    'oun_default_acc_currency': 'NOK',
    'oun_default_cost_center_id': '83',
    'oun_default_invoicing_party': '83',
    'oun_id': '83',
    'oun_name': 'Universitetet i Oslo',
    'oun_type': '1',
}


class Repeaterable(collections.Iterable):
    """ Repeatable iterator """

    def __init__(self, iterable):
        self.iterable = iterable

    def __iter__(self):
        self.iterable, iterable = itertools.tee(self.iterable)
        return iterable

    def __repr__(self):
        return 'Repeaterable(%s)' % (repr(self.iterable), )


def get_exported_orgs(db):
    """" Get the ou_id of OUs to export.

    :return tuple: OU entity_ids
    """
    co = Factory.get("Constants")(db)
    ou = Factory.get("OU")(db)

    def find_ous():
        for row in ou.search(spread=co.spread_uio_org_ou,
                             filter_quarantined=True):
            yield int(row['ou_id'])
        yield DEFAULT_ORG_OU_ID
    return tuple(find_ous())


def iter_employees(db):
    """ Iterate over persons to consider, and their ou affiliation. """
    pe = Factory.get("Person")(db)
    co = Factory.get('Constants')(db)
    seen_persons = set()

    def employee_iter(aff, aff_status):
        return pe.list_affiliations(
            source_system=co.system_sap,
            affiliation=aff,
            status=aff_status,
            fetchall=False)

    def seen(row):
        seen = row['person_id'] in seen_persons
        seen_persons.add(row['person_id'])
        return seen

    for row in itertools.chain(
            employee_iter(co.affiliation_ansatt,
                          co.affiliation_status_ansatt_tekadm),
            employee_iter(co.affiliation_ansatt,
                          co.affiliation_status_ansatt_vit),
            employee_iter(co.affiliation_tilknyttet,
                          co.affiliation_tilknyttet_innkjoper)):
        if seen(row):
            # Only consider the first found person affiliation
            continue
        else:
            yield row['person_id'], row['ou_id']


def generate_people_info(db, exported_orgs):
    """ Generate user data.

    :param exported_orgs:
        A list or tuple with ou_id of OUs to export (from get_exported_orgs())

    :return generator:
        A generator that yields user dicts
    """
    co = Factory.get('Constants')(db)
    context = ContextPool(db)

    logger.debug('fetching account quarantines ...')
    quarantined_accounts = QuarantineHandler.get_locked_entities(
        db, entity_types=co.entity_account)
    logger.debug('... got %d quarantines', len(quarantined_accounts))

    def get_primary_contact(person, contact_type):
        for row in person.get_contact_info(source=co.system_sap,
                                           type=contact_type):
            return row['contact_value']
        return ''

    def get_primary_email(account):
        try:
            return account.get_primary_mailaddress()
        except Errors.NotFoundError:
            return ''

    logger.debug('fetching employee data...')
    for person_id, ou_id in iter_employees(db):

        with context.ou.find(ou_id) as ou:
            use_home_oun_id = six.text_type(ou)
            if ou.entity_id not in exported_orgs:
                logger.warn("Skipping %s, connected to non-exported OU %s",
                            person_id, use_home_oun_id)
                # if a person is connected to a non-exported org unit,
                # do not export
                continue

        with context.person.find(person_id) as pe:
            primary_account_id = pe.get_primary_account()
            if not primary_account_id:
                logger.info("Skipping %s, no primary account found", person_id)
                continue

            with context.account.find(primary_account_id) as account:
                account_name = account.account_name
                email_address = get_primary_email(account)

            if not email_address:
                logger.info("No primary e-mail address found for %s",
                            account_name)

            no_sap_nr = pe.get_external_id(
                source_system=co.system_sap,
                id_type=co.externalid_sap_ansattnr)[0]['external_id']

            enabled = int(primary_account_id not in quarantined_accounts)
            person_name_full = pe.get_name(co.system_cached, co.name_full)
            contact_phone = get_primary_contact(pe, co.contact_phone)
            contact_fax = get_primary_contact(pe, co.contact_fax)

        yield {
            'uro_id': 'DUMMY1',
            'uro_oun_id': use_home_oun_id,
            'uro_user_uid': no_sap_nr,
            'use_change_cost_center': '1',
            'use_change_delivery_addr': '1',
            'use_change_invoicing_addr': '0',
            'use_client_type': '2',
            'use_edit_delivery_addr': '1',
            'use_email_address': email_address,
            'use_enabled': six.text_type(enabled),
            'use_full_name': person_name_full,
            'use_home_oun_id': use_home_oun_id,
            'use_inherit_cost_center': '0',
            'use_inherit_delivery_address': '1',
            'use_inherit_invoicing_address': '1',
            'use_language_code': 'NO',
            'use_name': account_name,
            'use_send_email': '1',
            'use_t1': contact_phone,
            'use_t2': contact_fax,
            'use_uid': no_sap_nr,
            'use_view_abstract_suplier': '0',
        }

    logger.debug("done fetching employee data")


def generate_ou_info(db, exported_orgs):
    """ Generate OU data.

    :param listorg_units:
        A dict with OUs to export (from get_exported_orgs())

    :return generator:
        A generator that yields ou dicts
    """
    co = Factory.get('Constants')(db)
    context = ContextPool(db)

    def get_parent_id(parent_id):
        try:
            with context.ou.find(parent_id) as parent:
                if parent_id and parent_id in exported_orgs:
                    return six.text_type(parent)
                else:
                    return get_parent_id(parent.get_parent(co.perspective_sap))
        except Errors.NotFoundError:
            return None

    def get_org_level(parent_id, level):
        with context.ou.find(parent_id) as parent:
            parent_id = parent.get_parent(co.perspective_sap)
            if parent_id is None:
                return level
            else:
                return get_org_level(int(parent_id), level + 1)

    def get_ou_name(ou):
        for row in ou.search_name_with_language(
            entity_id=ou.entity_id,
            name_language=co.language_nb,
                name_variant=co.ou_name_display):
            return row['name']
        raise ValueError("No name for ou_id=%r" % (ou.entity_id, ))

    logger.debug('fetching ou data...')
    for ou_id in exported_orgs:
        if ou_id == DEFAULT_ORG_OU_ID:
            # the default ou is hard coded
            continue

        oun_parent_id = None
        oun_type = None
        count_level = 1

        with context.ou.find(ou_id) as ou:
            oun_id = six.text_type(ou)
            oun_name = get_ou_name(ou)
            parent_id = ou.get_parent(co.perspective_sap)
            # No direct parent is registered for ou
            if not parent_id or parent_id not in exported_orgs:
                logger.info("No parent for ou %s, exporting default values"
                            " for oun_type and oun_parent_id", oun_id)
                # TODO: this seems wrong, should this not be
                #       DEFAULT_ORG_DATA['oun_id']?
                oun_parent_id = six.text_type(DEFAULT_ORG_OU_ID)
            else:
                oun_parent_id = get_parent_id(int(parent_id))
                count_level = get_org_level(int(parent_id), count_level)
            if count_level < 3:
                oun_type = '2'
            else:
                oun_type = '0'
            if oun_type == '2':
                oun_parent_id = '83'

        yield {
            # _ou_id is only used by 'generate_addr_parts_info'
            '_ou_id': ou_id,
            'add_id_1': oun_id + '1',
            'add_id_2': oun_id + '2',
            'add_is_delivery_1': '1',
            'add_is_delivery_2': '1',
            'add_is_invoicing_1': '0',
            'add_is_invoicing_2': '0',
            'add_oun_id_1': oun_id,
            'add_oun_id_2': oun_id,
            'add_title_1': oun_id + '-Besøk',
            'add_title_2': oun_id + '-Post',
            'oun_acc_cur_rate': '1',
            'oun_acc_cur_rate_method': '0',
            'oun_default_acc_currency': 'NOK',
            'oun_default_cost_center_id': '83',
            # default delivery address er besøksadresse
            'oun_default_delivery_address': oun_id + '1',
            'oun_default_invoicing_party': '83',
            'oun_id': oun_id,
            'oun_name': oun_id + ' - ' + oun_name,
            'oun_parent_id': oun_parent_id,
            'oun_type': oun_type,
        }
    # and the default OU...
    yield DEFAULT_ORG_DATA
    logger.debug("done fetching ou data")


def generate_addr_parts_info(db, ous):
    """ Generate OU data.

    :param ous:
        An iterable of ou_info (from generate_ou_info)

    :return generator:
        A generator that yields address dicts
    """
    co = Factory.get('Constants')(db)
    context = ContextPool(db)

    def get_address(ou, addr_type, name=''):
        address = {'address_text': '', 'city': '', 'postal_number': ''}
        for row in ou.get_entity_address(
                source=co.system_sap,
                type=addr_type):
            for key in address:
                address[key] = row[key]
            return address
        logger.warning(
            "OU %s (sko=%r, ou_id=%r) missing address of type %s",
            ou_name, six.text_type(ou), ou.entity_id, six.text_type(addr_type))
        return address

    logger.debug('fetching address data...')
    for ou_data in ous:
        if '_ou_id' not in ou_data:
            # TODO: Should there not be address data for the default OU?
            logger.debug("Skipping default ou: %s", ou_data['oun_id'])
            continue
        ou_id = ou_data['_ou_id']

        with context.ou.find(ou_id) as ou:
            sko = six.text_type(ou)

            ou_name = ou.get_name_with_language(
                name_variant=co.ou_name,
                name_language=co.language_nb,
                default="")

            # post
            apa_add_id = sko + '2'
            addr = get_address(ou, co.address_post, name=ou_name)
            pobox = addr['address_text'].split('\n')

            for e in ['Name1:0', 'Name2:1', 'POBox:3', 'Street1:4',
                      'Department:12', 'Postalcode:13', 'City:14']:
                apa_id, apa_type = e.split(':')
                if apa_id == 'Name1':
                    apa_text = 'Universitetet i Oslo'
                elif apa_id == 'Name2':
                    apa_text = ou_name
                elif apa_id == 'POBox':
                    apa_text = pobox[0]
                elif apa_id == 'Street1':
                    apa_text = pobox[1] if len(pobox) == 2 else ''
                elif apa_id == 'Department':
                    apa_text = apa_add_id
                elif apa_id == 'Postalcode':
                    apa_text = 'NO-' + addr['postal_number']
                elif apa_id == 'City':
                    apa_text = addr['city']

                yield {
                    'apa_add_id': apa_add_id,
                    'apa_id': apa_id,
                    'apa_type': apa_type,
                    'apa_text': apa_text,
                }

            # besøk
            apa_add_id = sko + '1'
            addr = get_address(ou, co.address_street, name=ou_name)
            street = addr['address_text'].split('\n')

            for e in ['Name1:0', 'Name2:1', 'Street1:4', 'Street2:6',
                      'Department:12', 'Postalcode:13', 'City:14']:
                apa_id, apa_type = e.split(':')
                if apa_id == 'Name1':
                    apa_text = 'Universitetet i Oslo'
                elif apa_id == 'Name2':
                    apa_text = ou_name
                elif apa_id == 'Street1':
                    apa_text = street[0]
                elif apa_id == 'Street2':
                    apa_text = street[1] if len(street) == 2 else ''
                elif apa_id == 'Department':
                    apa_text = apa_add_id
                elif apa_id == 'Postalcode':
                    apa_text = 'NO-' + addr['postal_number']
                elif apa_id == 'City':
                    apa_text = addr['city']

                yield {
                    'apa_add_id': apa_add_id,
                    'apa_id': apa_id,
                    'apa_type': apa_type,
                    'apa_text': apa_text,
                }
    logger.debug("done fetching address data")


def filtered_defaultdict(d, keys):
    """ Wrap a dict for writing with the CSV writer.

    1. unused keys are filtered out - otherwise the csv writer will complain
       about unused keys.
    2. provide a default empty string value for undefined keys
    """
    return collections.defaultdict(
        six.text_type,
        filter(lambda t: t[0] in keys, d.items()))


def write_users_file(filename, employees,
                     encoding=DEFAULT_ENCODING,
                     errors=DEFAULT_ERRORS):
    with io.open(filename, 'w', encoding=encoding, errors=errors) as stream:
        writer = UnicodeDictWriter(stream,
                                   ordered_people_keys,
                                   dialect=BaswareDialect)
        for person_data in employees:
            writer.writerow(
                filtered_defaultdict(person_data, ordered_people_keys))
        logger.info('wrote users to %r', stream.name)


def write_roles_file(filename, employees,
                     encoding=DEFAULT_ENCODING,
                     errors=DEFAULT_ERRORS):
    with io.open(filename, 'w', encoding=encoding, errors=errors) as stream:
        writer = UnicodeDictWriter(stream,
                                   ordered_role_keys,
                                   dialect=BaswareDialect)
        for person_data in employees:
            writer.writerow(
                filtered_defaultdict(person_data, ordered_role_keys))
        logger.info('wrote roles to %r', stream.name)


def write_org_file(filename, ous,
                   encoding=DEFAULT_ENCODING,
                   errors=DEFAULT_ERRORS):
    with io.open(filename, 'w', encoding=encoding, errors=errors) as stream:
        writer = UnicodeDictWriter(stream,
                                   ordered_org_keys,
                                   dialect=BaswareDialect)
        for ou_data in ous:
            writer.writerow(
                filtered_defaultdict(ou_data, ordered_org_keys))
        logger.info('wrote ou data to %r', stream.name)


def write_addr_file(filename, ous,
                    encoding=DEFAULT_ENCODING,
                    errors=DEFAULT_ERRORS):
    with io.open(filename, 'w', encoding=encoding, errors=errors) as stream:
        write_keys_1 = UnicodeDictWriter(stream,
                                         ordered_addr_keys_1,
                                         dialect=BaswareDialect)
        write_keys_2 = UnicodeDictWriter(stream,
                                         ordered_addr_keys_2,
                                         dialect=BaswareDialect)
        for ou_data in ous:
            write_keys_1.writerow(
                filtered_defaultdict(ou_data, ordered_addr_keys_1))
            write_keys_2.writerow(
                filtered_defaultdict(ou_data, ordered_addr_keys_2))
        logger.info('wrote address indexes to %r', stream.name)


def write_part_file(filename, ous,
                    encoding=DEFAULT_ENCODING,
                    errors=DEFAULT_ERRORS):
    with io.open(filename, 'w',
                 encoding=encoding,
                 errors=errors) as stream:
        writer = UnicodeDictWriter(stream,
                                   ordered_addr_part_keys,
                                   dialect=BaswareDialect)
        for ou_data in ous:
            data = filtered_defaultdict(ou_data, ordered_addr_part_keys)
            writer.writerow(data)
        logger.info('wrote address data to %r', stream.name)


def get_default_dumpdir():
    return os.path.join(
        '' if sys.prefix == '/usr' else sys.prefix,
        'var', 'cache', 'BASWAREPM')


def make_filename(suffix):
    return '{date}-{suffix}.csv'.format(
        date=datetime.datetime.now().strftime('%Y%m%d'),
        suffix=suffix)


def main(inargs=None):

    # Make default filenames with date prefix
    user_filename = make_filename('User')
    roles_filename = make_filename('Roles')
    org_filename = make_filename('Org')
    adr_filename = make_filename('Adr')
    adr_part_filename = make_filename('AdrPart')

    dump_directory = get_default_dumpdir()

    # TODO: Rework the arguments to make it more convenient for testing.
    # dump_directory = 'basware'

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p', '--gen-person-file',
        const=['users', 'roles'],
        dest='exports',
        type=set,
        action=Cerebrum.utils.argutils.ExtendConstAction,
        help='generate users and roles (%s, %s)'
              % (user_filename, roles_filename))
    parser.add_argument(
        '-o', '--gen-organization-files',
        const=['org', 'addr', 'parts'],
        dest='exports',
        type=set,
        action=Cerebrum.utils.argutils.ExtendConstAction,
        help='generate organization files (%s, %s, %s)'
              % (org_filename, adr_filename, adr_part_filename))
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        type=Cerebrum.utils.argutils.codec_type,
        default=DEFAULT_ENCODING,
        help="encoding of CSV files")

    filenames = parser.add_argument_group(
        'Files',
        'Override the default file placement')
    filenames.add_argument(
        '--users-file',
        default=os.path.join(dump_directory, user_filename),
        metavar='FILE',
        help='CSV file for users, default is %(default)s')
    filenames.add_argument(
        '--roles-file',
        default=os.path.join(dump_directory, roles_filename),
        metavar='FILE',
        help='CSV file for roles, default is %(default)s')
    filenames.add_argument(
        '--org-file',
        default=os.path.join(dump_directory, org_filename),
        metavar='FILE',
        help='CSV file for OU data, default is %(default)s')
    filenames.add_argument(
        '--addr-file',
        default=os.path.join(dump_directory, adr_filename),
        metavar='FILE',
        help='CSV file for address indexes, default is %(default)s')
    filenames.add_argument(
        '--part-file',
        default=os.path.join(dump_directory, adr_part_filename),
        metavar='FILE',
        help='CSV file for address data, default is %(default)s')

    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)
    logger.info("exports: %s", ', '.join(sorted(args.exports)))

    db = Factory.get("Database")()

    # orgs to export
    exported_orgs = get_exported_orgs(db)

    # iterable data
    employees = Repeaterable(generate_people_info(db, exported_orgs))
    ous = Repeaterable(generate_ou_info(db, exported_orgs))
    addrs = Repeaterable(generate_addr_parts_info(db, ous))

    if 'users' in args.exports:
        logger.info("Generating users file")
        write_users_file(args.users_file, employees, encoding=args.codec.name)

    if 'roles' in args.exports:
        logger.info("Generating roles file")
        write_roles_file(args.roles_file, employees, encoding=args.codec.name)

    if 'org' in args.exports:
        logger.info("Generating OU file")
        write_org_file(args.org_file, ous, encoding=args.codec.name)

    if 'addr' in args.exports:
        logger.info("Generating address index file")
        write_addr_file(args.addr_file, ous, encoding=args.codec.name)

    if 'parts' in args.exports:
        logger.info("Generating address data file")
        write_part_file(args.part_file, addrs, encoding=args.codec.name)

    logger.info('Done with script %s', parser.prog)


if __name__ == "__main__":
    main()
