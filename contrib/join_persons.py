#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2020 University of Oslo, Norway
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
"""
Script for joining duplicate person objects in a single person object
"""
import sys
import logging
import argparse

from Cerebrum import Errors
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def person_join(old_person, new_person, with_uio_ephorte, with_uio_voip,
                database):
    """Add information from old person to new person without overwriting

    :param old_person: Populated person object for old person
    :param new_person: Populated person object for new person
    :param with_uio_ephorte: Include ephorte information for UiO
    :param with_uio_voip: Include voip information for UiO
    :param database: Cerebrum database connection
    :return:
    """
    const = Factory.get('Constants')(database)
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    logger.debug(('source_systems: %r', source_systems))

    old_id = old_person.entity_id
    new_id = new_person.entity_id

    # birth_date
    new_person.birth_date = new_person.birth_date or old_person.birth_date
    new_person.write_db()
    # person_external_id
    types = {}
    for row in old_person.get_external_id():
        types[int(row['id_type'])] = 1
    for row in new_person.get_external_id():
        types[int(row['id_type'])] = 1
    types = types.keys()
    for source_sys in source_systems:
        logger.debug("person_external_id: %s", source_sys)
        new_person.clear()  # Avoid "Attribute '_extid_source' is read-only."
        new_person.find(new_id)
        new_person.affect_external_id(source_sys, *types)
        old_person.clear()
        old_person.find(old_id)
        old_person.affect_external_id(source_sys, *types)
        try:
            for row in old_person.get_external_id(source_sys):
                new_person.populate_external_id(source_sys, row['id_type'],
                                                row['external_id'])
        except Errors.NotFoundError:
            continue  # Old person didn't have data, no point in continuing
        try:
            for row in new_person.get_external_id(source_sys):
                new_person.populate_external_id(source_sys, row['id_type'],
                                                row['external_id'])
        except Errors.NotFoundError:
            pass
        old_person.write_db()  # Avoids unique external_id constraint violation
        new_person.write_db()

    # person_name
    variants = []
    for code in old_person.list_person_name_codes():
        variants.append(int(code['code']))
    for source_sys in source_systems:
        logger.debug("person_name: %s", source_sys)
        new_person.clear()
        new_person.find(new_id)
        new_person.affect_names(source_sys, *variants)
        for code in variants:
            try:
                new_person.populate_name(code,
                                         old_person.get_name(source_sys, code))
            except Errors.NotFoundError:
                pass
            try:
                new_person.populate_name(code,
                                         new_person.get_name(source_sys, code))
            except Errors.NotFoundError:
                pass
        new_person.write_db()

    # entity_contact_info
    for source_sys in source_systems:
        logger.debug("entity_contact_info: %s", source_sys)
        new_person.clear()
        new_person.find(new_id)
        for row in old_person.get_contact_info(source_sys):
            new_person.populate_contact_info(
                row['source_system'], row['contact_type'],
                row['contact_value'],
                row['contact_pref'], row['description'], row['contact_alias'])
        for row in new_person.get_contact_info(source_sys):
            new_person.populate_contact_info(
                row['source_system'], row['contact_type'],
                row['contact_value'],
                row['contact_pref'], row['description'], row['contact_alias'])
        new_person.write_db()

    # entity_address
    for source_sys in source_systems:
        logger.debug("entity_address: %s", source_sys)
        new_person.clear()
        new_person.find(new_id)
        try:
            for row in old_person.get_entity_address(source_sys):
                new_person.populate_address(
                    row['source_system'], row['address_type'],
                    row['address_text'], row['p_o_box'], row['postal_number'],
                    row['city'], row['country'])
        except Errors.NotFoundError:
            pass
        try:
            for row in new_person.get_entity_address(source_sys):
                new_person.populate_address(
                    row['source_system'], row['address_type'],
                    row['address_text'], row['p_o_box'], row['postal_number'],
                    row['city'], row['country'])
        except Errors.NotFoundError:
            pass
        new_person.write_db()

    # entity_quarantine
    for row in old_person.get_entity_quarantine():
        logger.debug("entity_quarantine: %s", row)
        new_person.add_entity_quarantine(
            row['quarantine_type'], row['creator_id'],
            row['description'], row['start_date'], row['end_date'])

    # entity_spread
    for row in old_person.get_spread():
        logger.debug("entity_spread: %s", row['spread'])
        if not new_person.has_spread(row['spread']):
            new_person.add_spread(row['spread'])

    # person_affiliation
    for source_sys in source_systems:
        logger.debug("person_affiliation: %s", source_sys)
        new_person.clear()
        new_person.find(new_id)
        do_del = []
        for aff in old_person.list_affiliations(old_person.entity_id,
                                                source_sys,
                                                include_deleted=True):
            new_person.populate_affiliation(
                aff['source_system'], aff['ou_id'], aff['affiliation'],
                aff['status'], aff['precedence'])
            if aff['deleted_date']:
                do_del.append((int(aff['ou_id']), int(aff['affiliation']),
                               int(aff['source_system'])))
        for aff in new_person.list_affiliations(new_person.entity_id,
                                                source_sys):
            new_person.populate_affiliation(
                aff['source_system'], aff['ou_id'], aff['affiliation'],
                aff['status'], aff['precedence'])
            try:
                do_del.remove((int(aff['ou_id']), int(aff['affiliation']),
                               int(aff['source_system'])))
            except ValueError:
                pass
        new_person.write_db()
        for aff in do_del:
            new_person.delete_affiliation(*aff)

    # account_type
    account = Factory.get('Account')(database)
    old_account_types = []
    # To avoid FK contraint on account_type, we must first remove all
    # account_types
    for row in account.get_account_types(owner_id=old_person.entity_id,
                                         filter_expired=False):
        account.clear()
        account.find(row['account_id'])
        account.del_account_type(row['ou_id'], row['affiliation'])
        old_account_types.append(row)
        logger.debug("account_type: %s", account.account_name)
    for row in account.list_accounts_by_owner_id(old_person.entity_id,
                                                 filter_expired=False):
        account.clear()
        account.find(row['account_id'])
        account.owner_id = new_person.entity_id
        account.write_db()
        logger.debug("account owner: %s", account.account_name)
    for row in old_account_types:
        account.clear()
        account.find(row['account_id'])
        account.set_account_type(row['ou_id'], row['affiliation'],
                                 row['priority'])

    # group_member
    group = Factory.get('Group')(database)
    for row in group.search(member_id=old_person.entity_id,
                            indirect_members=False):
        group.clear()
        group.find(row['group_id'])
        logger.debug("group_member: %s" % group.group_name)
        if not group.has_member(new_person.entity_id):
            group.add_member(new_person.entity_id)
        group.remove_member(old_person.entity_id)

    if with_uio_ephorte:
        join_ephorte_roles(old_id, new_id, database)

    if with_uio_voip:
        join_uio_voip_objects(old_id, new_id, database)

    # EntityConsentMixin
    join_consents(old_person, new_person)


def join_consents(old_person, new_person):
    """Join consent information to new person

    :param old_person: populated old person object
    :param new_person: populated new person object
    :return:
    """
    if not hasattr(new_person, 'list_consents'):
        return
    old_consents = old_person.list_consents(
        entity_id=old_person.entity_id, filter_expired=False)
    if not old_consents:
        return
    for old_consent in old_consents:
        new_consent = new_person.list_consents(
            entity_id=new_person.entity_id,
            consent_code=old_consent['consent_code'],
            filter_expired=False)

        if new_consent:
            new_consent = new_consent[0]

        replace_expired = (new_consent and new_consent['expiry'] and
                           not old_consent['expiry'])
        old_expires_later = (new_consent and old_consent['expiry'] and
                             new_consent['expiry'] and
                             (old_consent['expiry'] > new_consent['expiry']))
        keep = not new_consent or replace_expired or old_expires_later
        logger.info(
            'consent: old person has consent. '
            'joining with new? %s consent=%s', keep, dict(old_consent))
        if keep:
            new_person.set_consent(
                consent_code=old_consent['consent_code'],
                description=old_consent['description'],
                expiry=old_consent['expiry'])
        old_person.remove_consent(consent_code=old_consent['consent_code'])
    old_person.write_db()
    new_person.write_db()


def join_ephorte_roles(old_id, new_id, database):
    """Add old ephorte roles to new person

    :param old_id: entity_id of old person object
    :param new_id: entity_id of new person object
    :param database: database connection
    :return:
    """
    # All ephorte roles belonging to old_person must be deleted.
    # Any roles that are manual (auto=F) should be given to new person
    from Cerebrum.modules.no.uio.Ephorte import EphorteRole
    ephorte_role = EphorteRole(database)

    for row in ephorte_role.list_roles(person_id=old_id):
        role_str = "ephorte role (%s, %s, %s, %s) from %s" % (
            row['role_type'], row['adm_enhet'], row['arkivdel'],
            row['journalenhet'], old_id)
        if row['auto_role'] == 'F':
            # TODO: we should check if a person has a role before
            # adding, so that we don't need the try: ... except:...
            # but that is a bit swinish the way Ephorte.py is
            # designed at the moment and will be more dirty than this
            # hack. Ephorte.py will be redesigned pretty soon.
            try:
                ephorte_role.add_role(new_id,
                                      int(row['role_type']),
                                      int(row['adm_enhet']),
                                      row['arkivdel'],
                                      row['journalenhet'],
                                      auto_role='F')
                logger.debug("Transferring %s to %s", role_str, new_id)
            except Exception as exc:
                logger.warning("Couldn't transfer %s to %s\n%s",
                               role_str, new_id, exc)
        else:
            logger.debug("Removing %s", role_str)
        # Remove role from old_person
        ephorte_role.remove_role(old_id, int(row['role_type']),
                                 int(row['adm_enhet']),
                                 row['arkivdel'], row['journalenhet'])


def join_uio_voip_objects(old_id, new_id, database):
    """Transfer voip objects from person old_id to person new_id.

    Respect that a person can have at most one voip_address, i.e.
    transfer happens only if old_id owns one address and new_id
    owns none. In case old_id owns no voip_address, nothing is transfered
    and join continues. Otherwise, join rolls back.
    :type old_id: int
    :param old_id: person id
    :type new_id: int
    :param new_id: person id
    :param database: database connection
    """
    from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
    voip_addr = VoipAddress(database)
    voip_addr.clear()
    old_person_voip_addr = voip_addr.search(owner_entity_id=old_id)
    new_person_voip_addr = voip_addr.search(owner_entity_id=new_id)
    if (len(old_person_voip_addr) == 1
            and not new_person_voip_addr):
        # Transfer
        voip_addr.clear()
        try:
            voip_addr.find_by_owner_id(old_id)
        except Errors.NotFoundError:
            logger.info("No voip address found for owner id %s", old_id)
            return
        logger.debug("Change owner of voip_address %s to %s",
                     voip_addr.entity_id,
                     new_id)
        voip_addr.populate(new_id)
        voip_addr.write_db()
    elif not old_person_voip_addr:
        logger.info("Nothing to transfer."
                    " Person %s owns no voip addresses", old_id)
    else:
        logger.warning("Source person %s owns voip addresses: %s",
                       old_id, old_person_voip_addr)
        logger.warning("Target person %s owns voip addresses:%s",
                       new_id, new_person_voip_addr)
        database.rollback()
        logger.warning("Cannot transfer, rollback all changes."
                       "Manual intervention required to join voip objects.")
        sys.exit(1)


def main():
    """Parse arguments and run the appropriate functions

    :return:
    """
    parser = argparse.ArgumentParser(
        description='''Merges all information about a person identified by
        entity_id into the new person, not overwriting existing values in
        new person.  The old_person entity is permanently removed from the
         database.''')

    # Add commit/dryrun arguments
    parser = add_commit_args(parser)

    parser.add_argument(
        '--old',
        help='Old entity_id',
        required=True,
        type=int)
    parser.add_argument(
        '--new',
        help='New entity_id',
        required=True,
        type=int)
    parser.add_argument(
        '--ephorte-uio',
        dest='with_uio_ephorte',
        help='transfer uio-ephorte roles',
        action='store_true')
    parser.add_argument(
        '--voip-uio',
        dest='with_uio_voip',
        help='transfer voip objects',
        action='store_true')

    logutils.options.install_subparser(parser)
    args = parser.parse_args()
    logutils.autoconf('tee', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug('args: %r', args)

    #
    # Initialize globals
    #
    database = Factory.get('Database')()
    database.cl_init(change_program="join_persons")
    clconst = Factory.get('CLConstants')(database)

    old_person = Factory.get('Person')(database)
    old_person.find(args.old)
    new_person = Factory.get('Person')(database)
    new_person.find(args.new)
    database.log_change(
        new_person.entity_id,
        clconst.person_join,
        None,
        change_params={
            "old": old_person.entity_id,
            "new": new_person.entity_id
        },
    )

    person_join(old_person, new_person,
                args.with_uio_ephorte, args.with_uio_voip, database)
    old_person.delete()

    if args.commit:
        database.commit()
        logger.info('Changes were committed to the database')
    else:
        database.rollback()
        logger.info('Dry run. Changes to the database were rolled back')

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
