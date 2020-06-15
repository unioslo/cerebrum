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
from __future__ import unicode_literals

import time
import datetime
import requests
import json
from collections import OrderedDict

from six import text_type, integer_types
from mx import DateTime
from aniso8601.exceptions import ISOFormatError

import cereconf

from Cerebrum import Errors
from Cerebrum.utils.date import parse_date, date_to_datetime, apply_timezone
from Cerebrum.Utils import Factory, read_password
from Cerebrum.modules.event.mapping import CallbackMap
from Cerebrum.modules.automatic_group.structure import (get_automatic_group,
                                                        update_memberships)

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Namespace,
                                           Configuration)
from Cerebrum.config.settings import String
from Cerebrum.config.loader import read, read_config

from Cerebrum.modules.event_consumer import get_consumer
from Cerebrum.modules.event_consumer.config import AMQPClientConsumerConfig
from Cerebrum.modules.event_publisher.mock_client import MockClient
from Cerebrum.modules.event_publisher.amqp_publisher import (PublisherConfig,
                                                             AMQP091Publisher)

logger = Factory.get_logger('cronjob')
AccountClass = Factory.get('Account')
callback_functions = CallbackMap()
callback_filters = CallbackMap()

# INTEGER_TYPE is long in in python2 and will be int in python3
INTEGER_TYPE = integer_types[-1]
LEADER_GROUP_PREFIX = 'adm-leder-'


def filter_meta(l):
    """Filter out the __metadata key of a dict."""
    return dict(filter(lambda (k, _): k != '__metadata', l.items()))


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


class SourceSystemNotReachedError(Exception):
    """Package not received from source system."""


class EntityDoesNotExistInSourceSystemError(Exception):
    """Entity does not exist in source system."""


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


def load_config(cls, name, filepath=None):
    """Load config for consumer or publisher"""
    config_cls = cls()
    if filepath:
        logger.info('Loading config file: %r', filepath)
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, name)
        logger.info('no filepath, using defaults')
    logger.info('validating config_cls')
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
    address_types = ('legalAddress',
                     'workMailingAddress',
                     'workVisitingAddress')
    m = {'legalAddress': co.address_post_private,
         'workMailingAddress': co.address_post,
         'workVisitingAddress': co.address_street,
         'city': 'city',
         'postalCode': 'postal_number',
         'streetAndHouseNumber': 'address_text'}
    r = {x: d.get(x, {}) for x in address_types}
    logger.info('parsing %i addresses', len(r))
    # Visiting address should be a concoction of real address and a
    # meta-location
    if r.get('workVisitingAddress'):
        r['workVisitingAddress']['streetAndHouseNumber'] = '{}\n{}'.format(
            r.get('workVisitingAddress').get('streetAndHouseNumber'),
            r.get('workVisitingAddress').get('location'))
    return tuple([(k, tuple(sorted(filter_elements(translate_keys(v, m))))) for
                  (k, v) in filter_elements(
            translate_keys(filter_meta(r), m))])


def verify_sap_header(header):
    """Verify that the headers originate from SAP"""
    if 'sap-server' in header:
        return header['sap-server'] == 'true'
    return False


def parse_names(d):
    """Parse data from SAP and return names.

    :type d: dict
    :param d: Data from SAP

    :rtype: tuple((PersonName('FIRST'), 'first'),
                  (PersonName('FIRST'), 'last'))
    :return: A tuple with the fields that should be updated"""
    logger.info('parsing names')
    co = Factory.get('Constants')
    return ((co.name_first, d.get('firstName')),
            (co.name_last, d.get('lastName')))


def parse_contacts(d):
    """Parse data from SAP and return contact information.

    :type d: dict
    :param d: Data from SAP

    :rtype: ((ContactInfo('PHONE'), (('contact_pref', n),
                                     ('contact_value', v),
                                     ('description', None))),)
    :return: A tuple with the fields that should be updated"""
    logger.info('parsing contacts')
    co = Factory.get('Constants')
    # TODO: Validate/clean numbers with phonenumbers?
    m = {'workPhone': co.contact_phone,
         'workMobile': co.contact_mobile_phone,
         'privateMobile': co.contact_private_mobile,
         'publicMobile': co.contact_private_mobile_visible}

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
        return (('name_variant', variant),
                ('name_language', lang),
                ('name', name))

    co = Factory.get('Constants')
    logger.info('parsing titles')
    titles = []
    if d.get('personalTitle'):
        titles.extend(
            [make_tuple(co.personal_title,
                        co.language_en,
                        d.get('personalTitle', {}).get('en'))] +
            map(lambda lang: make_tuple(
                co.personal_title,
                lang,
                d.get('personalTitle', {}).get('nb')),
                [co.language_nb, co.language_nn]))
    # Select appropriate work title.
    assignment = None
    for e in d.get('assignments', {}).get('results', []):
        if not e.get('jobTitle'):
            continue
        if e.get('primaryAssignmentFlag'):
            assignment = e
            break
        if not assignment:
            assignment = e
        elif (float(e.get('agreedFTEPercentage')) >
              float(assignment.get('agreedFTEPercentage'))):
            assignment = e
    if assignment:
        titles.extend(map(lambda (lang_code, lang_str): make_tuple(
            co.work_title,
            lang_code,
            assignment.get('jobTitle').get(lang_str)),
                          [(co.language_nb, 'nb'),
                           (co.language_nn, 'nb'),
                           (co.language_en, 'en')]))
    return filter(lambda ((vk, vn), (lk, lv), (nk, nv)): nv, titles)


def parse_external_ids(d):
    """Parse data from SAP and return external ids (i.e. passnr).

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(EntityExternalId('PASSNR'),
                   '000001')]
    :return: A list of tuples with the external_ids"""
    co = Factory.get('Constants')
    external_ids = [(co.externalid_sap_ansattnr, unicode(d.get('personId')))]
    logger.info('parsing %i external ids', len(external_ids))
    if d.get('passportIssuingCountry') and d.get('passportNumber'):
        external_ids.append(
            (co.externalid_pass_number,
             co.make_passport_number(d.get('passportIssuingCountry'),
                                     d.get('passportNumber'))))
    if d.get('norwegianIdentificationNumber'):
        external_ids.append(
            (co.externalid_fodselsnr, d.get('norwegianIdentificationNumber')))

    return filter_elements(external_ids)


def _get_ou(database, placecode=None):
    """Populate a Cerebrum-OU-object from the DB."""
    if not placecode:
        return None
    ou = Factory.get('OU')(database)
    ou.clear()
    try:
        ou.find_stedkode(
            *map(''.join,
                 zip(*[iter(str(
                     placecode))] * 2)) + [cereconf.DEFAULT_INSTITUSJONSNR]
        )
        return ou
    except Errors.NotFoundError:
        return None


def _sap_assignments_to_affiliation_map():
    co = Factory.get('Constants')
    return {'administrative': co.affiliation_status_ansatt_tekadm,
            'academic': co.affiliation_status_ansatt_vitenskapelig}


def parse_affiliations(database, d):
    """Parse data from SAP. Return affiliations and leader group ids.

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(('ou_id': 3),
                   ('affiliation', PersonAffiliation('ANSATT')),
                   ('status', PersonAffStatus('ANSATT', 'tekadm')),
                   (precedence', (50, 50)))]
    :return: A list of dicts with the fields that should be updated AND
        a list of leader group ids where the person should be a member"""
    co = Factory.get('Constants')
    affiliations = []
    leader_group_ids = []
    for x in d.get('assignments', {}).get('results', []):
        status = _sap_assignments_to_affiliation_map().get(
            x.get('jobCategory'))
        if not status:
            logger.warn('parse_affiliations: Unknown job category')
            # Unknown job category
            continue
        ou = _get_ou(database, placecode=x.get('locationId'))
        if not ou:
            logger.warn(
                'OU {} does not exist, '
                'cannot parse affiliation {} for {}'.format(
                    x.get('locationId'), status, x.get('personId')))
            continue
        main = x.get('primaryAssignmentFlag')
        if x.get('managerFlag'):
            leader_group_ids.append(get_automatic_group(
                database, text_type(x.get('locationId')), LEADER_GROUP_PREFIX
            ).entity_id)
        affiliations.append({
            'ou_id': ou.entity_id,
            'affiliation': co.affiliation_ansatt,
            'status': status,
            'precedence': (
                (INTEGER_TYPE(50), INTEGER_TYPE(50)) if main else None)
        })
    logger.info('parsed %i affiliations', len(affiliations))
    logger.info('parsed %i leader groups', len(leader_group_ids))
    return affiliations, leader_group_ids


def _sap_roles_to_affiliation_map():
    co = Factory.get('Constants')
    return OrderedDict(
        [('INNKJØPER', co.affiliation_tilknyttet_innkjoper),
         ('EF-FORSKER', co.affiliation_tilknyttet_ekst_forsker),
         ('EMERITUS', co.affiliation_tilknyttet_emeritus),
         ('BILAGSLØNN', co.affiliation_tilknyttet_bilag),
         ('GJ-FORSKER', co.affiliation_tilknyttet_gjesteforsker),
         ('ASSOSIERT', co.affiliation_tilknyttet_assosiert_person),
         ('EF-STIP', co.affiliation_tilknyttet_ekst_stip),
         ('GRP-LÆRER', co.affiliation_tilknyttet_grlaerer),
         ('EKST-KONS', co.affiliation_tilknyttet_ekst_partner),
         ('PCVAKT', co.affiliation_tilknyttet_pcvakt),
         ('EKST-PART', co.affiliation_tilknyttet_ekst_partner),
         ('KOMITEMEDLEM', co.affiliation_tilknyttet_komitemedlem),
         ('STEDOPPLYS', None),
         ('POLS-ANSAT', None)])


def parse_roles(database, data):
    """Parse data from SAP and return existing roles.

    :type d: dict
    :param d: Data from SAP

    :rtype: [tuple(('ou_id': 3),
                   ('affiliation', PersonAffiliation('TILKNYTTET')),
                   ('status', PersonAffStatus('TILKNYTTET', 'pcvakt')),
                   (precedence', None))]
    :return: A list of tuples representing them roles."""
    role2aff = _sap_roles_to_affiliation_map()
    r = []
    for role in data.get('roles', {}).get('results', []):
        ou = _get_ou(database, placecode=role.get('locationId'))
        if not ou:
            logger.warn('OU %r does not exist, '
                        'cannot parse affiliation %r for %r',
                        role.get('locationId'),
                        role2aff.get(role.get('roleName')),
                        data.get('personId'))
        elif role2aff.get(role.get('roleName')):
            r.append({'ou_id': ou.entity_id,
                      'affiliation': role2aff.get(
                          role.get('roleName')).affiliation,
                      'status': role2aff.get(role.get('roleName')),
                      'precedence': None})
    logger.info('parsed %i roles', len(r))
    return sorted(r,
                  key=(lambda x: role2aff.values().index(x.get('status')) if
                  x.get('status') in role2aff.values() else len(r)),
                  reverse=True)


def _parse_hr_person(database, source_system, data):
    """Collects parsed information from SAP."""
    co = Factory.get('Constants')
    affiliations, leader_group_ids = parse_affiliations(database, data)
    return {
        'id': data.get('personId'),
        'addresses': parse_address(data),
        'names': parse_names(data),
        'birth_date': DateTime.DateFrom(
            data.get('dateOfBirth')),
        'gender': {'Kvinne': co.gender_female,
                   'Mann': co.gender_male}.get(
            data.get('gender'),
            co.gender_unknown),
        'external_ids': parse_external_ids(data),
        'contacts': parse_contacts(data),
        'leader_group_ids': leader_group_ids,
        'affiliations': affiliations,
        'roles': parse_roles(database, data),
        'titles': parse_titles(data),
        'reserved': not data.get('allowedPublicDirectoryFlag')
    }


def _request_sap_data(config, url, params=None, ignore_read_password=False):
    if not params:
        params = {}
    if ignore_read_password:
        headers = {'Accept': 'application/json',
                   'X-Gravitee-API-Key': 'true'}
    else:
        headers = {'Accept': 'application/json',
                   'X-Gravitee-API-Key': read_password(
                       user=config.auth_user,
                       system=config.auth_system)}
    try:
        logger.debug4('Fetching %r', url)
        response = requests.get(url, headers=headers, params=params)
        logger.debug4('Fetch completed')
    except Exception as e:
        # Be polite on connection errors. Connection errors seldom fix
        # themselves quickly.
        import time
        time.sleep(1)
        raise RemoteSourceUnavailable(str(e))
    if not verify_sap_header(response.headers):
        logger.warn('Source system not reached')
        raise SourceSystemNotReachedError
    return response


def _parse_sap_data(response, url=None):
    if response.status_code == 200:
        return json.loads(response.text).get('d', None)
    elif response.status_code == 404:
        raise EntityDoesNotExistInSourceSystemError('404: Not Found')
    else:
        raise RemoteSourceError(
            'Could not fetch {} from remote source: {}: {}'.format(
                url, response.status_code, response.reason))


SAP_ATTRIBUTE_NAMES = {
    'assignments': {'id': 'assignmentId'},
    'roles': {'id': 'roleId'}
}


def _add_roles_and_assignments(person_data, config, ignore_read_password):
    """Add roles and assignments to person_data received from SAP

    The person_data does not include roles and assignments, but rather the
    uri to get it from. This method fetches it and adds it to person_data.

    :return reschedule_date: Date when the person should be reprocessed
    :rtype: datetime.date or None
    """
    hire_date_offset = datetime.timedelta(
        days=cereconf.SAP_START_DATE_OFFSET)
    reschedule_date = None
    for key in person_data:
        if (isinstance(person_data.get(key), dict) and
                '__deferred' in person_data.get(key) and
                'uri' in person_data.get(key).get('__deferred') and
                key in SAP_ATTRIBUTE_NAMES.keys()):
            # Fetch, unpack and store role/assignment data
            deferred_uri = person_data.get(key).get('__deferred').get('uri')
            # We filter by effectiveEndDate >= today to also get
            # future assignments and roles
            filter_param = {
                '$filter': "effectiveEndDate ge '{today}'".format(
                    today=datetime.date.today())
            }
            response = _request_sap_data(
                config,
                deferred_uri,
                params=filter_param,
                ignore_read_password=ignore_read_password)
            data = _parse_sap_data(response, url=deferred_uri)
            results_to_add = []
            for result in data.get('results'):
                try:
                    start_date = (
                            parse_date(result.get('effectiveStartDate')) -
                            hire_date_offset
                    )
                except (ValueError, AttributeError, ISOFormatError):
                    logger.error('Invalid date %s', result.get(
                        'effectiveStartDate'))
                    results_to_add.append(result)
                else:
                    if datetime.date.today() >= start_date:
                        results_to_add.append(result)
                    elif (reschedule_date is None or
                          start_date < reschedule_date):
                        reschedule_date = start_date
                        logger.info(('%s: %s, effectiveStartDate: %s '
                                     '→ reschedule_date: %s'),
                                    SAP_ATTRIBUTE_NAMES[key]['id'],
                                    result.get(SAP_ATTRIBUTE_NAMES[key]['id']),
                                    result.get('effectiveStartDate'),
                                    reschedule_date)
            person_data.update({key: {'results': results_to_add}})
    return reschedule_date


def get_hr_person(config, database, source_system, url,
                  ignore_read_password=False):
    """Collect a person entry from the remote source system and parse the data.

    If a person has assignments or roles which are not yet in effect,
    they will not be added to the hr_person. Instead the message will be
    rescheduled so that it can be reprocessed at a later time.

    :param config: Authentication data
    :param database: Database object
    :param source_system: The source system code
    :param url: The URL to contact for collection
    :param ignore_read_password: Do not include a valid api-key in header
    :rtype: tuple
    :return The parsed data from the remote source system and reschedule_date

    :raises: RemoteSourceUnavailable if the remote system can't be contacted"""

    def _get_person_data():
        response = _request_sap_data(config,
                                     url,
                                     ignore_read_password=ignore_read_password)
        person_data = _parse_sap_data(response, url=url)
        reschedule_date = _add_roles_and_assignments(person_data,
                                                     config,
                                                     ignore_read_password)
        return person_data, reschedule_date

    person_data, reschedule_date = _get_person_data()
    return (_parse_hr_person(database, source_system, person_data),
            reschedule_date)


def get_cerebrum_person(database, ids):
    """Get a person object from Cerebrum.

    If the person does not exist in Cerebrum, the returned object is
    clear()'ed"""
    pe = Factory.get('Person')(database)
    try:
        pe.find_by_external_ids(*ids)
        logger.info('Found existing person with id: %r', pe.entity_id)
    except Errors.NotFoundError:
        logger.info('Could not find existing person with one of ids: %r', ids)
        pe.clear()
    except Errors.TooManyRowsError as e:
        raise EntityNotResolvableError(
            'Person in source system maps to multiple persons in Cerebrum. '
            'Manual intervention required: {}'.format(e))
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
                'Person id %r does not have exactly one account',
                cerebrum_person.entity_id)
            return
        ac = Factory.get('Account')(database)
        ac.find(accounts[0]['account_id'])
        co = Factory.get('Constants')(database)
        account_types = ac.get_account_types()
        if method.__name__ is AccountClass.del_account_type.__name__:
            if len(account_types) == 1:
                logger.info('Cannot delete last account_type')
                return
            if not ac.list_accounts_by_type(ou_id=ou_id,
                                            affiliation=affiliation,
                                            account_id=ac.entity_id):
                logger.info('account_type already deleted '
                            '(aff: %r, ou_id: %i)', affiliation, ou_id)
                return
        if method.__name__ is AccountClass.set_account_type.__name__:
            for at in account_types:
                if (at['ou_id'], at['affiliation']) == (ou_id, affiliation):
                    logger.info('account_type already exists '
                                '(aff: %r, ou_id: %i)', affiliation, ou_id)
                    return
        for account_type in account_types:
            if not int(co.affiliation_ansatt) == account_type['affiliation']:
                logger.info('Account has affiliation(s) besides '
                            '%r', co.affiliation_ansatt)
                return
            aff_info = cerebrum_person.list_affiliations(
                person_id=account_type['person_id'],
                ou_id=account_type['ou_id'],
                affiliation=account_type['affiliation'],
            )
            if aff_info:
                if not int(co.system_sap) == aff_info[0]['source_system']:
                    logger.info('Account has affiliation from source(s) other '
                                'than %r', co.system_sap)
                    return
        logger.info('%r for account: %r', method.__name__, ac.entity_id)
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
            cerebrum_person.gender == hr_person.get('gender') and
            cerebrum_person.birth_date == hr_person.get('birth_date')):
        cerebrum_person.populate(
            hr_person.get('birth_date'),
            hr_person.get('gender'))
        cerebrum_person.write_db()
        logger.info('Added birth date %r and gender %r for %i',
                    hr_person.get('birth_date'),
                    hr_person.get('gender'),
                    cerebrum_person.entity_id)


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
                    lambda (k, v): k != 'precedence',
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
                        {'ou_id': 'ou_id',
                         'affiliation': 'affiliation',
                         'status': 'status'}
                    )
                )
            )
        ),
        cerebrum_affiliations)
    if mode == 'remove':
        return [
            dict(filter(lambda (k, v): k in ('ou_id', 'affiliation'), x) +
                 (('source', source_system),))
            for x in set(in_cerebrum) - set(in_hr)]
    elif mode == 'add':
        to_add = set(in_hr) - set(in_cerebrum)
        to_ensure = set(in_hr) & set(in_cerebrum)
        return [dict(x) for x in to_add | to_ensure]
    else:
        raise Errors.ProgrammingError(
            'Invalid mode {} supplied to _find_affiliations'.format(
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
            hr_person.get('affiliations'),
            _sap_assignments_to_affiliation_map,
            source_system,
            'remove'):
        del_account_type(database,
                         cerebrum_person,
                         affiliation['ou_id'],
                         affiliation['affiliation'])
        cerebrum_person.delete_affiliation(**affiliation)
        logger.info('Removing affiliation %r for id: %r',
                    _stringify_for_log(affiliation),
                    cerebrum_person.entity_id)
    for affiliation in _find_affiliations(
            cerebrum_person,
            hr_person.get('affiliations'),
            _sap_assignments_to_affiliation_map,
            source_system,
            'add'):
        cerebrum_person.populate_affiliation(source_system, **affiliation)
        logger.info('Adding affiliation %r for id: %r',
                    _stringify_for_log(affiliation),
                    cerebrum_person.entity_id)
    cerebrum_person.write_db()
    for affiliation in _find_affiliations(
            cerebrum_person,
            hr_person.get('affiliations'),
            _sap_assignments_to_affiliation_map,
            source_system,
            'add'):
        set_account_type(database,
                         cerebrum_person,
                         affiliation['ou_id'],
                         affiliation['affiliation'])
        logger.info('Setting account type for id: %r',
                    cerebrum_person.entity_id)


def update_roles(database, source_system, hr_person, cerebrum_person):
    """Update a person in Cerebrum with the latest roles.

    :param database: A database object
    :param source_system: The source system code
    :param hr_person: The parsed data from the remote source system
    :param cerebrum_person: The Person object to be updated.
    """
    for role in _find_affiliations(
            cerebrum_person,
            hr_person.get('roles'),
            _sap_roles_to_affiliation_map,
            source_system,
            'remove'):
        cerebrum_person.delete_affiliation(**role)
        logger.info('Removing role %r for id: %r',
                    _stringify_for_log(role),
                    cerebrum_person.entity_id)
    for role in _find_affiliations(
            cerebrum_person,
            hr_person.get('roles'),
            _sap_roles_to_affiliation_map,
            source_system,
            'add'):
        cerebrum_person.populate_affiliation(source_system, **role)
        logger.info('Ensuring role %r for id: %r',
                    _stringify_for_log(role),
                    cerebrum_person.entity_id)


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
    to_remove = names - set(hr_person.get('names'))
    to_add = set(hr_person.get('names')) - names
    if to_remove:
        logger.info('Purging names of types %r for id: %r',
                    map(lambda (k, _): _stringify_for_log(k), to_remove),
                    cerebrum_person.entity_id)
    cerebrum_person.affect_names(
        source_system,
        *map(lambda (k, _): k, to_remove | to_add))
    for (k, v) in to_add:
        cerebrum_person.populate_name(k, v)
        logger.info('Adding name %r of type %r for id: %r',
                    v, k, cerebrum_person.entity_id)


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
    external_ids = set(map(lambda e: (e['id_type'], e['external_id']),
                           cerebrum_person.get_external_id(
                               source_system=source_system)))
    to_remove = external_ids - set(hr_person.get('external_ids'))
    to_add = set(hr_person.get('external_ids')) - external_ids
    cerebrum_person.affect_external_id(
        source_system,
        *map(lambda (k, _): k, to_remove | to_add))
    if to_remove:
        logger.info(
            'Purging externalids of types %r for id: %r',
            map(lambda (k, _): _stringify_for_log(co.EntityExternalId(k)),
                to_remove),
            cerebrum_person.entity_id)
    for (k, v) in to_add:
        cerebrum_person.populate_external_id(
            source_system, k, v)
        logger.info('Adding externalid %r for id: %r',
                    (_stringify_for_log(co.EntityExternalId(k)), v),
                    cerebrum_person.entity_id)


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
                              ('entity_id', 'source_system', 'address_type',
                               'p_o_box', 'country'),
                              cerebrum_person.get_entity_address(
                                  source=source_system))

    for (k, v) in addresses - set(hr_person.get('addresses')):
        cerebrum_person.delete_entity_address(source_system, k)
        logger.info('Removing address %r for id: %r',
                    (_stringify_for_log(k), v),
                    cerebrum_person.entity_id)
    for (k, v) in set(hr_person.get('addresses')) - addresses:
        cerebrum_person.add_entity_address(source_system, k, **dict(v))
        logger.info('Adding address %r for id: %r',
                    (_stringify_for_log(k), v),
                    cerebrum_person.entity_id)


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
                              'contact_type', 'contact_description',
                              'contact_alias', 'last_modified'),
                             cerebrum_person.get_contact_info(
                                 source=source_system))
    for (k, v) in contacts - set(hr_person.get('contacts')):
        (p, v, _d) = (value for (_, value) in v)
        cerebrum_person.delete_contact_info(source_system, k, p)
        logger.info('Removing contact (%r) of type %r with preference %r for '
                    'id: %r',
                    v,
                    _stringify_for_log(k),
                    p,
                    cerebrum_person.entity_id)
    for (k, v) in set(hr_person.get('contacts')) - contacts:
        (p, v, _d) = (value for (_, value) in v)
        cerebrum_person.add_contact_info(source_system, k, v, p)
        logger.info('Adding contact %r of type %r with preference %r for '
                    'id: %r',
                    v,
                    _stringify_for_log(k),
                    p,
                    cerebrum_person.entity_id)


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
                         name_variant=[co.work_title,
                                       co.personal_title])))
    for e in set(hr_person.get('titles')) - titles:
        cerebrum_person.add_name_with_language(**dict(e))
        logger.info('Adding title %r for id: %r',
                    _stringify_for_log(e),
                    cerebrum_person.entity_id)
    for e in titles - set(hr_person.get('titles')):
        cerebrum_person.delete_name_with_language(**dict(e))
        logger.info('Removing title %r for id: %r',
                    _stringify_for_log(e),
                    cerebrum_person.entity_id)


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
        logger.info('Adding id: %r to reservation group',
                    cerebrum_person.entity_id)
    elif not hr_person.get('reserved') and in_reserved_group:
        gr.remove_member(cerebrum_person.entity_id)
        logger.info('Removing id: %r from reservation group',
                    cerebrum_person.entity_id)


def cerebrum_leader_group_memberships(gr, co, cerebrum_person):
    return (r['group_id'] for r in
            gr.search(member_id=cerebrum_person.entity_id,
                      name=LEADER_GROUP_PREFIX + '*',
                      group_type=co.group_type_affiliation,
                      filter_expired=True,
                      fetchall=False))


def update_leader_group_memberships(database, hr_person, cerebrum_person):
    gr = Factory.get('Group')(database)
    co = Factory.get('Constants')(database)
    hr_memberships = set(hr_person.get('leader_group_ids'))
    cerebrum_memberships = set(
        cerebrum_leader_group_memberships(gr, co, cerebrum_person)
    )
    logger.info('Assert (person: %s) is member of (leader_groups: %s)',
                cerebrum_person.entity_id,
                hr_memberships)
    update_memberships(gr,
                       cerebrum_person.entity_id,
                       cerebrum_memberships,
                       hr_memberships)


def perform_update(database, source_system, hr_person, cerebrum_person):
    """Update or create a person."""
    logger.info('Starting perform_update for %r', hr_person.get('id'))
    update_person(database, source_system, hr_person, cerebrum_person)
    update_external_ids(database, source_system, hr_person, cerebrum_person)
    update_names(database, source_system, hr_person, cerebrum_person)
    update_addresses(database, source_system, hr_person, cerebrum_person)
    update_contact_info(database, source_system, hr_person, cerebrum_person)
    update_titles(database, source_system, hr_person, cerebrum_person)
    update_roles(database, source_system, hr_person, cerebrum_person)
    update_affiliations(database, source_system, hr_person, cerebrum_person)
    update_leader_group_memberships(database, hr_person, cerebrum_person)
    update_reservation(database, hr_person, cerebrum_person)
    logger.info('Perform_update for %r done', cerebrum_person.entity_id)


def perform_delete(database, source_system, hr_person, cerebrum_person):
    """Delete a person."""
    logger.info('Deleting: %r', cerebrum_person.entity_id)
    # Update person and external IDs
    if hr_person:
        update_person(database, source_system, hr_person, cerebrum_person)
        update_external_ids(
            database, source_system, hr_person, cerebrum_person)
    # Delete everything else
    update_names(database,
                 source_system,
                 {'names': []},
                 cerebrum_person)
    update_addresses(database,
                     source_system,
                     {'addresses': []},
                     cerebrum_person)
    update_contact_info(database,
                        source_system,
                        {'contacts': []},
                        cerebrum_person)
    update_titles(database,
                  source_system,
                  {'titles': []},
                  cerebrum_person)
    update_affiliations(database,
                        source_system,
                        {'affiliations': []},
                        cerebrum_person)
    update_roles(database,
                 source_system,
                 {'roles': []},
                 cerebrum_person)
    update_reservation(database,
                       {'reserved': False},
                       cerebrum_person)
    logger.info('%r deleted', cerebrum_person.entity_id)


def handle_person(database, source_system, url, datasource=get_hr_person):
    """Fetch info from the remote system, and perform changes.

    :param database: A database object
    :param source_system: The source system code
    :param url: The URL to the person object in the HR systems WS.
    :param datasource: The function used to fetch / parse the resource.

    :return reschedule_date: Date when the person should be reprocessed
    :rtype: datetime.date or None"""
    try:
        hr_person, reschedule_date = datasource(database, source_system, url)
        logger.info('Handling person %r from source system %r',
                    _stringify_for_log(hr_person.get('names')),
                    source_system)
    except EntityDoesNotExistInSourceSystemError:
        logger.warn('URL %s does not resolve in source system %r (404) - '
                    'deleting from Cerebrum',
                    url, source_system)
        hr_person = reschedule_date = None
    if hr_person:
        cerebrum_person = get_cerebrum_person(
            database,
            map(lambda (k, v): (k, v),
                hr_person.get('external_ids')))
    else:
        # assume manual ticket
        employee_number = url.split('(')[-1].strip(')')
        co = Factory.get('Constants')(database)
        cerebrum_person = Factory.get('Person')(database)
        cerebrum_person.find_by_external_id(
            id_type=co.externalid_sap_ansattnr,
            external_id=employee_number,
            source_system=co.system_sap,
            entity_type=co.entity_person)
    if hr_person and (hr_person.get('affiliations') or hr_person.get('roles')):
        perform_update(database, source_system, hr_person, cerebrum_person)
    elif cerebrum_person.entity_type:  # entity_type as indication of instance
        perform_delete(database, source_system, hr_person, cerebrum_person)
    else:
        logger.info('handle_person: no action performed')
        return reschedule_date
    logger.info('handle_person: commiting changes')
    cerebrum_person.write_db()
    database.commit()
    logger.info('handle_person: changes committed')
    return reschedule_date


def _reschedule_message(publisher, routing_key, message, reschedule_date):
    logger.info('Reschedule the message for %s', reschedule_date)
    reschedule_time = apply_timezone(date_to_datetime(reschedule_date))
    # Convert to timestamp and add to message
    message['nbf'] = int(time.mktime(reschedule_time.timetuple()))
    with publisher:
        publisher.publish(routing_key, message)


def callback(database, source_system, routing_key, content_type, body,
             datasource=get_hr_person, publisher=None):
    """Call appropriate handler functions."""
    try:
        message = json.loads(body)
        url = message.get('sub')
    except Exception as e:
        logger.warn('Received malformed message %r', body)
        return True
    message_processed = True
    try:
        reschedule_date = handle_person(database,
                                        source_system,
                                        url,
                                        datasource=datasource)
        logger.info('Successfully processed %r', body)
    except RemoteSourceUnavailable:
        message_processed = False
    except (RemoteSourceError, ErroneousSourceData) as e:
        logger.error('Failed processing %r:\n %r: %r',
                     body,
                     type(e).__name__, e)
    except EntityNotResolvableError as e:
        logger.critical('Failed processing %r:\n %r: %r',
                        body,
                        type(e).__name__,
                        e)
    except Exception as e:
        logger.error('Failed processing %r:\n %r', body, e, exc_info=True)
    else:
        if reschedule_date is not None:
            try:
                _reschedule_message(publisher,
                                    routing_key,
                                    message,
                                    reschedule_date)
            except Exception as e:
                logger.error('Failed to reschedule message \n %r', e)
    finally:
        # Always rollback, since we do an implicit begin and we want to discard
        # possible outstanding changes.
        database.rollback()
    return message_processed


def load_mock(mock_file):
    """Call appropriate handler functions."""
    with open(mock_file) as f:
        data = json.load(f).get('d')
        import pprint
        logger.debug1(
            'Using mock with data:\n%s', pprint.pformat(data, indent=4))
    return data


def main(args=None):
    """Start consuming messages."""
    import argparse
    import functools

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-c', '--config',
                        dest='configfile',
                        metavar='FILE',
                        default=None,
                        help='Use a custom configuration file for AMPQ '
                             'consumer')
    parser.add_argument('-p', '--publisher-config',
                        dest='publisher_configfile',
                        metavar='FILE',
                        default=None,
                        help='Use custom configuration for AMPQ publisher '
                             'used to reschedule messages')
    parser.add_argument('-m', '--mock',
                        dest='mock',
                        metavar='FILE',
                        default=None,
                        help='Load person object from JSON file')
    parser.add_argument(u'-u', u'--url',
                        action=type(
                            str(''), (argparse.Action,),
                            {'__call__': lambda s, p, ns, v, o=None: setattr(
                                ns, s.dest, json.dumps({'sub': v}))}),
                        dest=u'url',
                        metavar='<url>',
                        type=text_type,
                        default=None,
                        help=u'Load url manually')
    parser.add_argument('--dryrun',
                        dest='dryrun',
                        action='store_true',
                        default=False,
                        help='Do not commit changes')
    args = parser.parse_args(args)
    prog_name = parser.prog.rsplit('.', 1)[0]
    logger.info('Starting %r', prog_name)
    database = Factory.get('Database')()
    database.cl_init(change_program=prog_name)
    source_system = Factory.get('Constants')(database).system_sap
    config = load_config(SAPConsumerConfig,
                         'consumer_sap',
                         filepath=args.configfile)
    publisher_config = load_config(PublisherConfig,
                                   'sap_publisher',
                                   filepath=args.publisher_configfile)

    if args.dryrun:
        database.commit = database.rollback

    if args.mock:
        import pprint
        mock_data = load_mock(args.mock)
        parsed_mock_data = _parse_hr_person(database,
                                            source_system,
                                            mock_data)
        logger.debug1('Parsed mock data as:\n%r',
                      pprint.pformat(parsed_mock_data))
        body = json.dumps({'sub': None})
        callback(database, source_system, '', '', body,
                 datasource=lambda *x: (parsed_mock_data, None))
    elif args.url:
        datasource = functools.partial(get_hr_person, config.ws,
                                       ignore_read_password=True)
        publisher = MockClient(publisher_config)
        callback(
            database,
            source_system,
            # An example of a routing key which will land in the queue
            # q_cerebrum_sap_consumer:
            'no.uio.sap.scim.employees.modify',
            '',
            args.url,
            datasource=datasource,
            publisher=publisher,
        )
    else:
        logger.info('Starting %r', prog_name)
        datasource = functools.partial(
            get_hr_person,
            config.ws)
        publisher = AMQP091Publisher(publisher_config)
        consumer = get_consumer(
            functools.partial(
                callback,
                database,
                source_system,
                datasource=datasource,
                publisher=publisher,
            ),
            config=config.consumer)
        with consumer:
            try:
                consumer.start()
            except KeyboardInterrupt:
                consumer.stop()
            consumer.close()
    logger.info('Stopping %r', prog_name)


if __name__ == "__main__":
    main()
