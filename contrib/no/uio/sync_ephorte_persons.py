#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2014 University of Oslo, Norway
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
"""Syncronizator for persons in ePhorte.

This piece of software ensures existence of user accounts in ePhorte,
via the ePhorte web service.
"""

# TODO:
# - Handle primary account changes

import sys
import time
import pickle
from collections import defaultdict

try:
    import argparse
except ImportError:
    from Cerebrum.extlib import argparse

import cerebrum_path
import cereconf
cerebrum_path, cereconf  # Satisfy the linters.

from Cerebrum.Utils import Factory
from Cerebrum.Utils import read_password
from Cerebrum import Errors

from Cerebrum.modules.no.uio.Ephorte import EphorteRole
from Cerebrum.modules.no.uio.EphorteWS import EphorteWSError
from Cerebrum.modules.no.uio.Ephorte import EphortePermission

db = Factory.get('Database')(client_encoding='utf-8')

logger = Factory.get_logger("cronjob")
co = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
ephorte_role = EphorteRole(db)

ou_to_sko = {}
ephorte_ous = None


def get_email_address(pe):
    """Get a persons primary email address.

    :type pe: Person
    :param pe: The person

    :rtype: str
    :return: The persons primary email address
    """
    ac = Factory.get('Account')(db)
    ac.find(pe.get_primary_account())
    return ac.get_primary_mailaddress()


def get_username(pe):
    """Get the primary accounts username.

    :type pe: Person
    :param pe: The person

    :rtype: str
    :return: The primary accounts user name
    """
    ac = Factory.get('Account')(db)
    ac.find(pe.get_primary_account())
    return ac.account_name


def construct_user_id(pe):
    """Construct the persons user id in ePhorte.

    ePhorte uses FEIDE-ids to identify users.

    :type pe: Person
    :param pe: The person

    :rtype: str
    :return: The persons ePhorte (FEIDE) id
    """
    ac = Factory.get('Account')(db)
    ac.find(pe.get_primary_account())
    return "%s@%s" % (ac.account_name, cereconf.INSTITUTION_DOMAIN_NAME)


def get_sko(ou_id):
    """Get the stedkode for an OU.

    :type ou_id: int
    :param ou_id: The OU ID

    :rtype: str
    :return: The six-digit stedkode
    """
    sko = ou_to_sko.get(ou_id)

    if sko is None:
        ou.clear()
        ou.find(ou_id)
        sko = "%02i%02i%02i" % (ou.fakultet, ou.institutt, ou.avdeling)
        ou_to_sko[ou_id] = sko

    return sko


def ou_has_ephorte_spread(ou_id):
    """Check for ePhorte spread on an OU.

    :type ou_id: int
    :param ou_id: The OU ID

    :rtype: bool
    :return: Has spread?
    """
    global ephorte_ous

    if ephorte_ous is None:
        ephorte_ous = set([x['entity_id'] for x in
                          ou.list_all_with_spread(spreads=co.spread_ephorte_ou)])

    return ou_id in ephorte_ous


def update_person_info(pe, client):
    """Collect information about the person, and ensure that it exists in ePhorte.

    :type pe: Person
    :param pe: The person

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte
    """
    first_name = pe.get_name(co.system_cached, co.name_first)
    last_name = pe.get_name(co.system_cached, co.name_last)
    full_name = pe.get_name(co.system_cached, co.name_full)

    try:
        user_id = construct_user_id(pe)
        initials = get_username(pe)
    except Errors.NotFoundError:
        logger.warn('Skipping %d: Does not appear to have a primary account',
                    pe.entity_id)
        return

    try:
        email_address = get_email_address(pe)
    except Errors.NotFoundError:
        logger.warn('Email address non-existent for %s', user_id)
        email_address = None

    telephone = (lambda x: x[0]['contact_value'] if len(x) else None)(
        pe.get_contact_info(source=co.system_sap, type=co.contact_phone))
    # TODO: Has not been exported before. Export nao?
    mobile = None
    tmp_addr = (lambda x: x[0] if len(x) else None)(pe.get_entity_address(
        source=co.system_sap, type=co.address_street))
    if tmp_addr:
        street_address = tmp_addr['address_text']
        zip_code = tmp_addr['postal_number']
        city = tmp_addr['city']
    else:
        street_address = zip_code = city = None

    logger.info('Ensuring existence of %s, with params: %s', user_id, str((
        first_name, None, initials, last_name, full_name, initials,
        email_address, telephone, mobile, street_address, zip_code, city)))
    try:
        client.ensure_user(user_id, first_name, None, last_name, full_name,
                           initials, email_address, telephone, mobile,
                           street_address, zip_code, city)
    except EphorteWSError, e:
        logger.warn('Could not ensure existence of %s in ePhorte: %s',
                    user_id, str(e))

_perm_codes = None
def perm_code_id_to_perm(code):
    """Convert from ephorte perm code to cerebrum code"""
    global _perm_codes
    if _perm_codes:
        return _perm_codes[code]
    import functools
    logger.debug("Mapping perm codes")
    _perm_codes = dict((str(x), x)
            for x in map(functools.partial(getattr, co), dir(co))
            if isinstance(x, co.EphortePermission))

def user_details_to_perms(user_details):
    """Convert result from Cerebrum2EphorteClient.get_user_details()
    :type user_details tuple(dict, list(dict), list)
    :param user_details: Return value from get_user_details()

    :rtype list(authcode, boolean, ou)"""
    authzs = user_details[1]
    return [(perm_code_id_to_perm(x['AccessCodeId']), x['IsAutorizedForAllOrgUnits'], x['OrgId'])
            for x in authzs]


def list_perm_for_person(person):
    ret = []
    for row in EphortePermission(db).list_permission(person_id=person.entity_id):
        perm_type = row['perm_type']
        if perm_type:
            perm_type = str(co.EphortePermission(perm_type))
        sko = get_sko(row['adm_enhet'])
        if sko == '999999':
            sko = None
        ret.append((perm_type, False, sko))
    return ret

def fullsync_persons(client, selection_spread):
    """Full sync of person information.

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte

    :type selection_spread: Spread
    :param selection_spread: A person must have this spread to be synced
    """
    for person in select_persons_for_update(selection_spread):
        update_person_info(pe=person, client=client)


def select_persons_for_update(selection_spread):
    """Yield persons satisfying criteria.

    :type selection_spread: Spread
    :param selection_spread: The spread to filter by

    :rtype: generator
    :return: A generator that yields Person objects
    """
    pe = Factory.get('Person')(db)
    for p in pe.list_all_with_spread(selection_spread):
        pers = Factory.get('Person')(db)
        pers.find(p['entity_id'])
        yield pers


def select_events_by_person(clh, change_key, change_types, selection_spread):
    """Yield unhandled events, sorted by person_id.

    :type clh: CLHandler
    :param clh: Change log handler instance

    :type change_key: str
    :param change_key: Handled events are marked with this key

    :type change_types: iterable
    :param change_types: Get events of this type

    :type selection_spread: Spread
    :param selection_spread: A person must have this spread to be synced

    :rtype: generator
    :return: A generator that yields (person_id, events)
    """
    #too_old = time.time() - int(self.config['changes_too_old_seconds'])
    too_old = time.time() - 60*60*24*365
    # TODO

    logger.debug("Fetching unhandled events using change key: %s", change_key)
    all_events = clh.get_events(change_key, change_types)
    logger.debug("Found %d events to process", len(all_events))

    events_by_person = defaultdict(list)
    for event in all_events:
        # Ignore too old changes
        if int(event['tstamp']) < too_old:
            logger.info("Skipping too old change_id: %s" % event['change_id'])
            clh.confirm_event(event)
            continue

        events_by_person[event['subject_entity']].append(event)

    for person_id, events in events_by_person.iteritems():
        if not sanity_check_person(person_id=person_id, selection_spread=selection_spread):
            # TBD: confirm event?
            continue

        yield (person_id, events)


def sanity_check_person(person_id, selection_spread):
    pe = Factory.get('Person')(db)

    try:
        pe.find(person_id)
    except Errors.NotFoundError:
        logger.warn('person_id:%s does not exist, skipping', person_id)
        return False

    try:
        construct_user_id(pe)
    except Errors.NotFoundError:
        logger.warn('person_id:%s does not have a primary account, skipping', person_id)
        return False

    if not pe.has_spread(spread=selection_spread):
        logger.warn('person_id:%s has ePhorte role, but no ePhorte spread, skipping',
                    person_id)
        return False

    return True


def fullsync_roles_and_authz(client, selection_spread):
    """Full sync of roles and authorizations.

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte

    :type selection_spread: Spread
    :param selection_spread: A person must have this spread to be synced
    """
    for person in select_persons_for_update(selection_spread):
        if sanity_check_person(person_id=person.entity_id, selection_spread=selection_spread):
            update_person_roles_and_authz(pe=person, client=client)


def quicksync_roles_and_authz(client, selection_spread, config, commit):
    """Quick sync for roles and authorizations.

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte

    :type selection_spread: Spread
    :param selection_spread: A person must have this spread to be synced

    :type config: Config
    :param config: Configuration

    :type commit: bool
    :param commit: Commit confirmed events?
    """
    from Cerebrum.modules import CLHandler
    clh = CLHandler.CLHandler(db)
    pe = Factory.get('Person')(db)

    change_key = 'eph_sync'
    change_types_roles = (co.ephorte_role_add, co.ephorte_role_rem, co.ephorte_role_upd)
    change_types_perms = (co.ephorte_perm_add, co.ephorte_perm_rem)
    change_types_adds = (co.ephorte_role_add, co.ephorte_perm_add)
    change_types = change_types_roles + change_types_perms

    event_selector = select_events_by_person(
        clh=clh,
        change_key=change_key,
        change_types=change_types,
        selection_spread=selection_spread)

    for person_id, events in event_selector:
        pe.clear()
        pe.find(person_id)

        # We need to remove all roles and authz, unless we only got 'add' events.
        remove_all = not all(e['change_type_id'] in change_types_adds for e in events)

        if remove_all:
            try:
                update_person_roles_and_authz(client=client, pe=pe)
            except Exception, e:
                logger.warn('Failed to update all roles and authz for person_id:%s', person_id)
                logger.exception(e)
            else:
                logger.debug('Confirming events: %s', [e['change_id'] for e in events])

                for event in events:
                    clh.confirm_event(event)

                if commit:
                    clh.commit_confirmations()

            continue

        # We only need to add roles/authz.
        for event in events:
            logger.debug('Processing change_id %s (%s), from %s subject_entity:%s',
                         event['change_id'],
                         co.ChangeType(int(event['change_type_id'])),
                         event['tstamp'],
                         event['subject_entity'])
            change_fun = update_person_roles
            if event['change_type_id'] in change_types_perms:
                change_fun = update_person_authz
            try:
                if change_fun(pe, client, event=event):
                    clh.confirm_event(event)
            except Exception, e:
                logger.warn('Failed to process change_id:%s', event['change_id'])
                logger.exception(e)
            else:
                if commit:
                    clh.commit_confirmations()

    if commit:
        clh.commit_confirmations()


def update_person_roles_and_authz(pe, client):
    """Removes all roles and authorizations, then re-adds everything.

    :type pe: Person
    :param pe: The person to update

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte
    """
    remove_person_roles_and_authz(client=client, pe=pe)
    update_person_roles(client=client, pe=pe)
    update_person_authz(pe, client)


def remove_person_roles_and_authz(pe, client):
    """Removes all roles and authorizations for a person.

    :type pe: Person
    :param pe: The person remove roles and authz for

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte
    """
    user_id = construct_user_id(pe=pe)

    try:
        client.disable_roles_and_authz_for_user(user_id=user_id)
    except EphorteWSError, e:
        logger.warn('Could not remove all roles and authz for person_id:%s: %s',
                    pe.entity_id, e)
        raise

    logger.info('Removed all roles and authz for person_id:%s', pe.entity_id)


def update_person_authz(person, client, userid=None, event=None, remove_ok=False):
    try:
        if userid is None:
            userid = construct_user_id(person)
        logger.info("Updating perms for %s", userid)
        ephorte_perms = set(user_details_to_perms(client.get_user_details(userid)))
        for perm in ephorte_perms:
            logger.debug("Found perm for %s in ephorte: %s@%s, authorized=%s", userid, perm[0], perm[2], perm[1])
        cerebrum_perms = set(list_perm_for_person(person))
        for perm in cerebrum_perms:
            logger.debug("Setting perm for %s: %s@%s, authorized=%s", userid, perm[0], perm[2], perm[1])

        # Delete perms?
        if remove_ok:
            superfluous = ephorte_perms.difference(cerebrum_perms)
            if superfluous:
                for perm in superfluous:
                    logger.info("Deleting perm for %s: %s@%s, authorized=%s", userid, perm[0], perm[2], perm[1])
                client.disable_roles_and_authz_for_user(userid)
            
        for perm in cerebrum_perms:
            if perm in ephorte_perms:
                logger.info("Readding perm for %s: %s@%s, authorized=%s", userid, perm[0], perm[2], perm[1])
            else:
                logger.info("Adding new perm for %s: %s@%s, authorized=%s", userid, perm[0], perm[2], perm[1])
            client.ensure_access_code_authorization(userid, perm[0], perm

    except Exception, e:
        logger.exception("Something went wrong")
        return False
    return True


def get_target_role_by_event(event):
    change_params = pickle.loads(event['change_params'])

    # rolle_type and arkivdel may have been set to the code_str or
    # a string representation of the int
    try:
        role_id = int(change_params['rolle_type'])
    except ValueError:
        role_id = change_params['rolle_type']

    try:
        arkivdel = int(change_params['arkivdel'])
    except ValueError:
        arkivdel = change_params['arkivdel']

    return {
        'role_id': str(co.EphorteRole(role_id)),
        'arkivdel': str(co.EphorteArkivdel(arkivdel)),
        'adm_enhet': event['dest_entity'],
    }

def user_details_to_roles(user_details):
    """Convert result from Cerebrum2EphorteClient.get_user_details()
    to arguments suitable for ensure_role_for_user (user_id omitted).
    :type user_details tuple(dict, list(dict), list)
    :param user_details: Return value from get_user_details()

    :rtype list(dict)"""
    roles = user_details[2]
    return [{
        'arkivdel': x['FondsSeriesId'],
        'journalenhet': x['RegistryManagementUnitId'],
        'role_id': x['Role']['RoleId'],
        'ou_id': x['Org']['OrgId'],
        'default_role': x['IsDefault'],
        'job_title': x['JobTitle']
        } for x in roles]

def update_person_roles(pe, client, event=None, delete_superfluous=False):
    if event:
        target = get_target_role_by_event(event=event)

    user_id = construct_user_id(pe=pe)

    args = {}

    ephorte_roles = set(tuple(sorted(x.items())) 
                        for x in user_details_to_roles(client.get_user_details(user_id)))
    cerebrum_roles = set()
    for role in ephorte_role.list_roles(person_id=pe.entity_id):
        try:
            args['arkivdel'] = str(co.EphorteArkivdel(role['arkivdel']))
            args['journalenhet'] = str(co.EphorteJournalenhet(role['journalenhet']))
            args['role_id'] = str(co.EphorteRole(role['role_type']))
        except (TypeError, Errors.NotFoundError):
            logger.warn("Unknown arkivdel, journalenhet or role type, skipping role %s", role)
            continue

        # If we are looking for a specific role, is this the one?
        if (event and (args['role_id'] != target['role_id'] or
                       args['arkivdel'] != target['arkivdel'] or
                       role['adm_enhet'] != target['adm_enhet'])):
            continue

        args['ou_id'] = get_sko(ou_id=role['adm_enhet'])
        args['job_title'] = role['rolletittel']
        args['default_role'] = role['standard_role'] == 'T'

        # Check if adm_enhet for this role has ePhorte spread
        if not ou_has_ephorte_spread(ou_id=role['adm_enhet']):
            logger.warn("person_id:%s has role %s at non-ePhorte OU %s, skipping role",
                        pe.entity_id, args['role_id'], args['ou_id'])
            #missing_ou_spread.append({'uname':_get_primary_account(p_id),
            #                          'role_type':role_type,
            #                          'sko':sko})
            continue

        cerebrum_roles.add(tuple(sorted(args.items())))
        logger.info('Ensuring role %s@%s for %s, %s',
                    args['role_id'], args['ou_id'], user_id, args)

        try:
            client.ensure_role_for_user(user_id, **args)
        except EphorteWSError, e:
            logger.warn('Could not ensure existence of role %s@%s for %s',
                        args['role_id'], args['ou_id'], user_id)
            logger.exception(e)
            raise

        # Single event handled, we can exit
        if event:
            return True
    if delete_superfluous:
        for role in map(dict, ephorte_roles - cerebrum_roles):
            logger.info('Removing superfluous role %s@%s for %s',
                    role['role_id'], role['ou_id'], user_id)
            client.disable_user_role(user_id, role['role_id'], role['ou_id'])
    # If we are here, we have added all roles or failed to handle a single event
    return False if event else True


def main():
    """User-interface and configuration."""
    # Parse args
    parser = argparse.ArgumentParser(
        description='Update & provision users in ePhorte')
    parser.add_argument(
        '--config', metavar='<config>', type=str, default='sync_ephorte.cfg',
        help='Config file to use (default: sync_ephorte.cfg)')
    cmdgrp = parser.add_mutually_exclusive_group()
    cmdgrp.add_argument(
        '--fullsync-persons', help='Full sync of persons', action='store_true')
    cmdgrp.add_argument(
        '--fullsync-roles-authz', help='Full sync of roles and authz', action='store_true')
    cmdgrp.add_argument(
        '--quicksync-roles-authz', help='Quick sync of roles and authz', action='store_true')
    cmdgrp.add_argument(
        '--config-help', help='Show configuration help', action='store_true')
    parser.add_argument(
        '--commit', help='Run in commit mode', action='store_true')
    args = parser.parse_args()

    if args.config_help:
        print("""Example configuration:

  [DEFAULT]
  wsdl=http://example.com/?wsdl
  customer_id=CustomerID
  database=DatabaseName
  client_key=None
  client_cert=None
  ca_certs=None
  selection_spread=ePhorte_person""")
        sys.exit(0)

    # Select proper client depending on commit-argument
    if args.commit:
        logger.info('Running in commit mode')
    else:
        logger.info('Not running in commit mode. Using mock client')
    from Cerebrum.modules.no.uio.EphorteWS import make_ephorte_client

    client, config = make_ephorte_client(args.config, mock=not args.commit)

    try:
        selection_spread = co.Spread(config.selection_spread)
        int(selection_spread)
        logger.info('Using spread %s as selection criteria', str(selection_spread))
    except Errors.NotFoundError:
        logger.error('Spread %s could not be found, aborting.', args.spread)
        sys.exit(1)

    if args.quicksync_roles_authz:
        logger.info("Quick sync of roles and authz started")
        quicksync_roles_and_authz(client=client,
                                  config=config,
                                  selection_spread=selection_spread,
                                  commit=args.commit)
        logger.info('Quick sync of roles and authz finished')
    elif args.fullsync_roles_authz:
        logger.info("Full sync of roles and authz started")
        fullsync_roles_and_authz(client=client,
                                 selection_spread=selection_spread)
        logger.info('Full sync of roles and authz finished')
    elif args.fullsync_persons:
        logger.info("Full sync of persons started")
        fullsync_persons(client=client,
                         selection_spread=selection_spread)
        logger.info('Full sync of persons finished')


if __name__ == '__main__':
    main()
