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
filter_elements = lambda d: dict(
    filter(lambda (k, _): k, d.items()))


class RemoteSourceDown(Exception):
    """Exception signaling that the remote system is out of service."""


def parse_address(d):
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
    r['VisitingAddress'] = '{}\n{}'.format(
        r.get('VisitingAddress').get('StreetAndHouseNumber'),
        r.get('VisitingAddress').get('Location'))

    for address in filter_elements(translate_keys(filter_meta(r), m)):
        yield filter_elements(translate_keys(address, m))


def parse_names(d):
    co = Factory.get('Constants')
    return ((co.name_first, d.get('FirstName')),
            (co.name_last, d.get('LastName')))


def parse_contacts(d):
    co = Factory.get('Constants')
    c = d.get('Communication')
    # TODO: Vaildate/clean numbers with phonenumbers?
    m = {'Phone1': co.contact_phone,
         'Phone2': co.contact_phone,
         'Mobile': co.contact_mobile_phone,
         'MobilePrivate': co.contact_private_mobile,
         'MobilePublic': co.contact_private_mobile_visible}

    return filter_elements(translate_keys(c, m))


def parse_titles(d):
    co = Factory.get('Constans')

    def make_tuple(variant, lang, name):
        return (('name_variant', variant),
                ('name_language', lang),
                ('name'), name)
    titles = [
        make_tuple(co.personal_title,
                   co.language_en,
                   d.get('Title').get('English')),
        map(lambda lang: make_tuple(co.personal_title,
                                    lang,
                                    d.get('Title').get('Norwegian')),
            [co.language_nb, co.language_nn])]

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
        [('Norwegian', co.language_nb),
         ('Norwegian', co.language_nn),
         ('English', co.language_english)])


def parse_external_ids(source_system, d):
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
    import cereconf
    co = Factory.get('Constants')
    ou = Factory.get('OU')(database)

    for x in d.get('Employments').get('results'):
        status = {'T/A': co.affiliation_status_ansatt_tekadm,
                  'Vit': co.affiliation_status_ansatt_vitenskapelig}.get(
                      x.get('Category'))

        ou.find_stedkode(
            *map(''.join, zip(*[iter(x.get('OrganizationalUnit'))]*2)) +
            [cereconf.DEFAULT_INSTITUSJONSNR]).entity_id
        main = x.get('IsMain')
        yield {'ou_id': ou.entity_id,
               'affiliation': co.affiliation_ansatt,
               'status': status,
               'precedence': 50L if main else None}


def get_hr_person(database, source_system, endpoint, identificator):
    import requests
    import json
    from mx import DateTime

    co = Factory.get('Constants')
    r = requests.get(endpoint.format(identificator))
    if r.status_code == 200:
        data = json.loads(r.text).get('d', None)
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
    else:
        logger.error('Could not fetch {} from remote source: {}: {}').format(
            identificator, r.status_code, r.reason)
        raise RemoteSourceDown


def get_cerebrum_person(database, identificator):
    pe = Factory.get('Person')(database)
    co = Factory.get('Constants')(database)
    from Cerebrum import Errors
    try:
        pe.find_by_external_id(co.externalid_sap_ansattnr, str(identificator))
        logger.debug(''.format())
    except Errors.NotFoundError:
        logger.debug(''.format())
        pe.clear()
    return pe


def update_person(database, source_system, hr_person, cerebrum_person):

    cerebrum_person.populate(
        hr_person.get('birth_date'),
        hr_person.get('gender'))
    logger.debug('Added birth date {} and gender {} for {}'.format(
        hr_person.get('birth_date'),
        hr_person.get('gender'),
        cerebrum_person.entity_id))

    cerebrum_person.write_db()


def update_affiliations(database, source_system, hr_person, cerebrum_person):
    for affiliation in hr_person:
        cerebrum_person.populate_affiliation(source_system, **affiliation)
        logger.debug('Adding affiliation {} for id:{}'.format(
            affiliation, cerebrum_person.entity_id))


def update_names(database, source_system, hr_person, cerebrum_person):
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
    co = Factory.get('Constants')(database)
    addresses = row_transform(co.Address,
                              'address_type',
                              ('entity_id', 'source_system', 'address_type'),
                              cerebrum_person.get_entity_address(
                                  source=source_system))

    for (k, v) in set(hr_person.get('addresses')) - addresses:
        cerebrum_person.delete_entity_address(source_system, k)
        logger.debug('Removing address {} for id:{}'.format(
            (k, v), cerebrum_person.entity_id))
    for (k, v) in addresses - set(hr_person.get('addresses')):
        cerebrum_person.add_entity_address(source_system, k, **dict(v))
        logger.debug('Adding address {} for id:{}'.format(
            (k, v), cerebrum_person.entity_id))
        logger.debug(''.format())


def update_contact_info(database, source_system, hr_person, cerebrum_person):
    co = Factory.get('Constants')(database)
    contacts = row_transform(co.ContactInfo,
                             'contact_type',
                             ('entity_id', 'source_system',
                              'contact_type', 'contact_pref',
                              'contact_description', 'contact_alias'),
                             cerebrum_person.get_contact_info(
                                 source=source_system))

    for (k, v) in set(hr_person.get('contacts')) - contacts:
        cerebrum_person.delete_contact_info(source_system, k)
        logger.debug('Removing contact {} for id:{}'.format(
            (k, v), cerebrum_person.entity_id))
    for (k, v) in contacts - set(hr_person.get('contacts')):
        cerebrum_person.populate_contact_info(source_system, k, v)
        logger.debug('Adding contact {} for id:{}'.format(
            (k, v), cerebrum_person.entity_id))


def update_titles(database, source_system, hr_person, cerebrum_person):
    co = Factory.get('Constants')(database)
    titles = set(map(lambda x:
                     tuple(filter(lambda (k, v):
                                  k not in ('entity_id', 'entity_type'),
                                  x.items())),
                     cerebrum_person.search_name_with_language(
                         entity_id=cerebrum_person.entity_id,
                         name_variant=[co.name_work_title,
                                       co.name_person_title])))

    for e in hr_person.get('titles') - titles:
        cerebrum_person.delete_name_with_language(**dict(e))
        logger.debug('Removing title {} for id:{}'.format(
            e, cerebrum_person.entity_id))
    for e in titles - hr_person.get('titles'):
        cerebrum_person.add_name_with_language(**dict(e))
        logger.debug('Adding title {} for id:{}'.format(
            e, cerebrum_person.entity_id))


def update_reservation(database, hr_person, cerebrum_person):
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


def handle_person(database, source_system, identificator):
    hr_person = get_hr_person(database, source_system, identificator)
    cerebrum_person = get_cerebrum_person(database, identificator)

    update_person(database, source_system, hr_person, cerebrum_person)
    update_addresses(database, source_system, hr_person, cerebrum_person)
    update_contact_info(database, source_system, hr_person, cerebrum_person)
    update_titles(database, source_system, hr_person, cerebrum_person)
    update_affiliations(database, source_system, hr_person, cerebrum_person)
    update_reservation(database, hr_person, cerebrum_person)
    cerebrum_person.write_db()
    database.commit()


def callback(database, source_system, routing_key, content_type, body):
    """Call appropriate handler functions."""
    return_state = True
    try:
        handle_person(database, source_system, body)
        logger.info('Sucessfully processed {}'.format(body))
    except RemoteSourceDown:
        return_state = False
    except Exception as e:
        logger.error('Failed processing {}: {}'.format(body, e))

    # Always rollback, since we do an implicit begin and we want to discard
    # posible outstanding changes.
    database.rollback()
    return return_state


def main():
    """Start consuming messages."""
    import argparse
    import functools
    from Cerebrum.modules.event_consumer import get_consumer

    database = Factory.get('Database')()
    source_system = Factory.get('Constants')(database).system_sap

    consumer = get_consumer(functools.partial(callback,
                                              (database, source_system)),
                            argparse.ArgumentParser().prog.rsplit('.', 1)[0])

    try:
        consumer.start()
    except KeyboardInterrupt:
        consumer.stop()
        consumer.close()

if __name__ == "__main__":
    main()
