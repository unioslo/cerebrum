#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2026 University of Oslo, Norway
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

TODO
====
Simpler updates
    Remove the current *affect* + *populate* pattern.

    We shouldn't have to list and process *all* possible source systems + type
    codes.  The general update should simply be:

    1. Fetch all entries from *source*
    2. For each entry, add to *target* unless already present


*join* entity methods
    Each functional component should be moved to the appropriate class.

    Maybe the Entity base class and each subclass/mixin should have a
    `target.join_from(source)` method, which would update the target entity
    from the source entity, and clear the data from source?

"""
import sys
import logging
import argparse

from Cerebrum import Errors
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def _get_person_by_id(db, person_id):
    pe = Factory.get("Person")(db)
    pe.find(int(person_id))
    return pe


def _get_account_by_id(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(int(account_id))
    return ac


def _get_group_by_id(db, group_id):
    gr = Factory.get("Group")(db)
    gr.find(int(group_id))
    return gr


def copy_person_names(source, target):
    """
    Copy missing names from *source* to *target*.
    """
    logger.info("Copying names from person id=%d to person id=%d",
                source.entity_id, target.entity_id)
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    # old_id = old_person.entity_id
    target_id = int(target.entity_id)

    variants = []
    for code in source.list_person_name_codes():
        variants.append(int(code['code']))

    for source_sys in source_systems:
        logger.debug("person_name: %s", source_sys)
        # We re-find a fresh person object so we can re-populate for each
        # source system
        person = _get_person_by_id(db, target_id)
        person.affect_names(source_sys, *variants)
        for code in variants:
            try:
                person.populate_name(code,
                                     source.get_name(source_sys, code))
            except Errors.NotFoundError:
                pass
            try:
                person.populate_name(code,
                                     target.get_name(source_sys, code))
            except Errors.NotFoundError:
                pass
        person.write_db()


def move_extid(source, target):
    """
    Move missing external ids from *source* to *target*.
    """
    # Note: This will *clear* all external ids from *source*.  This must be
    # done to avoid a unique constraint preventing two entities having the same
    # id from the same source system.
    logger.info("Moving external ids from id=%d to id=%d",
                source.entity_id, target.entity_id)
    assert source._db is target._db
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    source_id = int(source.entity_id)
    target_id = int(target.entity_id)

    types = set()
    for row in source.get_external_id():
        types.add(int(row['id_type']))
    for row in target.get_external_id():
        types.add(int(row['id_type']))
    if not types:
        # Nothing to move
        return

    for source_sys in source_systems:
        logger.debug("person_external_id: %s", source_sys)

        # We need to re-find objects for each source system, as we can only run
        # *affect_external_id* once per person

        to_update = _get_person_by_id(db, target_id)
        to_update.affect_external_id(source_sys, *types)
        try:
            for row in source.get_external_id(source_sys):
                to_update.populate_external_id(source_sys,
                                               row['id_type'],
                                               row['external_id'])
        except Errors.NotFoundError:
            pass

        try:
            for row in to_update.get_external_id(source_sys):
                to_update.populate_external_id(source_sys,
                                               row['id_type'],
                                               row['external_id'])
        except Errors.NotFoundError:
            pass

        # We need to explicitly remove old data from our source object, to
        # avoid hitting certain duplicate id constraints
        to_clear = _get_person_by_id(db, source_id)
        to_clear.affect_external_id(source_sys, *types)
        to_clear.write_db()

        to_update.write_db()


def copy_contact_info(source, target):
    """
    Copy missing contact info from *source* to *target*.
    """
    logger.info("Copying contacts from id=%d to id=%d",
                source.entity_id, target.entity_id)
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    target_id = int(target.entity_id)

    for source_sys in source_systems:
        logger.debug("entity_contact_info: %s", source_sys)

        to_update = _get_person_by_id(db, target_id)
        for row in source.get_contact_info(source_sys):
            to_update.populate_contact_info(
                row['source_system'], row['contact_type'],
                row['contact_value'],
                row['contact_pref'], row['description'], row['contact_alias'])
        for row in target.get_contact_info(source_sys):
            to_update.populate_contact_info(
                row['source_system'], row['contact_type'],
                row['contact_value'],
                row['contact_pref'], row['description'], row['contact_alias'])
        to_update.write_db()


def copy_addresses(source, target):
    """ Copy missing addresses from *source* to *target*. """
    logger.info("Copying addresses from id=%d to id=%d",
                source.entity_id, target.entity_id)
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    target_id = int(target.entity_id)

    for source_sys in source_systems:
        logger.debug("entity_address: %s", source_sys)

        to_update = _get_person_by_id(db, target_id)
        try:
            for row in source.get_entity_address(source_sys):
                to_update.populate_address(
                    row['source_system'], row['address_type'],
                    row['address_text'], row['p_o_box'], row['postal_number'],
                    row['city'], row['country'])
        except Errors.NotFoundError:
            pass
        try:
            for row in target.get_entity_address(source_sys):
                to_update.populate_address(
                    row['source_system'], row['address_type'],
                    row['address_text'], row['p_o_box'], row['postal_number'],
                    row['city'], row['country'])
        except Errors.NotFoundError:
            pass
        to_update.write_db()


def copy_quarantines(source, target):
    """ Copy quarantines from *source* to *target*. """
    logger.info("Copying quarantines from id=%d to id=%d",
                source.entity_id, target.entity_id)
    # Note: This will potentially *replace* a similar quarantine on *target*.
    #
    # We should probably consider start/end dates if both objects has the same
    # quarantine!
    for row in source.get_entity_quarantine():
        logger.info("adding quarantine to id=%d: %s", target.entity_id, row)
        target.add_entity_quarantine(
            row['quarantine_type'], row['creator_id'],
            row['description'], row['start_date'], row['end_date'])


def copy_spreads(source, target):
    """ Copy quarantines from *source* to *target*. """
    logger.info("Copying spreads from id=%d to id=%d",
                source.entity_id, target.entity_id)
    for row in source.get_spread():
        if not target.has_spread(row['spread']):
            logger.info("adding spread to id=%d: %s",
                        target.entity_id, row['spread'])
            target.add_spread(row['spread'])


def copy_affiliations(source, target):
    """ Copy person affiliations from *source* to *target*. """
    logger.info("Copying affiliations from id=%d to id=%d",
                source.entity_id, target.entity_id)
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    target_id = int(target.entity_id)

    for source_sys in source_systems:
        logger.debug("person_affiliation: %s", source_sys)
        to_update = _get_person_by_id(db, target_id)
        do_del = []
        for aff in source.list_affiliations(person_id=int(source.entity_id),
                                            source_system=int(source_sys),
                                            include_deleted=True):
            to_update.populate_affiliation(
                aff['source_system'], aff['ou_id'], aff['affiliation'],
                aff['status'], aff['precedence'])
            if aff['deleted_date']:
                do_del.append((int(aff['ou_id']), int(aff['affiliation']),
                               int(aff['source_system'])))
        for aff in target.list_affiliations(person_id=int(target.entity_id),
                                            source_system=int(source_sys)):
            to_update.populate_affiliation(
                aff['source_system'], aff['ou_id'], aff['affiliation'],
                aff['status'], aff['precedence'])
            try:
                do_del.remove((int(aff['ou_id']), int(aff['affiliation']),
                               int(aff['source_system'])))
            except ValueError:
                pass
        to_update.write_db()
        for aff in do_del:
            to_update.delete_affiliation(*aff)


def move_user_accounts(source, target):
    """ Move personal user accounts from *source* to *target*. """
    logger.info("Moving user accounts from id=%d to id=%d",
                source.entity_id, target.entity_id)
    assert source._db is target._db
    db = target._db
    account = Factory.get('Account')(db)

    old_account_types = []
    # To avoid FK contraint on account_type, we must first remove all
    # account_types
    for row in account.get_account_types(owner_id=int(source.entity_id),
                                         filter_expired=False):
        ac = _get_account_by_id(db, row['account_id'])
        ac.del_account_type(row['ou_id'], row['affiliation'])
        old_account_types.append(dict(row))

    for row in account.list_accounts_by_owner_id(int(source.entity_id),
                                                 filter_expired=False):
        ac = _get_account_by_id(db, row['account_id'])
        ac.owner_id = target.entity_id
        ac.write_db()
        logger.info("Moving account %s (%d) from owner id=%d to id=%d",
                    ac.account_name, ac.entity_id, source.entity_id,
                    target.entity_id)
    for row in old_account_types:
        ac = _get_account_by_id(db, row['account_id'])
        ac.set_account_type(row['ou_id'], row['affiliation'], row['priority'])


def move_memberships(source, target):
    """ Move group memberships from *source* to *target*. """
    logger.info("Copying memberships from id=%d to id=%d",
                source.entity_id, target.entity_id)
    assert source._db is target._db
    db = target._db
    group = Factory.get('Group')(db)
    for row in group.search(member_id=int(source.entity_id),
                            filter_expired=False,
                            indirect_members=False):
        group = _get_group_by_id(db, row['group_id'])
        logger.info("removing id=%d to group %s (%d)",
                    source.entity_id, group.group_name, group.entity_id)
        group.remove_member(source.entity_id)
        if not group.has_member(target.entity_id):
            logger.info("adding id=%d to group %s (%d)",
                        target.entity_id, group.group_name, group.entity_id)
            group.add_member(target.entity_id)


def person_join(old_person, new_person, with_uio_ephorte, with_uio_voip,
                database):
    """
    Move missing information from old person to new person.

    :param old_person: Populated person object for old person
    :param new_person: Populated person object for new person
    :param with_uio_ephorte: Include ephorte information for UiO
    :param with_uio_voip: Include voip information for UiO
    :param database: Cerebrum database connection
    :return:
    """
    new_dob = new_person.birth_date or old_person.birth_date
    if new_person.birth_date != new_dob:
        logger.info("Updating date of birth for id=%d", new_person.entity_id)
        new_person.birth_date = new_dob
        new_person.write_db()

    move_extid(old_person, new_person)
    copy_person_names(old_person, new_person)
    copy_contact_info(old_person, new_person)
    copy_addresses(old_person, new_person)
    copy_quarantines(old_person, new_person)
    copy_spreads(old_person, new_person)
    copy_affiliations(old_person, new_person)
    move_user_accounts(old_person, new_person)
    move_memberships(old_person, new_person)

    old_id = old_person.entity_id
    new_id = new_person.entity_id

    if with_uio_ephorte:
        join_ephorte_roles(old_id, new_id, database)
        join_elements_roles(old_id, new_id, database)

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
    old_consents = old_person.list_consents(entity_id=old_person.entity_id)
    if not old_consents:
        return
    for old_consent in old_consents:
        new_consent = new_person.list_consents(
            entity_id=new_person.entity_id,
            consent_code=old_consent['consent_code'])

        if new_consent:
            new_consent = new_consent[0]
        keep = not new_consent
        logger.info(
            'consent: old person has consent. '
            'joining with new? %s consent=%s', keep, dict(old_consent))
        if keep:
            new_person.set_consent(
                consent_code=old_consent['consent_code'],
                description=old_consent['description'])
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


def join_elements_roles(old_id, new_id, database):
    """Add old ePhorte Elements roles to new person

    :param old_id: entity_id of old person object
    :param new_id: entity_id of new person object
    :param database: database connection
    :return:
    """
    # All ephorte roles belonging to old_person must be deleted.
    # Any roles that are manual (auto=F) should be given to new person
    from Cerebrum.modules.no.uio.Elements import ElementsRole
    ephorte_role = ElementsRole(database)

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
