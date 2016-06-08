#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2016 University of Oslo, Norway
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

"""Consumes events from SAP and updates Cerebrum."""

from Cerebrum.Utils import Factory
from Cerebrum.modules.event.mapping import CallbackMap

logger = Factory.get_logger('cronjob')
callback_functions = CallbackMap()
callback_filters = CallbackMap()


filter_meta = lambda l: dict(
    filter(lambda (k, _): k != '__metadata', l.items()))
translate_keys = lambda d, m: dict(
    map(lambda (k, v): (m.get(k, None), v), d.items()))
filter_elements = lambda d:     filter(lambda (k, _): k, d.items())


class RemoteSourceDown(Exception):
    """Exception signaling that the remote system is out of service."""


def parse_address(d):
    """Parse the data from SAP an return a diff-able structure.

    :type d: dict
    :param d: Data from SAP

    :rtype: tuple(
        (AddressCode,
         ('city', 'OSLO'),
         ('postal_number', 0316),
         ('address_text', 'Postboks 1059 Blindern')))
    :return: A tuple with the fields that should be updated"""
    co = Factory.get('Constants')
    r = d.get('Address')
    m = {'ResidentialAddress': co.address_post_private,
         'PostalAddress': co.address_post,
         'VisitingAddress': co.address_street,

         'City': 'city',
         'PostalCode': 'postal_number',
         'StreetAndHouseNumber': 'address_text'}

    # Visiting address should be a concoction of real address and a
    # meta-location
    r['VisitingAddress']['StreetAndHouseNumber'] = '{}\n{}'.format(
        r.get('VisitingAddress').get('StreetAndHouseNumber'),
        r.get('VisitingAddress').get('Location'))

    return tuple([(k, tuple(filter_elements(translate_keys(v, m)))) for
                  (k, v) in filter_elements(
                      translate_keys(filter_meta(r), m))])


def parse_names(d):
    """Parse data from SAP and return names.

    :type d: dict
    :param d: Data from SAP

    :rtype: tuple((PersonName('FIRST'), 'first'),
                  (PersonName('FIRST'), 'last'))
    :return: A tuple with the fields that should be updated"""

    co = Factory.get('Constants')
    return ((co.name_first, d.get('FirstName')),
            (co.name_last, d.get('LastName')))


def parse_contacts(d):
    """Parse data from SAP and return contact information.

    :type d: dict
    :param d: Data from SAP

    :rtype: (ContactInfo('PHONE'), ''),
             ContactInfo('MOBILE_PHONE'), ''),
             ContactInfo('MOBILE'), ''),
             ContactInfo('PRIVATEMOBILE'), ''),
             ContactInfo('PRIVMOBVISIBLE'), '')
    :return: A tuple with the fields that should be updated"""
    co = Factory.get('Constants')
    c = d.get('Communication')
    # TODO: Validate/clean numbers with phonenumbers?
    m = {'Phone1': co.contact_phone,
         'Phone2': co.contact_phone,
         'Mobile': co.contact_mobile_phone,
         'MobilePrivate': co.contact_private_mobile,
         'MobilePublic': co.contact_private_mobile_visible}

    return filter_elements(translate_keys(c, m))


def parse_titles(d):
    """Parse data from SAP and return person titles.

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(('name_variant', EntityNameCode('PERSONALTITLE')),
                   ('name_language', LanguageCode('en')),
                   ('name', 'Over Engingineer'))]
    :return: A list of tuples with the fields that should be updated"""
    co = Factory.get('Constants')

    def make_tuple(variant, lang, name):
        return (('name_variant', variant),
                ('name_language', lang),
                ('name', name))
    titles = ([
        make_tuple(co.personal_title,
                   co.language_en,
                   d.get('Title').get('English'))] +
              map(lambda lang: make_tuple(co.personal_title,
                                          lang,
                                          d.get('Title').get('Norwegian')),
                  [co.language_nb, co.language_nn]))

    # Select appropriate work title.
    work_title = None
    for e in d.get('Employments').get('results', []):
        if e.get('IsMain'):
            work_title = e
            break
        if (e.get('EmploymentPercentage') >
                work_title.get('EmploymentPercentage') or
                not work_title):
            work_title = e

    return titles + map(lambda (lang_code, lang_str): make_tuple(
        co.work_title,
        lang_code,
        work_title.get('Job').get('Title').get(lang_str)),
        [(co.language_nb, 'Norwegian'),
         (co.language_nn, 'Norwegian'),
         (co.language_en, 'English')])


def parse_external_ids(source_system, d):
    """Parse data from SAP and return external ids (i.e. passnr).

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(('id_type', EntityExternalId('PASSNR')),
                   ('source_system', AuthoritativeSystem('SAP')),
                   ('external_id', '000001'))]
    :return: A list of tuples with the fields that should be updated"""
    co = Factory.get('Constants')

    def make_tuple(id_type, source_system, value):
        return (('id_type', id_type),
                ('source_system', source_system),
                ('external_id', value))

    external_ids = [
        make_tuple(co.externalid_sap_ansattnr,
                   source_system,
                   d.get('PersonID'))]

    passport = d.get('PersonalDetails').get('InternationalID').get('Passport')
    if passport.get('Country') and passport.get('IdentityNumber'):
        external_ids.append(
            make_tuple(co.externalid_pass_number,
                       source_system,
                       (passport.get('Country') +
                        passport.get('IdentityNumber'))))

    if d.get('PersonalDetails').get('NationalID'):
        external_ids.append(
            make_tuple(co.externalid_fodselsnr,
                       source_system,
                       d.get('PersonalDetails').get('NationalID')))

    return external_ids


def parse_affiliations(database, d):
    """Parse data from SAP and return names.

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(('ou_id': 3),
                   ('affiliation', PersonAffiliation('ANSATT')),
                   ('status', PersonAffStatus('ANSATT', 'tekadm')),
                   (precedence', (50, 50)))]
    :return: A list of tuples with the fields that should be updated"""
    import cereconf
    co = Factory.get('Constants')
    ou = Factory.get('OU')(database)

    for x in d.get('Employments').get('results'):
        status = {'T/A': co.affiliation_status_ansatt_tekadm,
                  'Vit': co.affiliation_status_ansatt_vitenskapelig}.get(
                      x.get('Job').get('Category'))

        ou.find_stedkode(
            *map(''.join, zip(*[iter(x.get('OrganizationalUnit'))]*2)) +
            [cereconf.DEFAULT_INSTITUSJONSNR])
        main = x.get('IsMain')
        yield {'ou_id': ou.entity_id,
               'affiliation': co.affiliation_ansatt,
               'status': status,
               'precedence': (50L, 50L) if main else None}


def _parse_hr_person(database, source_system, data):
    from mx import DateTime
    co = Factory.get('Constants')

    return {
        'addresses': parse_address(data),
        'names': parse_names(data),
        'birth_date': DateTime.DateFrom(
            data.get('PersonalDetails').get('DateOfBirth')),
        'gender': {'Kvinne': co.gender_female,
                   'Mann': co.gender_male}.get(
                       data.get('PersonalDetails').get('Gender'),
                       co.gender_unknown),
        'external_ids': parse_external_ids(source_system, data),
        'contacts': parse_contacts(data),
        'affiliations': parse_affiliations(database, data),
        'titles': parse_titles(data),
        'reserved': data.get('PublicView')}


def get_hr_person(database, source_system, url, identifier):
    """Collect a person entry from the remote source system, and parse the data.

    :param db: Database object
    :param source_system: The source system code
    :param url: The URL to contact for collection
    :param identifier: The id of the object to collect

    :rtype: dict
    :return The parsed data from the remote source system

    :raises: RemoteSourceDown if the remote system can't be contacted"""
    import requests
    import json

    r = requests.get(url)
    if r.status_code == 200:
        data = json.loads(r.text).get('d', None)
        return _parse_hr_person(database, source_system, data)
    else:
        logger.error('Could not fetch {} from remote source: {}: {}').format(
            identifier, r.status_code, r.reason)
        raise RemoteSourceDown


def get_cerebrum_person(database, identifier):
    """Get a person object from Cerebrum.

    If the person does not exist in Cerebrum, the returned object is
    clear()'ed"""
    pe = Factory.get('Person')(database)
    co = Factory.get('Constants')(database)
    from Cerebrum import Errors
    try:
        pe.find_by_external_id(co.externalid_sap_ansattnr, str(identifier))
        logger.debug('Found existing person with id:{}'.format(pe.entity_id))
    except Errors.NotFoundError:
        logger.debug(
            'Could not find existing person for external_id:{}'.format(
                identifier))
        pe.clear()
    return pe


def _stringify_for_log(data):
    from Cerebrum.Constants import _CerebrumCode
    import collections
    if isinstance(data, _CerebrumCode):
        return str(data)
    elif isinstance(data, basestring):
        return data
    elif isinstance(data, collections.Mapping):
        return dict(map(_stringify_for_log, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(_stringify_for_log, data))
    else:
        return data


def update_person(database, source_system, hr_person, cerebrum_person):
    """Update person with birth date and gender."""
    cerebrum_person.populate(
        hr_person.get('birth_date'),
        hr_person.get('gender'))
    cerebrum_person.write_db()

    logger.debug('Added birth date {} and gender {} for {}'.format(
        hr_person.get('birth_date'),
        hr_person.get('gender'),
        cerebrum_person.entity_id))


def update_affiliations(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with the latest affiliations.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    for affiliation in hr_person.get('affiliations'):
        cerebrum_person.populate_affiliation(source_system, **affiliation)
        logger.debug('Adding affiliation {} for id:{}'.format(
            _stringify_for_log(affiliation), cerebrum_person.entity_id))


def update_names(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with fresh names.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    co = Factory.get('Constants')(database)
    names = map(lambda name_type:
                (name_type,
                 cerebrum_person.get_name(
                     source_system,
                     name_type)),
                [co.name_first, co.name_last])

    to_remove = set(hr_person.get('names')) - names
    to_add = names - set(hr_person.get('names'))

    cerebrum_person.affect_names(source_system,
                                 map(lambda (k, _): k, to_remove | to_add))
    logger.debug('Purging names of types {} for id:{}'.format(
        map(lambda (k, _): k, to_remove), cerebrum_person.entity_id))

    for (k, v) in to_add:
        cerebrum_person.populate_name(k, v)
        logger.debug('Adding name {} for id:{}'.format(
            (k, v), cerebrum_person.entity_id))


# Transform list of db_rows to a set of (address_type, (('city': '', …)))
row_transform = (lambda key_type, key_label, squash_keys, elements:
                 set(map(lambda e:
                         (key_type(e[key_label]),
                          tuple(filter(lambda (k, _): k not in squash_keys,
                                       e.items()))),
                         elements)))


def update_external_ids(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with appropriate external ids.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    co = Factory.get('Constants')(database)

    hr_person.get('external_ids')

    external_ids = row_transform(
        co.EntityExternalId,
        'id_type',
        'id_type',
        cerebrum_person.get_external_id(source_system=source_system))

    to_remove = hr_person.get('external_ids') - external_ids
    to_add = external_ids - hr_person.get('external_ids')

    cerebrum_person.affect_external_id(
        source_system,
        map(lambda (k, _): k, to_remove | to_add))
    logger.debug('Purging externalids of types {} for id:{}'.format(
        map(lambda (k, _): k, to_remove), cerebrum_person.entity_id))

    for (k, v) in to_add:
        cerebrum_person.populate_external_id(
            source_system, k, v)
        logger.debug('Adding externalid {} for id:{}'.format(
            (k, v), cerebrum_person.entity_id))


def update_addresses(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with addresses.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    co = Factory.get('Constants')(database)
    addresses = row_transform(co.Address,
                              'address_type',
                              ('entity_id', 'source_system', 'address_type'),
                              cerebrum_person.get_entity_address(
                                  source=source_system))

    for (k, v) in set(hr_person.get('addresses')) - addresses:
        cerebrum_person.add_entity_address(source_system, k, **dict(v))
        logger.debug('Adding address {} for id:{}'.format(
            (_stringify_for_log(k), v), cerebrum_person.entity_id))

    for (k, v) in addresses - set(hr_person.get('addresses')):
        cerebrum_person.delete_entity_address(source_system, k)
        logger.debug('Removing address {} for id:{}'.format(
            (_stringify_for_log(k), v), cerebrum_person.entity_id))


def update_contact_info(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with contact information (telephone, etc.).

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    co = Factory.get('Constants')(database)
    contacts = row_transform(co.ContactInfo,
                             'contact_type',
                             ('entity_id', 'source_system',
                              'contact_type', 'contact_pref',
                              'contact_description', 'contact_alias'),
                             cerebrum_person.get_contact_info(
                                 source=source_system))

    for (k, v) in set(hr_person.get('contacts')) - contacts:
        cerebrum_person.populate_contact_info(source_system, k, v)
        logger.debug('Adding contact {} for id:{}'.format(
            (_stringify_for_log(k), v), cerebrum_person.entity_id))
    for (k, v) in contacts - set(hr_person.get('contacts')):
        cerebrum_person.delete_contact_info(source_system, k)
        logger.debug('Removing contact {} for id:{}'.format(
            (_stringify_for_log(k), v), cerebrum_person.entity_id))


def update_titles(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with work and personal titles.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    co = Factory.get('Constants')(database)
    titles = set(map(lambda x:
                     tuple(filter(lambda (k, v):
                                  k not in ('entity_id', 'entity_type'),
                                  x.items())),
                     cerebrum_person.search_name_with_language(
                         entity_id=cerebrum_person.entity_id,
                         name_variant=[co.name_work_title,
                                       co.name_personal_title])))

    for e in set(hr_person.get('titles')) - titles:
        cerebrum_person.add_name_with_language(**dict(e))
        logger.debug('Adding title {} for id:{}'.format(
            _stringify_for_log(e), cerebrum_person.entity_id))

    for e in titles - set(hr_person.get('titles')):
        cerebrum_person.delete_name_with_language(**dict(e))
        logger.debug('Removing title {} for id:{}'.format(
            _stringify_for_log(e), cerebrum_person.entity_id))


def update_reservation(database, hr_person, cerebrum_person):
    """Manage reservation from public display for a person in Cerebrum.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    # TODO: Recode this function when we handle reservation on the fly
    gr = Factory.get('Group')(database)
    gr.find_by_name('SAP-elektroniske-reservasjoner')
    in_reserved_group = gr.has_member(cerebrum_person.entity_id)

    if hr_person.get('reserved') and not in_reserved_group:
        gr.add_member(cerebrum_person.entity_id)
        logger.debug('Removing id:{} from reservation group'.format(
            cerebrum_person.entity_id))
    elif not hr_person.get('reserved') and in_reserved_group:
        gr.remove_member(cerebrum_person.entity_id)
        logger.debug('Adding id:{} to reservation group'.format(
            cerebrum_person.entity_id))


def handle_person(database, source_system, url, identifier,
                  datasource=get_hr_person):
    """Fetch info from the remote system, and perform changes.

    :param database: A database object
    :param source_system: The source system code
    :param url: The URL to the person object in the HR systems WS.
    :param identifier: The updated identifier"""
    hr_person = datasource(database, source_system, url, identifier)
    cerebrum_person = get_cerebrum_person(database, identifier)

    update_person(database, source_system, hr_person, cerebrum_person)
    update_addresses(database, source_system, hr_person, cerebrum_person)
    update_contact_info(database, source_system, hr_person, cerebrum_person)
    update_titles(database, source_system, hr_person, cerebrum_person)
    update_affiliations(database, source_system, hr_person, cerebrum_person)
    update_reservation(database, hr_person, cerebrum_person)
    cerebrum_person.write_db()
    database.commit()


def select_identifier(body):
    """Excavate identifier from message body."""
    import json
    d = json.loads(body)
    return (d.get('url'), d.get('id'))


def callback(database, source_system, routing_key, content_type, body,
             datasource=get_hr_person):
    """Call appropriate handler functions."""
    (url, identifier) = select_identifier(body)

    return_state = True
    try:
        handle_person(database, source_system, url, identifier,
                      datasource=datasource)
        logger.info('Successfully processed {}'.format(identifier))
    except RemoteSourceDown:
        return_state = False
    except Exception as e:
        logger.error('Failed processing {}: {}'.format(identifier, e),
                     exc_info=True)

    # Always rollback, since we do an implicit begin and we want to discard
    # possible outstanding changes.
    database.rollback()
    return return_state


def load_mock(mock_file):
    """Call appropriate handler functions."""
    import json
    with open(mock_file) as f:
        data = json.load(f).get('d')
        import pprint
        logger.debug1(
            'Using mock with data:\n%s', pprint.pformat(data, indent=4))
    return data


def main(args=None):
    """Start consuming messages."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-m', '--mock',
                        dest='mock',
                        metavar='FILE',
                        default=None,
                        help='Load person object from JSON file')
    parser.add_argument('--dryrun',
                        dest='dryrun',
                        action='store_true',
                        default=False,
                        help='Do not commit changes')
    args = parser.parse_args(args)
    prog_name = parser.prog.rsplit('.', 1)[0]

    import functools
    from Cerebrum.modules.event_consumer import get_consumer

    database = Factory.get('Database')()
    database.cl_init(change_program=prog_name)
    source_system = Factory.get('Constants')(database).system_sap

    if args.dryrun:
        database.commit = database.rollback

    if args.mock:
        import json
        mock_data = load_mock(args.mock)
        parsed_mock_data = _parse_hr_person(database,
                                            source_system,
                                            mock_data)
        body = json.dumps({'id': mock_data.get(u'PersonID'), 'url': None})
        callback(database, source_system, '', '', body,
                 datasource=lambda *x: parsed_mock_data)
    else:
        consumer = get_consumer(functools.partial(callback,
                                                  (database, source_system)),
                                prog_name)

        try:
            consumer.start()
        except KeyboardInterrupt:
            consumer.stop()
        consumer.close()

if __name__ == "__main__":
    main()
