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

from Cerebrum.modules.no.uio.EphorteWS import EphorteWSError
from Cerebrum.modules.no.uio.Ephorte import EphortePermission

db = Factory.get('Database')(client_encoding='utf-8')

logger = Factory.get_logger("cronjob")
co = Factory.get('Constants')(db)


def get_email_address(pe):
    """Get a persons primary email address.

    :type pe: Person
    :param pe: The person

    :rtype: str:
    :return: The persons primary email address
    """
    ac = Factory.get('Account')(db)
    ac.find(pe.get_primary_account())
    return ac.get_primary_mailaddress()


def get_username(pe):
    """Get the primary accounts username.

    :type pe: Person
    :param pe: The person

    :rtype: str:
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

    :rtype: str:
    :return: The persons ePhorte (FEIDE) id
    """
    ac = Factory.get('Account')(db)
    ac.find(pe.get_primary_account())
    return "%s@%s" % (ac.account_name, cereconf.INSTITUTION_DOMAIN_NAME)


def update_person(pe, client):
    """Collect information about the person, and ensure that it exists in ePhorte.

    :type pe: Person
    :param pe: The person

    :type client: instance
    :param client: The client used to talkt to ePhorte
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

sko_cache = dict()
ou = Factory.get("OU")(db)
def _get_sko(ou_id):
    ret = sko_cache.get(ou_id)
    if ret is None:
        ou.clear()
        ou.find(ou_id)
        ret = "%02i%02i%02i" % (ou.fakultet, ou.institutt, ou.avdeling)
        sko_cache[ou_id] = ret
    return ret


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
        sko = _get_sko(row['adm_enhet'])
        if sko == '999999':
            sko = None
        ret.append((perm_type, False, sko))
    return ret

def update_perms(person, client, userid=None):
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

def select_for_update(selection_spread):
    """Yield persons satisfying criteria.

    :type selection_spread: Spread
    :param selection_spread: The spread to filter by

    :rtype: generator
    :return: A generator that yields Person-objects
    """
    pe = Factory.get('Person')(db)
    for p in pe.list_all_with_spread(selection_spread):
        pers = Factory.get('Person')(db)
        pers.find(p['entity_id'])
        yield pers


class Config(object):
    """Read config trough ConfiParser."""
    # TODO: Make this use yaml?
    # TODO: Is this really a good way to do it?
    def __init__(self, conf, section='DEFAULT'):
        """Init. a configuration.

        :type conf: str
        :param conf: The file name to load (cereconf.CONFIG_PATH prepended if
            file does not exist)
        :type section: str
        :param section: The section of the config file to load
        """
        import ConfigParser
        import os
        if not os.path.exists(conf):
            conf = os.path.join(cereconf.CONFIG_PATH, conf)
        self._config = ConfigParser.ConfigParser()
        self._config.read(conf)
        self._section = section

    def __getattribute__(self, key):
        """Get a config variable.

        :type key: str
        :param key: The field to return
        """
        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            from ConfigParser import NoOptionError
            try:
                c = self._config.get(self._section, key)
                # TODO: This is a bit nasty. Represent this another way?
                if c == 'None':
                    c = None
                return c
            except NoOptionError:
                raise AttributeError("'%s' object has no attribute '%s'" %
                                     (self.__class__.__name__, key))


def main():
    """User-interface and configuration."""
    # Parse args
    parser = argparse.ArgumentParser(
        description='Update & provision users in ePhorte')
    parser.add_argument(
        '--config', metavar='<config>', type=str, default='sync_ephorte.cfg',
        help='Config file to use (default: sync_ephorte.cfg)')
    parser.add_argument(
        '--commit', help='Run in commit mode', action='store_true')
    parser.add_argument(
        '--update-person-info', help='Update person info', action='store_true')
    parser.add_argument(
        '--update-perms', help='Update permissions', action='store_true')
    parser.add_argument(
        '--config-help', help='Show configuration help', action='store_true')
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
        logger.info('Running in commit-mode')
        from Cerebrum.modules.no.uio.EphorteWS \
            import Cerebrum2EphorteClient as EphorteWS
    else:
        logger.info('Not running in commit-mode. Using mock WS-client')
        from Cerebrum.modules.no.uio.EphorteWS \
            import Cerebrum2EphorteClientMock as EphorteWS

    config = Config(args.config)

    try:
        selection_spread = co.Spread(config.selection_spread)
        int(selection_spread)
        logger.info('Using %s as selection-criteria', str(selection_spread))
    except Errors.NotFoundError:
        logger.error('Spread %s could not be found, aborting.', args.spread)
        sys.exit(1)

    client = EphorteWS(config.wsdl, config.customer_id, config.database,
                       client_key=config.client_key,
                       client_cert=config.client_cert,
                       ca_certs=config.ca_certs,
                       username=config.username,
                       password=read_password(config.username, config.wsdl.split('/')[2]))

    for person in select_for_update(selection_spread):
        if args.update_person_info:
            update_person(person, client)
        if args.update_perms:
            update_perms(person, client)


    logger.info('All persons syncronized')

if __name__ == '__main__':
    main()
