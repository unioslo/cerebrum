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

import datetime
import requests
import json
from collections import OrderedDict
from six import text_type

from Cerebrum import Errors
from Cerebrum.Utils import Factory, read_password
from Cerebrum.modules.event.mapping import CallbackMap

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Namespace,
                                           Configuration)
from Cerebrum.config.settings import String
from Cerebrum.config.loader import read, read_config

from Cerebrum.modules.event_consumer.config import AMQPClientConsumerConfig

logger = Factory.get_logger('cronjob')
AccountClass = Factory.get('Account')
callback_functions = CallbackMap()
callback_filters = CallbackMap()


def filter_meta(l):
    """Filter out the __metadata key of a dict."""
    return dict(filter(lambda (k, _): k != u'__metadata', l.items()))


def translate_keys(d, m):
    """Translate keys in accordance to a LUT.

    :type d: dict
    :param d: The dict whose keys to convert.

    :type m: dict
    :param m: A lookup table.

    :rtype: dict
    :return: The converted dict."""
    return map(lambda (k, v): (m.get(k, None), v), d.items())


def filter_elements(d):
    """Filter out all elements that do not evaluate to True.

    :type d: list(tuple(k, v))
    :param d: A list of tuples to filter.

    :rtype: list(tuple(k, v))
    :return: The filtered list."""
    return filter(lambda (k, v): k and v, d)


class RemoteSourceUnavailable(Exception):
    """Exception signaling that the remote system is out of service."""


class RemoteSourceError(Exception):
    """An error occured in the source system."""


class ErroneousSourceData(Exception):
    """An error occured in the source system data."""


class EntityNotResolvableError(Exception):
    """Distinctive entity could not be resolved with supplied information."""


class SAPWSConsumerConfig(Configuration):
    """Configuration of the WebService connectivity."""
    auth_user = ConfigDescriptor(
        String,
        default=u"webservice",
        doc=u"Username to use when connecting to the WS.")

    auth_system = ConfigDescriptor(
        String,
        default='sap_ws',
        doc=u"The system name used for the password file, for example 'test'.")


class SAPConsumerConfig(Configuration):
    """Config combining class."""
    ws = ConfigDescriptor(Namespace, config=SAPWSConsumerConfig)
    consumer = ConfigDescriptor(Namespace, config=AMQPClientConsumerConfig)


def load_config(filepath=None):
    """Load config for this consumer."""
    config_cls = SAPConsumerConfig()
    if filepath:
        logger.info(u'(load_config) Loading config file: {}'.format(filepath))
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'consumer_sap')
        logger.info(u'(load_config) no filepath, using defaults')
    logger.info(u'(load_config) validating config_cls')
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
    logger.info(u'parsing %i addresses', len(d))
    co = Factory.get('Constants')
    address_types = (u'legalAddress',
                     u'workMailingAddress',
                     u'workVisitingAddress')
    m = {u'legalAddress': co.address_post_private,
         u'workMailingAddress': co.address_post,
         u'workVisitingAddress': co.address_street,
         u'city': u'city',
         u'postalCode': u'postal_number',
         u'streetAndHouseNumber': u'address_text'}
    r = {x: d.get(x, {}) for x in address_types}
    # Visiting address should be a concoction of real address and a
    # meta-location
    if r.get(u'workVisitingAddress'):
        r[u'workVisitingAddress'][u'streetAndHouseNumber'] = u'{}\n{}'.format(
            r.get(u'workVisitingAddress').get(u'streetAndHouseNumber'),
            r.get(u'workVisitingAddress').get(u'location'))
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
    logger.info(u'parsing {} names'.format(len(d)))
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
    logger.info(u'parsing {} contacts'.format(len(d)))
    co = Factory.get('Constants')
    # TODO: Validate/clean numbers with phonenumbers?
    m = {u'workPhone': co.contact_phone,
         u'workMobile': co.contact_mobile_phone,
         u'privateMobile': co.contact_private_mobile,
         u'publicMobile': co.contact_private_mobile_visible}

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
            translate_keys({c: d.get(c) for c in m.keys()}, m)))


def parse_titles(d):
    """Parse data from SAP and return person titles.

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(('name_variant', EntityNameCode('PERSONALTITLE')),
                   ('name_language', LanguageCode('en')),
                   ('name', 'Over Engingineer'))]
    :return: A list of tuples with the fields that should be updated"""

    def make_tuple(variant, lang, name):
        return ((u'name_variant', variant),
                (u'name_language', lang),
                (u'name', name))

    co = Factory.get('Constants')
    logger.info(u'parsing {} titles'.format(len(d)))
    titles = []
    if d.get(u'personalTitle'):
        titles.extend(
            [make_tuple(co.personal_title,
                        co.language_en,
                        d.get(u'personalTitle', {}).get(u'en'))] +
            map(lambda lang: make_tuple(
                    co.personal_title,
                    lang,
                    d.get(u'personalTitle', {}).get(u'nb')),
                [co.language_nb, co.language_nn]))
    # Select appropriate work title.
    assignment = None
    for e in d.get(u'assignments', {}).get(u'results', []):
        if not e.get(u'jobTitle'):
            continue
        if e.get(u'primaryAssignmentFlag'):
            assignment = e
            break
        if not assignment:
            assignment = e
        elif (float(e.get(u'agreedFTEPercentage')) >
                float(assignment.get(u'agreedFTEPercentage'))):
            assignment = e
    if assignment:
        titles.extend(map(lambda (lang_code, lang_str): make_tuple(
            co.work_title,
            lang_code,
            assignment.get(u'jobTitle').get(lang_str)),
            [(co.language_nb, u'nb'),
             (co.language_nn, u'nb'),
             (co.language_en, u'en')]))
    return filter(lambda ((vk, vn), (lk, lv), (nk, nv)): nv, titles)


def parse_external_ids(d):
    """Parse data from SAP and return external ids (i.e. passnr).

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(EntityExternalId('PASSNR'),
                   '000001')]
    :return: A list of tuples with the external_ids"""
    logger.info(u'parsing %i external ids', len(d))
    co = Factory.get('Constants')
    external_ids = [(co.externalid_sap_ansattnr, unicode(d.get(u'personId')))]
    if d.get(u'passportIssuingCountry') and d.get(u'passportNumber'):
        external_ids.append(
            (co.externalid_pass_number,
             co.make_passport_number(d.get(u'passportIssuingCountry'),
                                     d.get(u'passportNumber'))))
    if d.get(u'norwegianIdentificationNumber'):
        external_ids.append(
            (co.externalid_fodselsnr, d.get(u'norwegianIdentificationNumber')))

    return filter_elements(external_ids)


def _get_ou(database, sap_id, placecode):
    """Populate a Cerebrum-OU-object from the DB."""
    if not placecode:
        return None
    import cereconf
    ou = Factory.get('OU')(database)
    ou.clear()
    try:
        ou.find_stedkode(
            *map(u''.join,
                 zip(*[iter(str(
                     placecode))]*2)) +
            [cereconf.DEFAULT_INSTITUSJONSNR])
        return ou
    except Errors.NotFoundError:
        return None


def _sap_assignments_to_affiliation_map():
    co = Factory.get('Constants')
    return {u'administrative': co.affiliation_status_ansatt_tekadm,
            u'academic': co.affiliation_status_ansatt_vitenskapelig}


def parse_affiliations(database, d):
    """Parse data from SAP and return affiliations.

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(('ou_id': 3),
                   ('affiliation', PersonAffiliation('ANSATT')),
                   ('status', PersonAffStatus('ANSATT', 'tekadm')),
                   (precedence', (50, 50)))]
    :return: A list of tuples with the fields that should be updated"""
    logger.info(u'parsing %i affiliations', len(d))
    co = Factory.get('Constants')
    r = []
    for x in d.get(u'assignments', {}).get(u'results', []):
        status = _sap_assignments_to_affiliation_map().get(
                      x.get(u'jobCategory'))
        if not status:
            logger.warn(u'parse_affiliations: Unknown job category')
            # Unknown job category
            continue
        ou = _get_ou(database,
                     sap_id=x.get('organizationalUnitId'),
                     placecode=x.get(u'locationId'))
        if not ou:
            logger.warn(
                u'OU {} does not exist, '
                u'cannot parse affiliation {} for {}'.format(
                    x.get(u'locationId'), status, x.get(u'personId')))
            continue
        main = x.get(u'primaryAssignmentFlag')
        r.append({u'ou_id': ou.entity_id,
                  u'affiliation': co.affiliation_ansatt,
                  u'status': status,
                  u'precedence': (50L, 50L) if main else None})
    return r


def _sap_roles_to_affiliation_map():
    co = Factory.get('Constants')
    return OrderedDict(
            [(u'INNKJØPER', co.affiliation_tilknyttet_innkjoper),
             (u'EF-FORSKER', co.affiliation_tilknyttet_ekst_forsker),
             (u'EMERITUS', co.affiliation_tilknyttet_emeritus),
             (u'BILAGSLØNN', co.affiliation_tilknyttet_bilag),
             (u'GJ-FORSKER', co.affiliation_tilknyttet_gjesteforsker),
             (u'ASSOSIERT', co.affiliation_tilknyttet_assosiert_person),
             (u'EF-STIP', co.affiliation_tilknyttet_ekst_stip),
             (u'GRP-LÆRER', co.affiliation_tilknyttet_grlaerer),
             (u'EKST-KONS', co.affiliation_tilknyttet_ekst_partner),
             (u'PCVAKT', co.affiliation_tilknyttet_pcvakt),
             (u'EKST-PART', co.affiliation_tilknyttet_ekst_partner),
             (u'STEDOPPLYS', None),
             (u'POLS-ANSAT', None)])


def parse_roles(database, data):
    """Parse data from SAP and return existing roles.

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(('ou_id': 3),
                   ('affiliation', PersonAffiliation('TILKNYTTET')),
                   ('status', PersonAffStatus('TILKNYTTET', 'pcvakt')),
                   (precedence', None))]
    :return: A list of tuples representing them roles."""
    logger.info(u'parsing %i roles', len(d))
    role2aff = _sap_roles_to_affiliation_map()
    r = []
    for role in data.get(u'roles', {}).get(u'results', []):
        ou = _get_ou(database, sap_id=None, placecode=role.get(u'locationId'))
        if not ou:
            logger.warn(
                u'OU {} does not exist, '
                u'cannot parse affiliation {} for {}'.format(
                    role.get(u'locationId'),
                    role2aff.get(role.get(u'roleName')),
                    data.get(u'personId')))
        elif role2aff.get(role.get(u'roleName')):
            r.append({u'ou_id': ou.entity_id,
                      u'affiliation': role2aff.get(
                          role.get(u'roleName')).affiliation,
                      u'status': role2aff.get(role.get(u'roleName')),
                      u'precedence': None})
    return sorted(r,
                  key=(lambda x: role2aff.values().index(x.get('status')) if
                       x.get('status') in role2aff.values() else len(r)),
                  reverse=True)


def _parse_hr_person(database, source_system, data):
    """Collects parsed information from SAP."""
    from mx import DateTime
    co = Factory.get('Constants')
    return {
        u'id': data.get(u'personId'),
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
        u'roles': parse_roles(database, data),
        u'titles': parse_titles(data),
        u'reserved': not data.get(u'allowedPublicDirectoryFlag')
    }


def get_hr_person(config, database, source_system, url):
    """Collect a person entry from the remote source system and parse the data.

    :param config: Authentication data
    :param database: Database object
    :param source_system: The source system code
    :param url: The URL to contact for collection

    :rtype: dict
    :return The parsed data from the remote source system

    :raises: RemoteSourceUnavailable if the remote system can't be contacted"""

    def _get_data(config, url, params=None):
        if not params:
            params = {}

        headers = {'Accept': 'application/json',
                   'X-Gravitee-API-Key': read_password(
                       user=config.auth_user,
                       system=config.auth_system)}
        try:
            logger.debug4(u'Fetching {}'.format(url))
            r = requests.get(url, headers=headers, params=params)
            logger.debug4(u'Fetch completed')
        except Exception as e:
            # Be polite on connection errors. Connection errors seldom fix
            # themselves quickly.
            import time
            time.sleep(1)
            raise RemoteSourceUnavailable(str(e))
        if r.status_code == 200:
            data = json.loads(r.text).get(u'd', None)
            for k in data:
                if (isinstance(data.get(k), dict) and
                        '__deferred' in data.get(k) and
                        'uri' in data.get(k).get('__deferred')):
                    # Fetch, unpack and store data
                    deferred_uri = data.get(k).get('__deferred').get('uri')
                    # We filter by effectiveEndDate >= today to also get
                    # future assignments and roles
                    if k in ('assignments', 'roles'):
                        filter_param = {
                            '$filter': "effectiveEndDate ge '{today}'".format(
                                today=datetime.date.today())
                        }
                    r = _get_data(config, deferred_uri, filter_param)
                    data.update({k: r})
            return data
        else:
            raise RemoteSourceError(
                u'Could not fetch {} from remote source: {}: {}'.format(
                    url, r.status_code, r.reason))
    return _parse_hr_person(database, source_system, _get_data(config, url))


def get_cerebrum_person(database, ids):
    """Get a person object from Cerebrum.

    If the person does not exist in Cerebrum, the returned object is
    clear()'ed"""
    pe = Factory.get('Person')(database)
    try:
        pe.find_by_external_ids(*ids)
        logger.info(u'Found existing person with id: {}'.format(pe.entity_id))
    except Errors.NotFoundError:
        logger.info(
            u'Could not find existing person with one of ids: {}'.format(ids))
        pe.clear()
    except Errors.TooManyRowsError as e:
        raise EntityNotResolvableError(
            u'Person in source system maps to multiple persons in Cerebrum. '
            u'Manual intervention required: {}'.format(e))
    return pe


def update_account_affs(method):
    def wrapper(database, cerebrum_person, ou_id, affiliation):
        """Calls method if a person's account satisfies certain conditions

        :param database: A database object
        :param cerebrum_person: The Person object to be updated.
        :param ou_id: The ou_id code
        :param affiliation: The affiliation code
        """
        accounts = cerebrum_person.get_accounts()
        if len(accounts) != 1:
            logger.info(
                u'Person id {} does not have exactly one account'.format(
                    cerebrum_person.entity_id))
            return
        ac = Factory.get('Account')(database)
        ac.find(accounts[0]['account_id'])
        co = Factory.get('Constants')(database)
        account_types = ac.get_account_types()
        if method.__name__ is AccountClass.del_account_type.__name__:
            if len(account_types) == 1:
                logger.info(u'Cannot delete last account_type')
                return
            if not ac.list_accounts_by_type(ou_id=ou_id,
                                            affiliation=affiliation,
                                            account_id=ac.entity_id):
                logger.info(u'account_type already deleted '
                            u'(aff: %s, ou_id: %s)', affiliation, ou_id)
                return
        if method.__name__ is AccountClass.set_account_type.__name__:
            for at in account_types:
                if (at['ou_id'], at['affiliation']) == (ou_id, affiliation):
                    logger.info(u'account_type already exists '
                                u'(aff: %s, ou_id: %s)', affiliation, ou_id)
                    return
        for account_type in account_types:
            if not int(co.affiliation_ansatt) == account_type['affiliation']:
                logger.info(u'Account has affiliation(s) besides %s' %
                            co.affiliation_ansatt)
                return
            aff_info = cerebrum_person.list_affiliations(
                person_id=account_type['person_id'],
                ou_id=account_type['ou_id'],
                affiliation=account_type['affiliation'],
            )
            if aff_info:
                if not int(co.system_sap) == aff_info[0]['source_system']:
                    logger.info(
                        u'Account has affiliation from source(s) other than %s'
                        % co.system_sap)
                    return
        logger.info(u'{} for account: {}'.format(method.__name__,
                                                 ac.entity_id))
        method(ac, ou_id, affiliation)
    return wrapper


del_account_type = update_account_affs(AccountClass.del_account_type)
set_account_type = update_account_affs(AccountClass.set_account_type)


def _stringify_for_log(data):
    """Convert data to appropriate types for logging."""
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
        logger.info(u'Added birth date {} and gender {} for {}'.format(
            hr_person.get(u'birth_date'),
            hr_person.get(u'gender'),
            cerebrum_person.entity_id))


def _find_affiliations(cerebrum_person, hr_affs, affiliation_map,
                       source_system, mode):
    consider_affiliations = filter(lambda x: x, affiliation_map().values())
    cerebrum_affiliations = cerebrum_person.list_affiliations(
        person_id=cerebrum_person.entity_id,
        status=consider_affiliations,
        source_system=source_system)
    # Format of a hr_aff: { str: [] }
    in_hr = map(
        lambda d: tuple(
            sorted(
                filter(
                    lambda (k, v): k != u'precedence',
                    d.items()
                )
            )
        ),
        hr_affs)
    in_cerebrum = map(
        lambda x: tuple(
            sorted(
                filter_elements(
                    translate_keys(
                        x,
                        {u'ou_id': u'ou_id',
                         u'affiliation': u'affiliation',
                         u'status': u'status'}
                    )
                )
            )
        ),
        cerebrum_affiliations)
    if mode == u'remove':
        return [
            dict(filter(lambda (k, v): k in (u'ou_id', u'affiliation'), x) +
                 ((u'source', source_system),))
            for x in set(in_cerebrum) - set(in_hr)]
    elif mode == u'add':
        to_add = set(in_hr) - set(in_cerebrum)
        to_ensure = set(in_hr) & set(in_cerebrum)
        return [dict(x) for x in to_add | to_ensure]
    else:
        raise Errors.ProgrammingError(
            u'Invalid mode {} supplied to _find_affiliations'.format(
                repr(mode)))


def update_affiliations(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with the latest affiliations.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    for affiliation in _find_affiliations(
            cerebrum_person,
            hr_person.get(u'affiliations'),
            _sap_assignments_to_affiliation_map,
            source_system,
            u'remove'):
        del_account_type(database,
                         cerebrum_person,
                         affiliation['ou_id'],
                         affiliation['affiliation'])
        cerebrum_person.delete_affiliation(**affiliation)
        logger.info(u'Removing affiliation {} for id: {}'.format(
            _stringify_for_log(affiliation), cerebrum_person.entity_id))
    for affiliation in _find_affiliations(
            cerebrum_person,
            hr_person.get(u'affiliations'),
            _sap_assignments_to_affiliation_map,
            source_system,
            u'add'):
        cerebrum_person.populate_affiliation(source_system, **affiliation)
        logger.info(u'Adding affiliation {} for id: {}'.format(
            _stringify_for_log(affiliation), cerebrum_person.entity_id))
    cerebrum_person.write_db()
    for affiliation in _find_affiliations(
            cerebrum_person,
            hr_person.get(u'affiliations'),
            _sap_assignments_to_affiliation_map,
            source_system,
            u'add'):
        set_account_type(database,
                         cerebrum_person,
                         affiliation['ou_id'],
                         affiliation['affiliation'])
        logger.info(u'Setting account type for id: {}'.format(
            cerebrum_person.entity_id))


def update_roles(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with the latest roles.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    for role in _find_affiliations(
            cerebrum_person,
            hr_person.get(u'roles'),
            _sap_roles_to_affiliation_map,
            source_system,
            u'remove'):
        cerebrum_person.delete_affiliation(**role)
        logger.info(u'Removing role {} for id: {}'.format(
            _stringify_for_log(role), cerebrum_person.entity_id))
    for role in _find_affiliations(
            cerebrum_person,
            hr_person.get(u'roles'),
            _sap_roles_to_affiliation_map,
            source_system,
            u'add'):
        cerebrum_person.populate_affiliation(source_system, **role)
        logger.info(
            u'Ensuring role {} for id: {}'.format(
                _stringify_for_log(role),
                cerebrum_person.entity_id))


def update_names(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with fresh names.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
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
        logger.info(u'Purging names of types {} for id: {}'.format(
            map(lambda (k, _): _stringify_for_log(k), to_remove),
            cerebrum_person.entity_id))
    cerebrum_person.affect_names(
        source_system,
        *map(lambda (k, _): k, to_remove | to_add))
    for (k, v) in to_add:
        cerebrum_person.populate_name(k, v)
        logger.info(u'Adding name {} for id: {}'.format(
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
    external_ids = set(map(lambda e: (e[u'id_type'], e[u'external_id']),
                       cerebrum_person.get_external_id(
                           source_system=source_system)))
    to_remove = external_ids - set(hr_person.get(u'external_ids'))
    to_add = set(hr_person.get(u'external_ids')) - external_ids
    cerebrum_person.affect_external_id(
        source_system,
        *map(lambda (k, _): k, to_remove | to_add))
    if to_remove:
        logger.info(u'Purging externalids of types {} for id: {}'.format(
            map(lambda (k, _): _stringify_for_log(co.EntityExternalId(k)),
                to_remove),
            cerebrum_person.entity_id))
        for (k, v) in to_add:
            cerebrum_person.populate_external_id(
                source_system, k, v)
            logger.info(u'Adding externalid {} for id: {}'.format(
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
        logger.info(u'Removing address {} for id: {}'.format(
            (_stringify_for_log(k), v), cerebrum_person.entity_id))
    for (k, v) in set(hr_person.get(u'addresses')) - addresses:
        cerebrum_person.add_entity_address(source_system, k, **dict(v))
        logger.debug(u'Adding address {} for id: {}'.format(
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
                              u'contact_alias', u'last_modified'),
                             cerebrum_person.get_contact_info(
                                 source=source_system))
    for (k, v) in contacts - set(hr_person.get('contacts')):
        (p, v, _d) = (value for (_, value) in v)
        cerebrum_person.delete_contact_info(source_system, k, p)
        logger.info(
            u'Removing contact ({}) of type {} with preference {} for '
            u'id: {}'.format(
                v, _stringify_for_log(k), p, cerebrum_person.entity_id))
    for (k, v) in set(hr_person.get(u'contacts')) - contacts:
        (p, v, _d) = (value for (_, value) in v)
        cerebrum_person.add_contact_info(source_system, k, v, p)
        logger.info(
            u'Adding contact {} of type {} with preference {} for '
            u'id: {}'.format(
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
        logger.info(u'Adding title {} for id: {}'.format(
            _stringify_for_log(e), cerebrum_person.entity_id))
    for e in titles - set(hr_person.get(u'titles')):
        cerebrum_person.delete_name_with_language(**dict(e))
        logger.info(u'Removing title {} for id: {}'.format(
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
        logger.info(u'Adding id: {} to reservation group'.format(
            cerebrum_person.entity_id))
    elif not hr_person.get(u'reserved') and in_reserved_group:
        gr.remove_member(cerebrum_person.entity_id)
        logger.info(u'Removing id: {} from reservation group'.format(
            cerebrum_person.entity_id))


def perform_update(database, source_system, hr_person, cerebrum_person):
    """Update or create a person."""
    logger.info(u'Starting perform_update for {}'.format(
        cerebrum_person.entity_id))
    update_person(database, source_system, hr_person, cerebrum_person)
    update_external_ids(database, source_system, hr_person, cerebrum_person)
    update_names(database, source_system, hr_person, cerebrum_person)
    update_addresses(database, source_system, hr_person, cerebrum_person)
    update_contact_info(database, source_system, hr_person, cerebrum_person)
    update_titles(database, source_system, hr_person, cerebrum_person)
    update_roles(database, source_system, hr_person, cerebrum_person)
    update_affiliations(database, source_system, hr_person, cerebrum_person)
    update_reservation(database, hr_person, cerebrum_person)
    logger.info(u'perform_update done for {}'.format(
        cerebrum_person.entity_id))


def perform_delete(database, source_system, hr_person, cerebrum_person):
    """Delete a person."""
    logger.info(u'Deleting: {}'.format(cerebrum_person.entity_id))
    # Update person and external IDs
    update_person(database, source_system, hr_person, cerebrum_person)
    update_external_ids(database, source_system, hr_person, cerebrum_person)
    # Delete everything else
    update_names(database,
                 source_system,
                 {u'names': []},
                 cerebrum_person)
    update_addresses(database,
                     source_system,
                     {u'addresses': []},
                     cerebrum_person)
    update_contact_info(database,
                        source_system,
                        {u'contacts': []},
                        cerebrum_person)
    update_titles(database,
                  source_system,
                  {u'titles': []},
                  cerebrum_person)
    update_affiliations(database,
                        source_system,
                        {u'affiliations': []},
                        cerebrum_person)
    update_roles(database,
                 source_system,
                 {u'roles': []},
                 cerebrum_person)
    update_reservation(database,
                       {u'reserved': False},
                       cerebrum_person)
    logger.info(u'{} deleted'.format(cerebrum_person.entity_id))


def handle_person(database, source_system, url, datasource=get_hr_person):
    """Fetch info from the remote system, and perform changes.

    :param database: A database object
    :param source_system: The source system code
    :param url: The URL to the person object in the HR systems WS.
    :param datasource: The function used to fetch / parse the resource."""
    hr_person = datasource(database, source_system, url)
    logger.info(u'Handling person {} from source system {}'.format(
        _stringify_for_log(hr_person.get('names')), source_system))
    cerebrum_person = get_cerebrum_person(database,
                                          map(lambda (k, v): (k, v),
                                              hr_person.get(u'external_ids')))
    if hr_person.get('affiliations') or hr_person.get('roles'):
        perform_update(database, source_system, hr_person, cerebrum_person)
    elif cerebrum_person.entity_type:  # entity_type as indication of instance
        perform_delete(database, source_system, hr_person, cerebrum_person)
    else:
        logger.info(u'handle_person: no action performed')
        return
    logger.info(u'handle_person: commiting changes')
    cerebrum_person.write_db()
    database.commit()
    logger.info(u'handle_person: changes committed')


def get_resource_url(body):
    """Excavate resource URL from message body."""
    d = json.loads(body)
    return d.get(u'sub')


def callback(database, source_system, routing_key, content_type, body,
             datasource=get_hr_person):
    """Call appropriate handler functions."""
    try:
        url = get_resource_url(body)
    except Exception as e:
        logger.warn(u'Received malformed message "{}"'.format(body))
        return True
    message_processed = True
    try:
        handle_person(database, source_system, url, datasource=datasource)
        logger.info(u'Successfully processed {}'.format(body))
    except RemoteSourceUnavailable:
        message_processed = False
    except (RemoteSourceError, ErroneousSourceData) as e:
        logger.error(u'Failed processing {}:\n {}: {}'.format(
            body, type(e).__name__, e))
        message_processed = True
    except EntityNotResolvableError as e:
        logger.critical(u'Failed processing {}:\n {}: {}'.format(
            body, type(e).__name__, e))
        message_processed = True
    except Exception as e:
        message_processed = True
        logger.error(u'Failed processing {}:\n {}'.format(body, e),
                     exc_info=True)
    # Always rollback, since we do an implicit begin and we want to discard
    # possible outstanding changes.
    logger.info(u'Rolling back changes')
    database.rollback()
    return message_processed


def load_mock(mock_file):
    """Call appropriate handler functions."""
    with open(mock_file) as f:
        data = json.load(f).get(u'd')
        import pprint
        logger.debug1(
            u'Using mock with data:\n%s', pprint.pformat(data, indent=4))
    return data


def main(args=None):
    """Start consuming messages."""
    import argparse
    import functools
    from Cerebrum.modules.event_consumer import get_consumer

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
    logger.info(u'Starting {}'.format(prog_name))
    database = Factory.get('Database')()
    database.cl_init(change_program=prog_name)
    source_system = Factory.get('Constants')(database).system_sap
    config = load_config(filepath=args.configfile)

    if args.dryrun:
        database.commit = database.rollback

    if args.mock:
        import pprint
        mock_data = load_mock(args.mock)
        parsed_mock_data = _parse_hr_person(database,
                                            source_system,
                                            mock_data)
        logger.debug1(u'Parsed mock data as:\n{}'.format(
            pprint.pformat(parsed_mock_data)))
        body = json.dumps({u'sub': None})
        callback(database, source_system, u'', u'', body,
                 datasource=lambda *x: parsed_mock_data)
    else:
        logger.info(u'Starting {}'.format(prog_name))
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
        logger.info(u'Stopping {}'.format(prog_name))


if __name__ == "__main__":
    main()
