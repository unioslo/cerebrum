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


from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Namespace,
                                           Configuration)
from Cerebrum.config.settings import String
from Cerebrum.config.loader import read, read_config

from Cerebrum.modules.event_consumer.config import AMQPClientConsumerConfig

logger = Factory.get_logger('cronjob')
callback_functions = CallbackMap()
callback_filters = CallbackMap()


def filter_meta(l):
    return dict(filter(lambda (k, _): k != u'__metadata', l.items()))


def translate_keys(d, m):
    return map(lambda (k, v): (m.get(k, None), v), d.items())


def filter_elements(d):
    return filter(lambda (k, v): k and v, d)


class RemoteSourceDown(Exception):
    """Exception signaling that the remote system is out of service."""


class SAPWSConsumerConfig(Configuration):
    auth_user = ConfigDescriptor(
        String,
        default=u"webservice",
        doc=u"Username to use when connecting to the WS.")

    auth_system = ConfigDescriptor(
        String,
        default='sap_ws',
        doc=u"The system name used for the password file, for example 'test'.")


class SAPConsumerConfig(Configuration):
    ws = ConfigDescriptor(Namespace, config=SAPWSConsumerConfig)
    consumer = ConfigDescriptor(Namespace, config=AMQPClientConsumerConfig)


def load_config(filepath=None):
    config_cls = SAPConsumerConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'consumer_sap')
    config_cls.validate()
    return config_cls


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

    m = {u'homeAddress': co.address_post_private,
         u'postalAddress': co.address_post,
         u'visitingAddress': co.address_street,

         u'city': u'city',
         u'postalCode': u'postal_number',
         u'streetAndHouseNumber': u'address_text'}

    r = {x.get('type'): x for x in d.get('addresses', [])}

    # Visiting address should be a concoction of real address and a
    # meta-location
    if u'visitingAddress' in r:
        r[u'visitingAddress'][u'streetAndHouseNumber'] = u'{}\n{}'.format(
            r.get(u'visitingAddress').get(u'streetAndHouseNumber'),
            r.get(u'visitingAddress').get(u'location'))

    return tuple([(k, tuple(sorted(filter_elements(translate_keys(v, m))))) for
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
    return ((co.name_first, d.get(u'firstName')),
            (co.name_last, d.get(u'lastName')))


def parse_contacts(d):
    """Parse data from SAP and return contact information.

    :type d: dict
    :param d: Data from SAP

    :rtype: ((ContactInfo('PHONE'), (('contact_pref', n),
                                     ('contact_value', v),
                                     ('description', None))),)
    :return: A tuple with the fields that should be updated"""
    co = Factory.get('Constants')

    # TODO: Validate/clean numbers with phonenumbers?
    m = {u'phone1': co.contact_phone,
         u'phone2': co.contact_phone,
         u'mobile': co.contact_mobile_phone,
         u'mobilePrivate': co.contact_private_mobile,
         u'mobilePrivateWeb': co.contact_private_mobile_visible}

    def expand(l, pref=0):
        if not l:
            return tuple()
        elif len(l) > 1:
            n = l[1:]
        else:
            n = None

        (k, v) = l[0]
        return ((k,
                (('contact_pref', pref),
                 ('contact_value', v),
                 ('description', None)),),) + expand(n, pref + 1)
    return expand(
        filter_elements(
            translate_keys(
                {c.get('type'): c.get('value') for
                 c in d.get(u'phoneNumbers')},
                m)))


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
        return ((u'name_variant', variant),
                (u'name_language', lang),
                (u'name', name))

    titles = ([make_tuple(co.personal_title,
                          co.language_en,
                          d.get(u'title').get(u'english'))] +
              map(lambda lang: make_tuple(co.personal_title,
                                          lang,
                                          d.get(u'title').get(u'norwegian')),
                  [co.language_nb, co.language_nn]))

    # Select appropriate work title.
    work_title = None
    for e in d.get(u'assignments', []):
        if e.get(u'type') == u'primary':
            work_title = e
            break
        if not work_title:
            work_title = e
        elif (float(e.get(u'percentage')) >
                float(work_title.get(u'percentage')) or
                not work_title):
            work_title = e

    if work_title:
        titles.extend(map(lambda (lang_code, lang_str): make_tuple(
            co.work_title,
            lang_code,
            work_title.get(u'job').get(u'title').get(lang_str)),
            [(co.language_nb, u'norwegian'),
             (co.language_nn, u'norwegian'),
             (co.language_en, u'english')]))

    return filter(lambda ((vk, vn), (lk, lv), (nk, nv)): nv, titles)


def parse_external_ids(d):
    """Parse data from SAP and return external ids (i.e. passnr).

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(EntityExternalId('PASSNR'),
                   '000001')]
    :return: A list of tuples with the external_ids"""
    co = Factory.get('Constants')

    def make_tuple(x):
        return {
            u'internationalId': (co.externalid_pass_number,
                                 (x.get(u'country') + x.get(u'value'))),
            u'nationalIdentityNumber': (co.externalid_fodselsnr,
                                        x.get(u'value'))}.get(x.get('type'))

    external_ids = [(co.externalid_sap_ansattnr, unicode(d.get(u'id')))]

    external_ids.extend(
        [make_tuple(x) for x in d.get('identities')])

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

    for x in d.get(u'assignments'):
        status = {u'T/A': co.affiliation_status_ansatt_tekadm,
                  u'Vit': co.affiliation_status_ansatt_vitenskapelig}.get(
                      x.get(u'job').get(u'category').get('uio'))

        ou.clear()
        ou.find_stedkode(
            *map(u''.join,
                 zip(*[iter(str(
                     x.get(u'organizationalUnit')))]*2)) +
            [cereconf.DEFAULT_INSTITUSJONSNR])
        main = x.get(u'type') == u'primary'
        yield {u'ou_id': ou.entity_id,
               u'affiliation': co.affiliation_ansatt,
               u'status': status,
               u'precedence': (50L, 50L) if main else None}


def _parse_hr_person(database, source_system, data):
    from mx import DateTime
    co = Factory.get('Constants')

    return {
        u'id': data.get(u'id'),
        u'addresses': parse_address(data),
        u'names': parse_names(data),
        u'birth_date': DateTime.DateFrom(
            data.get(u'dateOfBirth')),
        u'gender': {u'Kvinne': co.gender_female,
                    u'Mann': co.gender_male}.get(
                        data.get(u'gender'),
                        co.gender_unknown),
        u'external_ids': parse_external_ids(data),
        u'contacts': parse_contacts(data),
        u'affiliations': parse_affiliations(database, data),
        u'titles': parse_titles(data),
        u'reserved': not data.get(u'publicView')}


def get_hr_person(config, database, source_system, url):
    """Collect a person entry from the remote source system, and parse the data.

    :param db: Database object
    :param source_system: The source system code
    :param url: The URL to contact for collection

    :rtype: dict
    :return The parsed data from the remote source system

    :raises: RemoteSourceDown if the remote system can't be contacted"""

    def _get_data(config, url):
        import requests
        import json
        from Cerebrum.Utils import read_password

        auth = (config.auth_user, read_password(user=config.auth_user,
                                                system=config.auth_system))
        headers = {'Accept': 'application/json'}

        try:
            r = requests.get(url, auth=auth, headers=headers)
        except Exception as e:
            # Be polite on connection errors. Conenction errors seldom fix
            # themselves quickly.
            import time
            time.sleep(1)
            raise e

        if r.status_code == 200:
            data = json.loads(r.text).get(u'd', None)

            for k in data:
                if (isinstance(data.get(k), dict) and
                        '__deferred' in data.get(k) and
                        'uri' in data.get(k).get('__deferred')):
                    # Fetch, unpack and store data
                    r = _get_data(config,
                                  data.get(k).get('__deferred').get('uri'))
                    if r.keys() == [u'results']:
                        r = r[u'results']
                    data.update({k: r})
            return data
        else:
            logger.error(
                u'Could not fetch {} from remote source: {}: {}'.format(
                    url, r.status_code, r.reason))
            raise RemoteSourceDown

    return _parse_hr_person(database, source_system, _get_data(config, url))


def get_cerebrum_person(database, identifier):
    """Get a person object from Cerebrum.

    If the person does not exist in Cerebrum, the returned object is
    clear()'ed"""
    pe = Factory.get('Person')(database)
    co = Factory.get('Constants')(database)
    from Cerebrum import Errors
    try:
        pe.find_by_external_id(co.externalid_sap_ansattnr, str(identifier))
        logger.debug(u'Found existing person with id:{}'.format(pe.entity_id))
    except Errors.NotFoundError:
        logger.debug(
            u'Could not find existing person for sap id:{}'.format(
                identifier))
        pe.clear()
    return pe


def _stringify_for_log(data):
    from Cerebrum.Constants import _CerebrumCode
    import collections
    if isinstance(data, _CerebrumCode):
        return unicode(data)
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
    if not (cerebrum_person.gender and
            cerebrum_person.birth_date and
            cerebrum_person.gender == hr_person.get(u'gender') and
            cerebrum_person.birth_date == hr_person.get(u'birth_date')):
        cerebrum_person.populate(
            hr_person.get(u'birth_date'),
            hr_person.get(u'gender'))
        cerebrum_person.write_db()

        logger.debug(u'Added birth date {} and gender {} for {}'.format(
            hr_person.get(u'birth_date'),
            hr_person.get(u'gender'),
            cerebrum_person.entity_id))


def update_affiliations(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with the latest affiliations.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    for affiliation in hr_person.get(u'affiliations'):
        cerebrum_person.populate_affiliation(source_system, **affiliation)
        logger.debug(u'Adding affiliation {} for id:{}'.format(
            _stringify_for_log(affiliation), cerebrum_person.entity_id))


def update_names(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with fresh names.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    from Cerebrum import Errors
    co = Factory.get('Constants')(database)
    try:
        names = set(map(lambda name_type:
                    (name_type,
                     cerebrum_person.get_name(
                         source_system,
                         name_type)),
                    [co.name_first, co.name_last]))
    except Errors.NotFoundError:
        names = set()

    to_remove = names - set(hr_person.get(u'names'))
    to_add = set(hr_person.get(u'names')) - names

    if to_remove:
        logger.debug(u'Purging names of types {} for id:{}'.format(
            map(lambda (k, _): _stringify_for_log(k), to_remove),
            cerebrum_person.entity_id))

    cerebrum_person.affect_names(
        source_system,
        *map(lambda (k, _): k, to_remove | to_add))
    for (k, v) in to_add:
        cerebrum_person.populate_name(k, v)
        logger.debug(u'Adding name {} for id:{}'.format(
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

    hr_person.get(u'external_ids')

    external_ids = set(map(lambda e: (e[u'id_type'], e[u'external_id']),
                       cerebrum_person.get_external_id(
                           source_system=source_system)))

    to_remove = external_ids - set(hr_person.get(u'external_ids'))
    to_add = set(hr_person.get(u'external_ids')) - external_ids

    cerebrum_person.affect_external_id(
        source_system,
        *map(lambda (k, _): k, to_remove | to_add))
    if to_remove:
        logger.debug(u'Purging externalids of types {} for id:{}'.format(
            map(lambda (k, _): _stringify_for_log(co.EntityExternalId(k)),
                to_remove),
            cerebrum_person.entity_id))

    for (k, v) in to_add:
        cerebrum_person.populate_external_id(
            source_system, k, v)
        logger.debug(u'Adding externalid {} for id:{}'.format(
            (_stringify_for_log(co.EntityExternalId(k)), v),
            cerebrum_person.entity_id))


def update_addresses(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with addresses.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    co = Factory.get('Constants')(database)
    addresses = row_transform(co.Address,
                              u'address_type',
                              (u'entity_id', u'source_system', u'address_type',
                               u'p_o_box', u'country'),
                              cerebrum_person.get_entity_address(
                                  source=source_system))

    for (k, v) in addresses - set(hr_person.get(u'addresses')):
        cerebrum_person.delete_entity_address(source_system, k)
        logger.debug(u'Removing address {} for id:{}'.format(
            (_stringify_for_log(k), v), cerebrum_person.entity_id))

    for (k, v) in set(hr_person.get(u'addresses')) - addresses:
        cerebrum_person.add_entity_address(source_system, k, **dict(v))
        logger.debug(u'Adding address {} for id:{}'.format(
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
                             u'contact_type',
                             (u'entity_id', u'source_system',
                              u'contact_type', u'contact_description',
                              u'contact_alias'),
                             cerebrum_person.get_contact_info(
                                     source=source_system))

    for (k, v) in contacts - set(hr_person.get('contacts')):
        (p, v, _d) = (value for (_, value) in v)
        cerebrum_person.delete_contact_info(source_system, k, p)
        logger.debug(
            u'Removing contact ({}) type {} with preference {} for '
            u'id:{}'.format(
                v, _stringify_for_log(k), p, cerebrum_person.entity_id))

    for (k, v) in set(hr_person.get(u'contacts')) - contacts:
        (p, v, _d) = (value for (_, value) in v)
        cerebrum_person.add_contact_info(source_system, k, v, p)
        logger.debug(
            u'Adding contact {} of type {} with preference {} for '
            u'id:{}'.format(
                v, _stringify_for_log(k), p, cerebrum_person.entity_id))


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
                                  k not in (u'entity_id', u'entity_type'),
                                  x.items())),
                     cerebrum_person.search_name_with_language(
                         entity_id=cerebrum_person.entity_id,
                         name_variant=[co.work_title,
                                       co.personal_title])))

    for e in set(hr_person.get(u'titles')) - titles:
        cerebrum_person.add_name_with_language(**dict(e))
        logger.debug(u'Adding title {} for id:{}'.format(
            _stringify_for_log(e), cerebrum_person.entity_id))

    for e in titles - set(hr_person.get(u'titles')):
        cerebrum_person.delete_name_with_language(**dict(e))
        logger.debug(u'Removing title {} for id:{}'.format(
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
    gr.find_by_name(u'SAP-elektroniske-reservasjoner')
    in_reserved_group = gr.has_member(cerebrum_person.entity_id)

    if hr_person.get(u'reserved') and not in_reserved_group:
        gr.add_member(cerebrum_person.entity_id)
        logger.debug(u'Adding id:{} to reservation group'.format(
            cerebrum_person.entity_id))
    elif not hr_person.get(u'reserved') and in_reserved_group:
        gr.remove_member(cerebrum_person.entity_id)
        logger.debug(u'Removing id:{} from reservation group'.format(
            cerebrum_person.entity_id))


def handle_person(database, source_system, url, datasource=get_hr_person):
    """Fetch info from the remote system, and perform changes.

    :param database: A database object
    :param source_system: The source system code
    :param url: The URL to the person object in the HR systems WS.
    :param datasource: The function used to fetch / parse the resource."""
    hr_person = datasource(database, source_system, url)
    identifier = hr_person.get(u'id')
    cerebrum_person = get_cerebrum_person(database, identifier)

    update_person(database, source_system, hr_person, cerebrum_person)
    update_external_ids(database, source_system, hr_person, cerebrum_person)
    update_names(database, source_system, hr_person, cerebrum_person)
    update_addresses(database, source_system, hr_person, cerebrum_person)
    update_contact_info(database, source_system, hr_person, cerebrum_person)
    update_titles(database, source_system, hr_person, cerebrum_person)
    update_affiliations(database, source_system, hr_person, cerebrum_person)
    update_reservation(database, hr_person, cerebrum_person)
    cerebrum_person.write_db()
    database.commit()


def get_resource_url(body):
    """Excavate resource URL from message body."""
    import json
    d = json.loads(body)
    return d.get(u'sub')


def callback(database, source_system, routing_key, content_type, body,
             datasource=get_hr_person):
    """Call appropriate handler functions."""
    try:
        url = get_resource_url(body)
    except Exception as e:
        logger.warn('Received malformed message "{}"'.format(body))
        return True

    message_processed = True
    try:
        handle_person(database, source_system, url, datasource=datasource)
        logger.info(u'Successfully processed {}'.format(body))
    except RemoteSourceDown:
        message_processed = False
    except Exception as e:
        message_processed = False
        logger.error(u'Failed processing {}:\n {}'.format(body, e),
                     exc_info=True)

    # Always rollback, since we do an implicit begin and we want to discard
    # possible outstanding changes.
    database.rollback()
    return message_processed


def load_mock(mock_file):
    """Call appropriate handler functions."""
    import json
    with open(mock_file) as f:
        data = json.load(f).get(u'd')
        import pprint
        logger.debug1(
            u'Using mock with data:\n%s', pprint.pformat(data, indent=4))
    return data


def main(args=None):
    """Start consuming messages."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--config',
                        dest='configfile',
                        metavar='FILE',
                        default=None,
                        help='Use a custom configuration file')
    parser.add_argument(u'-m', u'--mock',
                        dest=u'mock',
                        metavar=u'FILE',
                        default=None,
                        help=u'Load person object from JSON file')
    parser.add_argument(u'--dryrun',
                        dest=u'dryrun',
                        action=u'store_true',
                        default=False,
                        help=u'Do not commit changes')
    args = parser.parse_args(args)
    prog_name = parser.prog.rsplit(u'.', 1)[0]

    import functools
    from Cerebrum.modules.event_consumer import get_consumer

    database = Factory.get('Database')(client_encoding='UTF-8')
    database.cl_init(change_program=prog_name)
    source_system = Factory.get('Constants')(database).system_sap

    config = load_config(filepath=args.configfile)

    if args.dryrun:
        database.commit = database.rollback

    if args.mock:
        import json
        mock_data = load_mock(args.mock)
        parsed_mock_data = _parse_hr_person(database,
                                            source_system,
                                            mock_data)
        body = json.dumps({u'sub': None})
        callback(database, source_system, u'', u'', body,
                 datasource=lambda *x: parsed_mock_data)
    else:
        logger.info('Starting {}'.format(prog_name))
        consumer = get_consumer(functools.partial(callback,
                                                  database, source_system,
                                                  datasource=functools.partial(
                                                      get_hr_person,
                                                      config.ws)),
                                config=config.consumer)
        with consumer:
            try:
                consumer.start()
            except KeyboardInterrupt:
                consumer.stop()
            consumer.close()
        logger.info('Stopping {}'.format(prog_name))

if __name__ == "__main__":
    main()
