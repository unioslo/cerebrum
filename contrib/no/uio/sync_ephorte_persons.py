#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2014-2015 University of Oslo, Norway
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

from __future__ import unicode_literals

# TODO:
# - Handle primary account changes

import sys
import time
import functools
import argparse
from collections import defaultdict

from six import text_type

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors

from Cerebrum.modules.no.uio.Ephorte import EphorteRole
from Cerebrum.modules.no.uio.EphorteWS import EphorteWSError
from Cerebrum.modules.no.uio.Ephorte import EphortePermission
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.utils.context import entity

cerebrum_path, cereconf  # Satisfy the linters.

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
ephorte_role = EphorteRole(db)

# Caches
_person_to_user_id = {}
_ephorte_ous = None
_perm_codes = None
_valid_ephorte_ous = None


def get_email_address(pe):
    """Get a persons primary email address.

    :type pe: Person
    :param pe: The person

    :rtype: text
    :return: The persons primary email address
    """
    ac = Factory.get('Account')(db)
    ac.find(pe.get_primary_account())
    return ac.get_primary_mailaddress()


def get_username(pe):
    """Get the primary accounts username.

    :type pe: Person
    :param pe: The person

    :rtype: text
    :return: The primary accounts user name
    """
    with entity.account.find(pe.get_primary_account()) as ac:
        return ac.account_name


def get_user_id(pe):
    """Get the persons user id in ePhorte.

    ePhorte uses FEIDE-ids to identify users.

    :type pe: Person
    :param pe: The person

    :rtype: str
    :return: The persons ePhorte (FEIDE) id
    """
    user_id = _person_to_user_id.get(pe.entity_id)

    if user_id is None:
        with entity.account.find(pe.get_primary_account()) as ac:
            user_id = ac.account_name
        _person_to_user_id[pe.entity_id] = user_id

    return user_id


@memoize
def get_sko(ou_id):
    """Get the stedkode for an OU.

    :type ou_id: int
    :param ou_id: The OU ID

    :rtype: str
    :return: The six-digit stedkode
    """
    with entity.ou.find(ou_id) as ou:
        return text_type(ou)


def ou_has_ephorte_spread(ou_id):
    """Check for ePhorte spread on an OU.

    :type ou_id: int
    :param ou_id: The OU ID

    :rtype: bool
    :return: Has spread?
    """
    global _ephorte_ous

    if _ephorte_ous is None:
        _ephorte_ous = set([x['entity_id'] for x in
                           ou.list_all_with_spread(
                            spreads=co.spread_ephorte_ou)])

    return ou_id in _ephorte_ous


def ephorte_has_ou(client, sko):
    """Check for OU in ePhorte

    :type sko: str
    :param sko: Stedkode

    :rtype: dict/None
    :return: ephorte ou data if exists else None
    """
    global _valid_ephorte_ous
    if _valid_ephorte_ous is None:
        _valid_ephorte_ous = dict(((x['OrgId'], x) for x in
                                  client.get_all_org_units()))
    return _valid_ephorte_ous.get(sko, False)


def update_person_info(pe, client):
    """Collect information about the person, and ensure that
    it exists in ePhorte.

    :type pe: Person
    :param pe: The person

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte
    """
    first_name = pe.get_name(co.system_cached, co.name_first)
    last_name = pe.get_name(co.system_cached, co.name_last)
    full_name = pe.get_name(co.system_cached, co.name_full)

    try:
        user_id = get_user_id(pe)
        initials = get_username(pe)
    except Errors.NotFoundError:
        logger.warn(
            'Skipping person_id:%d: Does not appear to have a primary account',
            pe.entity_id)
        return

    try:
        email_address = get_email_address(pe)
    except Errors.NotFoundError:
        logger.warn('No email address for %s', user_id)
        email_address = None

    # Webservice accepts max 20 characters for this field
    telephone = pe.get_contact_info(source=co.system_sap,
                                    type=co.contact_phone)
    telephone = telephone[0]['contact_value'][:20] if len(telephone) else None

    # TODO: Has not been exported before. Export nao?
    mobile = None

    tmp_addr = (lambda x: x[0] if len(x) else None)(pe.get_entity_address(
        source=co.system_sap, type=co.address_street))
    if tmp_addr:
        street_address = tmp_addr['address_text']
        # There seems to be a limit in ePhorte ...
        if street_address and len(street_address) > 50:
            street_address = street_address[0:50]
        zip_code = tmp_addr['postal_number']
        city = tmp_addr['city']
    else:
        street_address = zip_code = city = None

    logger.info('Ensuring existence of %s: %s', user_id, text_type((
        first_name, None, initials, last_name, full_name, initials,
        email_address, telephone, mobile, street_address, zip_code, city)))
    try:
        client.ensure_user(user_id, first_name, None, last_name, full_name,
                           initials, email_address, telephone, mobile,
                           street_address, zip_code, city)
        return True
    except EphorteWSError, e:
        # Temporary hack to return prettier error-message if EphorteWS returns
        # an unspecified rule violation for field length.
        # Should be removed once the WS itself returns the specific field
        # that caused the exception.
        if 'Det er ikke tillatt med mer enn' in text_type(e):
            max_length = [num for num in str(e).split() if num.isdigit()][0]
            e = ('Unknown field violating WS-rule of max '
                 '%s characters.' % max_length)
        logger.warn('Could not ensure existence of %s in ePhorte: %s',
                    user_id, text_type(e))
        return False


def perm_code_id_to_perm(code):
    """Convert from ePhorte perm code to Cerebrum code"""
    global _perm_codes

    if _perm_codes:
        return _perm_codes[code]

    logger.debug("Mapping perm codes")
    _perm_codes = dict((text_type(x), x)
                       for x in map(functools.partial(getattr, co), dir(co))
                       if isinstance(x, co.EphortePermission))


def user_details_to_perms(user_details):
    """Convert result from Cerebrum2EphorteClient.get_user_details()

    :type user_details tuple(dict, list(dict), list)
    :param user_details: Return value from get_user_details()

    :rtype list(authcode, ou, boolean)"""
    authzs = user_details[1]
    return [(x['AccessCodeId'], x['OrgId'], x['IsAutorizedForAllOrgUnits'])
            for x in authzs]


def list_perm_for_person(person):
    ret = []
    for row in EphortePermission(db).list_permission(
            person_id=person.entity_id, filter_expired=True):
        perm_type = row['perm_type']
        if perm_type:
            perm_type = str(co.EphortePermission(perm_type))
        sko = get_sko(row['adm_enhet'])
        if sko == '999999':
            sko = None
        ret.append((perm_type, sko, False))
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


def fullsync_account(client, selection_spread, account_name):
    """Sync info, roles and permissions for a single account/person.

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte

    :type selection_spread: Spread
    :param selection_spread: A person must have this spread to be synced

    :type account_name: str
    :param account_name: Account name of person to be synced
    """
    ac = Factory.get('Account')(db)
    try:
        ac.find_by_name(account_name)
    except Errors.NotFoundError:
        logger.error("No such account %s", account_name)
        return

    if sanity_check_person(person_id=ac.owner_id,
                           selection_spread=selection_spread):
        person = Factory.get('Person')(db)
        person.find(ac.owner_id)

        update_person_info(pe=person, client=client)

        try:
            update_person_roles(person, client, remove_superfluous=True)
        except:
            logger.warn(
                'Failed to update roles for person_id:%s',
                person.entity_id, exc_info=True)

        try:
            update_person_perms(person, client, remove_superfluous=True)
        except:
            logger.warn(
                'Failed to update permissions for person_id:%s',
                person.entity_id, exc_info=True)


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


def select_events_by_person(clh, config, change_types, selection_spread):
    """Yield unhandled events, sorted by person_id.

    :type clh: CLHandler
    :param clh: Change log handler instance

    :type config: Config
    :param config: Configuration

    :type change_types: iterable
    :param change_types: Get events of this type

    :type selection_spread: Spread
    :param selection_spread: A person must have this spread to be synced

    :rtype: generator
    :return: A generator that yields (person_id, events)
    """
    too_old = time.time() - int(config.changes_too_old_days) * 60*60*24

    logger.debug("Fetching unhandled events using change key: %s",
                 config.change_key)
    all_events = clh.get_events(config.change_key, change_types)
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
        yield (person_id, events)


def sanity_check_person(person_id, selection_spread):
    """Checks that:
     - the person exists
     - has a primary account
     - has ePhorte spread

    :type person_id: int
    :param person_id: Person ID

    :type selection_spread: Spread
    :param selection_spread: A person must have this spread

    :rtype: bool
    :return: True if everything checks out, else False
    """
    pe = Factory.get('Person')(db)

    try:
        pe.find(person_id)
    except Errors.NotFoundError:
        logger.info('person_id:%s does not exist, skipping', person_id)
        return False

    try:
        get_user_id(pe)
    except Errors.NotFoundError:
        logger.info(
            'person_id:%s does not have a primary account, skipping',
            person_id)
        return False

    if not pe.has_spread(spread=selection_spread):
        logger.info('person_id:%s has no ePhorte spread, skipping', person_id)
        return False

    return True


def fullsync_roles_and_perms(client, selection_spread):
    """Full sync of roles and permissions.

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte

    :type selection_spread: Spread
    :param selection_spread: A person must have this spread to be synced
    """
    for person in select_persons_for_update(selection_spread):
        if sanity_check_person(person_id=person.entity_id,
                               selection_spread=selection_spread):
            try:
                update_person_roles(person, client, remove_superfluous=True)
            except:
                logger.warn(
                    'Failed to update roles for person_id:%s',
                    person.entity_id, exc_info=True)

            try:
                update_person_perms(person, client, remove_superfluous=True)
            except:
                logger.warn(
                    'Failed to update permissions for person_id:%s',
                    person.entity_id, exc_info=True)


def quicksync_roles_and_perms(client, selection_spread, config, commit):
    """Quick sync for roles and permissions.

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

    change_types_roles = (co.ephorte_role_add,
                          co.ephorte_role_rem,
                          co.ephorte_role_upd)
    change_types_perms = (co.ephorte_perm_add, co.ephorte_perm_rem)
    change_types = change_types_roles + change_types_perms

    event_selector = select_events_by_person(
        clh=clh,
        config=config,
        change_types=change_types,
        selection_spread=selection_spread)

    for person_id, events in event_selector:
        if not sanity_check_person(person_id=person_id,
                                   selection_spread=selection_spread):
            continue

        pe.clear()
        pe.find(person_id)

        if not update_person_info(pe, client):
            continue

        try:
            if update_person_roles(pe, client, remove_superfluous=True):
                for event in events:
                    if event['change_type_id'] in change_types_roles:
                        clh.confirm_event(event)
        except:
            logger.warn(
                'Failed to update roles for person_id:%s',
                person_id, exc_info=True)
        else:
            if commit:
                clh.commit_confirmations()

        try:
            if update_person_perms(pe, client, remove_superfluous=True):
                for event in events:
                    if event['change_type_id'] in change_types_perms:
                        clh.confirm_event(event)
        except:
            logger.warn(
                'Failed to update permissions for person_id:%s',
                person_id, exc_info=True)
        else:
            if commit:
                clh.commit_confirmations()

    if commit:
        clh.commit_confirmations()


def update_person_perms(person, client, remove_superfluous=False):
    userid = get_user_id(person)

    logger.info("Updating perms for %s", userid)

    ephorte_perms = set(user_details_to_perms(
        client.get_user_details(userid)))
    for perm in ephorte_perms:
        logger.debug("Found perm for %s in ePhorte: %s@%s, authorized=%s",
                     userid, *perm)

    cerebrum_perms = set(list_perm_for_person(person))
    for perm in cerebrum_perms:
        logger.debug("Should have perm for %s: %s@%s, authorized=%s",
                     userid, *perm)

    # Remove permissions
    if remove_superfluous:
        superfluous = ephorte_perms.difference(cerebrum_perms)
        for perm in superfluous:
            logger.info("Removing perm for %s: %s@%s, authorized=%s",
                        userid, *perm)
            try:
                client.disable_user_authz(userid, perm[0], perm[1])
            except Exception:
                logger.exception(
                    "Failed to remove perm for %s: %s@%s, authorized=%s",
                    userid, *perm)

    # Add new permissions
    for perm in cerebrum_perms:
        if perm not in ephorte_perms:
            logger.info(u"Adding new perm for %s: %s@%s, authorized=%s",
                        userid, *perm)
        else:
            logger.info(u"Ensuring perm for %s: %s@%s, authorized=%s",
                        userid, *perm)

        if perm[1] and not ephorte_has_ou(client, perm[1]):
            logger.warn("No OU in ePhorte for %s for perm %s for %s",
                        perm[1], perm[0], userid)
            continue

        try:
            client.ensure_access_code_authorization(userid, *perm)
        except Exception:
            logger.exception(
                u"Could not ensure perm for %s: %s@%s, authorized=%s",
                userid, *perm)

    return True


def report_person_perms(person, client):
    """Generate report for person"""
    userid = get_user_id(person)

    try:
        ephorte_perms = set(user_details_to_perms(
            client.get_user_details(userid)))
    except EphorteWSError, e:
        if 'UserId not found in Ephorte' in str(e):
            logger.warn("Fetching of user details for %s failed: %s",
                        userid, e)
            return "User %s exists in Cerebrum, but not in ePhorte!" % userid
        else:
            raise

    cerebrum_perms = set(list_perm_for_person(person))

    toadd = cerebrum_perms - ephorte_perms
    torem = ephorte_perms - cerebrum_perms

    def format_perm(code, ou, omni):
        if ou is None:
            if omni:
                return "%s - hele uio" % code
            else:
                return "%s - egne saker" % code
        else:
            return "%s@%s" % (code, ou)

    if toadd or torem:
        ret = ["Endringer for %s" % userid]
        for i in toadd:
            ret.append(" legger til tilgang: %s" % format_perm(*i))
        for i in torem:
            ret.append(" fjerner tilgang: %s" % format_perm(*i))
        return "\n".join(ret)


def report_perms(client, selection_spread, fil):
    """Generate perms report"""
    first = True
    for person in select_persons_for_update(selection_spread):
        if not sanity_check_person(person.entity_id, selection_spread):
            continue
        tmp = report_person_perms(person, client)
        if tmp:
            if first:
                first = False
            else:
                fil.write("\n\n")
            fil.write(tmp)
    fil.close()


def user_details_to_roles(user_details):
    """Convert result from Cerebrum2EphorteClient.get_user_details()
    to arguments suitable for ensure_role_for_user (user_id omitted).
    :type user_details tuple(dict, list(dict), list)
    :param user_details: Return value from get_user_details()

    :rtype list(dict)"""
    roles = user_details[2]
    return [{'arkivdel': x['FondsSeriesId'],
             'journalenhet': x['RegistryManagementUnitId'],
             'role_id': x['Role']['RoleId'],
             'ou_id': x['Org']['OrgId'],
             'default_role': x['IsDefault'],
             'job_title': x['JobTitle']}
            for x in roles]


def update_person_roles(pe, client, remove_superfluous=False):
    """Updates roles for a person.

    :type pe: Person
    :param pe: The person to update roles for

    :type client: EphorteWS
    :param client: The client used to talk to ePhorte

    :rtype: bool
    :return: Roles updated?
    """
    user_id = get_user_id(pe)

    args = {}

    ephorte_roles = set(tuple(sorted(x.items()))
                        for x in user_details_to_roles(
                            client.get_user_details(user_id)))
    cerebrum_roles = set()

    # These functons can be used to remove the default_role component from
    # data-structures.
    def remove_default_flag(l):
        return filter(lambda e: e[0] is not 'default_role', l)

    def remove_default_flag_from_set(l):
        return set(map(remove_default_flag, l))

    for role in ephorte_role.list_roles(person_id=pe.entity_id,
                                        filter_expired=True):
        try:
            args['arkivdel'] = unicode(co.EphorteArkivdel(role['arkivdel']))
            args['journalenhet'] = unicode(co.EphorteJournalenhet(
                role['journalenhet']))
            args['role_id'] = unicode(co.EphorteRole(role['role_type']))
        except (TypeError, Errors.NotFoundError):
            logger.warn(
                "Unknown arkivdel, journalenhet or role type, "
                "skipping role %s", role)
            continue

        args['ou_id'] = unicode(get_sko(ou_id=role['adm_enhet']))
        args['job_title'] = role['rolletittel'] or None
        args['default_role'] = role['standard_role'] == 'T'

        # Check if adm_enhet for this role has ePhorte spread
        if not ou_has_ephorte_spread(ou_id=role['adm_enhet']):
            logger.warn(
                "person_id:%s has role %s at non-ePhorte OU %s, skipping role",
                pe.entity_id, args['role_id'], args['ou_id'])
            continue
        # Check if the OU exists in ePhorte
        elif not ephorte_has_ou(client, args['ou_id']):
            logger.warn("OU %s does not exist in ePhorte for role %s %s",
                        args['ou_id'], user_id, args)
            continue

        role_tuple = tuple(sorted(args.items()))
        cerebrum_roles.add(role_tuple)
        # Remove the standard role flag in order to log correct message.
        if (remove_default_flag(role_tuple) not in
                remove_default_flag_from_set(ephorte_roles)):
            logger.info('Adding role %s@%s for %s, %s',
                        args['role_id'], args['ou_id'], user_id, args)
        else:
            logger.debug('Ensuring role %s@%s for %s, %s',
                         args['role_id'], args['ou_id'], user_id, args)

        try:
            client.ensure_role_for_user(user_id, **args)
        except EphorteWSError, e:
            logger.warn('Could not ensure existence of role %s@%s for %s: %s',
                        args['role_id'], args['ou_id'], user_id, unicode(e))

    if remove_superfluous:
        # Remove the default role flag. We need to do this before computing the
        # set difference, or else we'll remove roles that we should have when
        # changing the standard role.
        for role in map(dict,
                        remove_default_flag_from_set(ephorte_roles) -
                        remove_default_flag_from_set(cerebrum_roles)):
            logger.info('Removing superfluous role %s@%s for %s',
                        role['role_id'], role['ou_id'], user_id)
            try:
                client.disable_user_role(
                    user_id, role['role_id'], role['ou_id'],
                    role['arkivdel'], role['journalenhet'])
            except EphorteWSError, e:
                logger.warn('Could not remove role %s@%s for %s: %s',
                            role['role_id'], role['ou_id'], user_id,
                            unicode(e))

    return True


def disable_users(client, selection_spread):
    logger.info('Fetching all users from ePhorte... go grab some coffee.')
    start = time.time()
    all_users = client.get_all_users()
    logger.info('Fetched all users in %s secs', int(time.time() - start))

    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    def should_be_disabled(user_id):
        """Check if given account should be disabled in ePhorte.

        Looks through the account's data in Cerebrum to conclude.

        :type user_id: str
        :param user_id: ePhorte user id, including domain

        :rtype: bool
        :returns: True if account should be disabled in ePhorte.

        """
        account_name = user_id.lower()

        try:
            ac.clear()
            ac.find_by_name(account_name)
        except Errors.NotFoundError:
            # Haven't found a way to separate out internal system accounts from
            # the output (since ePhorte stopped using realms), so we can for
            # now only ignore these accounts. If we disabled all of these, we
            # would probably break something in ePhorte, according to the
            # sysadmins.
            logger.info('No such account:%s in Cerebrum, ignoring user',
                        account_name)
            # TODO: Check with ePhorte before disabling such accounts!
            return False

        try:
            pe.clear()
            pe.find(ac.owner_id)
        except Errors.NotFoundError:
            logger.info(
                'No such person_id:%s when '
                'looking for owner of account:%s, ignoring user',
                ac.owner_id, account_name)
            # TODO: Check with ePhorte before disabling such accounts!
            return False

        primary_account_id = pe.get_primary_account()

        if not primary_account_id:
            logger.info(
                'Owner of account:%s, person_id:%s, '
                'has no primary account, user should be disabled',
                account_name, ac.owner_id)
            return True

        ac.clear()
        ac.find(primary_account_id)
        primary_account = ac.account_name

        if not pe.has_spread(spread=selection_spread):
            logger.info(
                'Owner of account:%s, person_id:%s, '
                'has no ePhorte spread, user should be disabled',
                account_name, ac.owner_id)
            return True

        if account_name != primary_account:
            logger.info(
                'Owner of account:%s, person_id:%s, has a different primary '
                'account (%s), user should be disabled',
                account_name, ac.owner_id, primary_account)
            return True

        return False

    def is_disabled_in_ephorte(user_id):
        user_details = client.get_user_details(user_id)
        # consider user as disabled if number of roles + permissions is zero
        disabled = (len(user_details[1]) + len(user_details[2])) == 0
        logger.debug('User %s disabled? %s', user_id, disabled)
        return disabled

    start = time.time()
    disabled_previously = 0
    disabled_now = 0
    failed = 0

    for eph_user_id in all_users.keys():
        logger.debug('Considering user_id:%s', eph_user_id)

        if should_be_disabled(eph_user_id):
            try:
                if not is_disabled_in_ephorte(eph_user_id):
                    client.disable_user(eph_user_id)
                    logger.info('Successfully disabled user %s', eph_user_id)
                    client.disable_roles_and_authz_for_user(eph_user_id)
                    logger.info('Successfully disabled roles and authz for %s',
                                eph_user_id)
                    disabled_now += 1
                else:
                    logger.debug('User %s is already disabled', eph_user_id)
                    disabled_previously += 1
            except EphorteWSError, e:
                logger.warn('Failed disabling user %s or its roles/authz: %s',
                            eph_user_id, unicode(e), exc_info=True)
                failed += 1

    logger.info('Checked %s users in %s secs',
                len(all_users), int(time.time() - start))
    logger.info('Users already disabled: %s', disabled_previously)
    logger.info('Users disabled now: %s', disabled_now)
    logger.info('Webservice errors encountered: %s', failed)


def show_org_units(client):
    for org in client.get_all_org_units():
        print dict(org)


def main():
    """User-interface and configuration."""
    # Parse args
    parser = argparse.ArgumentParser(
        description='Update and provision users, ' +
                    'roles and permissions in ePhorte')
    parser.add_argument('--config',
                        metavar='<config>',
                        type=str,
                        default='sync_ephorte.cfg',
                        help='Config file to use (default: sync_ephorte.cfg)')
    cmdgrp = parser.add_mutually_exclusive_group()
    cmdgrp.add_argument('--full-persons',
                        help='Full sync of persons',
                        action='store_true')
    cmdgrp.add_argument('--full-sync-account',
                        type=str,
                        metavar="<account_name>",
                        help='Full sync of a single account/person')
    cmdgrp.add_argument('--full-roles-perms',
                        help='Full sync of roles and permissions',
                        action='store_true')
    cmdgrp.add_argument('--quick-roles-perms',
                        help='Quick sync of roles and permissions',
                        action='store_true')
    cmdgrp.add_argument('--disable-users',
                        help='Disable users',
                        action='store_true')
    cmdgrp.add_argument('--show-org-units',
                        help='Print org units currently in ePhorte',
                        action='store_true')
    cmdgrp.add_argument('--config-help',
                        help='Show configuration help',
                        action='store_true')
    cmdgrp.add_argument('--permission-report',
                        help="Generate permission report",
                        action="store", type=argparse.FileType(mode="w"))
    parser.add_argument('--commit',
                        help='Run in commit mode',
                        action='store_true')
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
  selection_spread=ePhorte_person
  change_key=eph_sync_foo
  changes_too_old_days=30""")
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
        logger.info('Using spread %s as selection criteria',
                    str(selection_spread))
    except Errors.NotFoundError:
        logger.error('Spread %s could not be found, aborting.',
                     config.selection_spread)
        sys.exit(1)

    try:
        config.change_key
    except AttributeError:
        logger.error('Missing change_key in configuration.')
        sys.exit(1)

    if args.quick_roles_perms:
        logger.info("Quick sync of roles and permissions started")
        quicksync_roles_and_perms(client=client,
                                  config=config,
                                  selection_spread=selection_spread,
                                  commit=args.commit)
        logger.info('Quick sync of roles and permissions finished')
    elif args.full_roles_perms:
        logger.info("Full sync of roles and permissions started")
        fullsync_roles_and_perms(client=client,
                                 selection_spread=selection_spread)
        logger.info('Full sync of roles and permissions finished')
    elif args.full_sync_account:
        logger.info("Syncing person info, roles and permissions for %s",
                    args.full_sync_account)
        fullsync_account(client=client,
                         selection_spread=selection_spread,
                         account_name=args.full_sync_account)
        logger.info("Done syncing person info, roles and permissions for %s",
                    args.full_sync_account)
    elif args.disable_users:
        logger.info('Starting to disable users')
        disable_users(client=client,
                      selection_spread=selection_spread)
        logger.info('Finished disabling users')
    elif args.full_persons:
        logger.info("Full sync of persons started")
        fullsync_persons(client=client,
                         selection_spread=selection_spread)
        logger.info('Full sync of persons finished')
    elif args.permission_report:
        logger.info("Permission report generation started")
        report_perms(client, selection_spread, args.permission_report)
        logger.info("Permission report generation finished")
    elif args.show_org_units:
        show_org_units(client)


if __name__ == '__main__':
    main()
