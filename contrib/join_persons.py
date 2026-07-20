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

Testable *join* helpers
    Each functional component should be moved to an appropriate module, and get
    unit tests.

    Maybe the Entity base class and each subclass/mixin should have a
    ``target.join_from(source)`` method, which would update the target entity
    from the source entity?  This is probably the simplest way to organize
    this, but also a bit messy as we need to mutate/update the *source* in some
    cases...

    The mixin approach would also remove the need for ephorte and voip switches
    - this would be automatically done if appropriate mixins are in place.

    Or maybe we should have a `Cerebrum[.modules].merge_utils` module with
    helpers similar to `Cerebrum.modules.import_utils.syncs`?
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging
import textwrap

import six

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum import Errors
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


def _log_changes(change_type, ident, before, after):
    """
    Calculate and log changes from *before*/*after* sets.

    Before/after are compatible sets of tuples, where each tuple contains
    ``(key, value)``, where the key is a tuple of CerebrumCode values or (some
    other primary key value).

    :param set before: a set of value tuples
    :param set after: a set of value tuples

    :returns tuple:
        A tuple with three sets; added, updated, removed

        Each set contains the keys that has been added, updated, or removed
        according to the input sets.
    """
    # Ideally, we shouldn't need this at all - changes *should* be logged as
    # they are written to the database.  Newer or refactored modules does this
    # better - notice how traits or otp codes are shown if present when
    # deleting the source object.
    def _get_changes(before, after):
        before_types = set(t[0] for t in before)
        after_types = set(t[0] for t in after)
        removed = before_types - after_types
        added = after_types - before_types
        updated = set(t[0] for t in (after - before)) - added
        return added, updated, removed

    def _pretty_keys(keyset):
        return ", ".join(sorted("/".join(six.text_type(k) for k in key)
                                for key in keyset))

    added, updated, removed = _get_changes(before, after)
    if added:
        logger.info("%s: id=%s, added: %s", change_type, ident,
                    _pretty_keys(added))
    if updated:
        # Note: This script should *generally* not produce any updates, but we
        # may encounter updates for:
        # - person names (the cached source system)
        # - quarantines (if both persons have a given quarantine, this is
        #                however likely not intended)
        # - affiliations (e.g. last_seen is always touched)
        logger.info("%s: id=%s, updated: %s", change_type, ident,
                    _pretty_keys(updated))
    if removed:
        logger.info("%s: id=%s, removed: %s", change_type, ident,
                    _pretty_keys(removed))
    if not any((added, removed, updated)):
        logger.info("%s: id=%s, no change", change_type, ident)


def copy_person_names(source, target):
    """
    Copy missing names from *source* to *target*.
    """
    logger.debug("person name: copying from person id=%d to person id=%d",
                 source.entity_id, target.entity_id)
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    # old_id = old_person.entity_id
    target_id = int(target.entity_id)

    variants = []
    for code in source.list_person_name_codes():
        variants.append(int(code['code']))

    def _get_current(person):
        for row in person.get_names():
            key = (
                six.text_type(const.AuthoritativeSystem(row['source_system'])),
                six.text_type(const.PersonName(row['name_variant'])),
            )
            value = (row['name'],)
            yield (key, value)

    before = set(_get_current(target))

    for source_sys in source_systems:
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

    _log_changes("person name", target.entity_id,
                 before, set(_get_current(target)))


def move_extid(source, target):
    """
    Move missing external ids from *source* to *target*.
    """
    # Note: This will *clear* all external ids from *source*.  This must be
    # done to avoid a unique constraint preventing two entities having the same
    # id from the same source system.
    logger.debug("external id: moving from id=%d to id=%d",
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

    def _get_current(curr):
        for row in curr.get_external_id():
            key = (
                six.text_type(const.AuthoritativeSystem(row['source_system'])),
                six.text_type(const.EntityExternalId(row['id_type'])),
            )
            value = (row['external_id'],)
            yield (key, value)

    before = set(_get_current(target))

    for source_sys in source_systems:
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

    _log_changes("external id", target.entity_id,
                 before, set(_get_current(target)))


def copy_contact_info(source, target):
    """
    Copy missing contact info from *source* to *target*.
    """
    logger.debug("contact info: copying from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    target_id = int(target.entity_id)

    def _get_current(curr):
        for row in curr.get_contact_info():
            key = (
                six.text_type(const.AuthoritativeSystem(row['source_system'])),
                six.text_type(const.ContactInfo(row['contact_type'])),
            )
            value = (row['contact_value'], row['contact_pref'],
                     row['description'], row['contact_alias'])
            yield (key, value)

    before = set(_get_current(target))

    for source_sys in source_systems:
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

    _log_changes("contact info", target.entity_id,
                 before, set(_get_current(target)))


def copy_addresses(source, target):
    """ Copy missing addresses from *source* to *target*. """
    logger.debug("address: copying from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    target_id = int(target.entity_id)

    def _get_current(curr):
        for row in curr.get_entity_address():
            key = (
                six.text_type(const.AuthoritativeSystem(row['source_system'])),
                six.text_type(const.Address(row['address_type'])),
            )
            value = (row['address_text'], row['p_o_box'],
                     row['postal_number'], row['city'], row['country'])
            yield (key, value)

    before = set(_get_current(target))

    for source_sys in source_systems:
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

    _log_changes("address", target.entity_id,
                 before, set(_get_current(target)))


def copy_quarantines(source, target):
    """ Copy quarantines from *source* to *target*. """
    logger.debug("quarantine: copying from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    const = target.const

    def _get_current(curr):
        for row in curr.get_entity_quarantine():
            key = (six.text_type(const.Quarantine(row['quarantine_type'])),)
            value = (row['creator_id'], row['description'],
                     row['create_date'], row['start_date'],
                     row['end_date'], row['disable_until'])
            yield key, value

    before = set(_get_current(target))

    # Note: This will potentially *replace* a similar quarantine on *target*.
    #
    # We should probably consider start/end dates if both objects has the same
    # quarantine!
    for row in source.get_entity_quarantine():
        target.add_entity_quarantine(
            row['quarantine_type'], row['creator_id'],
            row['description'], row['start_date'], row['end_date'])

    _log_changes("quarantine", target.entity_id, before,
                 set(_get_current(target)))


def copy_spreads(source, target):
    """ Copy quarantines from *source* to *target*. """
    logger.debug("spread: copying from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    const = target.const

    for row in source.get_spread():
        spread = const.Spread(row['spread'])
        if not target.has_spread(spread):
            logger.info("spread: id=%s, adding: %s",
                        target.entity_id, spread)
            target.add_spread(spread)


def copy_affiliations(source, target):
    """ Copy person affiliations from *source* to *target*. """
    # Note that we also copy *deleted* affiliations
    logger.debug("affiliation: copying from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    db = target._db
    const = target.const
    source_systems = const.fetch_constants(const.AuthoritativeSystem)

    target_id = int(target.entity_id)

    def _get_current(person):
        for row in person.list_affiliations(person_id=int(person.entity_id),
                                            include_deleted=True):
            key = (
                six.text_type(const.AuthoritativeSystem(row['source_system'])),
                six.text_type(const.PersonAffiliation(row['affiliation'])),
                six.text_type(row['ou_id']),
            )
            value = (row['status'], row['precedence'], row['create_date'],
                     row['deleted_date'], row['last_date'])
            yield (key, value)

    before = set(_get_current(target))

    for source_sys in source_systems:
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

    _log_changes("affiliation", target.entity_id, before,
                 set(_get_current(target)))


def move_user_accounts(source, target):
    """ Move personal user accounts from *source* to *target*. """
    logger.debug("user account: moving from id=%d to id=%d",
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
        logger.info("user account: moving account %s (%d) to id=%d",
                    ac.account_name, ac.entity_id, target.entity_id)
    for row in old_account_types:
        ac = _get_account_by_id(db, row['account_id'])
        ac.set_account_type(row['ou_id'], row['affiliation'], row['priority'])


def move_memberships(source, target):
    """ Move group memberships from *source* to *target*. """
    logger.debug("group: copying memberships from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    assert source._db is target._db
    db = target._db
    group = Factory.get('Group')(db)
    for row in group.search(member_id=int(source.entity_id),
                            filter_expired=False,
                            indirect_members=False):
        group = _get_group_by_id(db, row['group_id'])
        logger.info("group: removing id=%d from %s (%d)",
                    source.entity_id, group.group_name, group.entity_id)
        group.remove_member(source.entity_id)
        if not group.has_member(target.entity_id):
            logger.info("group: adding id=%d to %s (%d)",
                        target.entity_id, group.group_name, group.entity_id)
            group.add_member(target.entity_id)


def move_notes(source, target):
    """
    Move notes from *source* to *target*.

    All notes associated with the source entity will be copied to the target
    entity. The notes on the source will be automatically deleted when the
    source entity is deleted (via EntityNoteCleanupMixin).
    """
    logger.debug("note: copying note from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    assert source._db is target._db

    if not hasattr(source, "get_notes") or not hasattr(target, "add_note"):
        logger.debug("note: entity does not have note mixin, skipping")
        return

    moved_count = 0
    for note in source.get_notes():
        target.add_note(
            operator=note['creator_id'],
            subject=note['subject'],
            description=note['description']
        )
        moved_count += 1
        logger.info("note: moved note %d (subject: %s) from id=%d to id=%d",
                    note['note_id'], note['subject'],
                    source.entity_id, target.entity_id)

    if moved_count == 0:
        logger.debug("note: no notes to move from id=%d", source.entity_id)
    else:
        logger.info("note: moved %d note(s) from id=%d to id=%d",
                    moved_count, source.entity_id, target.entity_id)


def person_join(source, target, with_uio_ephorte, with_uio_voip):
    """
    Move missing information from old person to new person.

    :param source: person object to fetch from and delete
    :param target: person object to update and keep
    :param with_uio_ephorte: merge manual ephorte/elements roles
    :param with_uio_voip: merge voip addresses
    """
    new_dob = target.birth_date or source.birth_date
    if target.birth_date != new_dob:
        logger.info("basic: updating date of birth for id=%d",
                    target.entity_id)
        target.birth_date = new_dob
        target.write_db()

    move_extid(source, target)
    copy_person_names(source, target)
    copy_contact_info(source, target)
    copy_addresses(source, target)
    copy_quarantines(source, target)
    copy_spreads(source, target)
    copy_affiliations(source, target)
    move_user_accounts(source, target)
    move_memberships(source, target)

    if with_uio_ephorte:
        join_ephorte_roles(source, target)
        join_elements_roles(source, target)

    if with_uio_voip:
        join_uio_voip_objects(source, target)

    move_consents(source, target)
    move_notes(source, target)
    # TODO: We should probably consider traits?
    # TODO: We should probably consider special consent/reservation logic not
    # represented through the consent module?
    # TODO: We should probably consider personal otp secrets?


def move_consents(source, target):
    """ Move consent data from *source* to *target*. """
    logger.debug("consent: moving from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    assert source._db is target._db
    if not hasattr(target, "list_consents"):
        return
    const = target.const

    def _get_current(curr):
        for row in curr.list_consents(entity_id=int(curr.entity_id)):
            key = (
                const.EntityConsent(row['consent_code']),
            )
            value = (row['set_at'], row['description'])
            yield key, value

    to_move = set(_get_current(source))
    before = set(_get_current(target))
    if to_move:
        target_types = set(t[0] for t in before)

        for key, value in to_move:
            consent_type = key[0]
            description = value[1]

            # TODO: This shouldn't be neccessary - the mixin should remove
            # consents on source.delete()!
            source.remove_consent(consent_code=consent_type)
            if key not in target_types:
                target.set_consent(
                    consent_code=consent_type,
                    description=description,
                )
        source.write_db()
        target.write_db()

    _log_changes("consent", target.entity_id, before,
                 set(_get_current(target)))


def _join_ephorte_roles(source, target, role_db, role_sys_hint="ephorte"):
    """
    Move manual roles from *source* to *target*
    """
    # All ephorte roles belonging to source must be deleted.
    # Any roles that are manual (auto=F) should be given to target
    source_id = int(source.entity_id)
    target_id = int(target.entity_id)

    for row in role_db.list_roles(person_id=source_id):
        role_str = "role ({}, {}, {}, {})".format(
            row['role_type'], row['adm_enhet'], row['arkivdel'],
            row['journalenhet'],
        )
        if row['auto_role'] == 'F':
            # TODO: we should check if a person has a role before
            # adding, so that we don't need the try: ... except:...
            # but that is a bit swinish the way Ephorte.py is
            # designed at the moment and will be more dirty than this
            # hack. Ephorte.py will be redesigned pretty soon.
            try:
                role_db.add_role(
                    target_id,
                    int(row['role_type']),
                    int(row['adm_enhet']),
                    row['arkivdel'],
                    row['journalenhet'],
                    auto_role='F',
                )
                logger.info("%s: added %s to %d",
                            role_sys_hint, role_str, target_id)
            except Exception as exc:
                logger.warning("%s: couldn't transfer %s to %s - %s",
                               role_sys_hint, role_str, target_id, exc)

        role_db.remove_role(source_id, int(row['role_type']),
                            int(row['adm_enhet']),
                            row['arkivdel'], row['journalenhet'])
        logger.info("%s: removed %s from %d",
                    role_sys_hint, role_str, source_id)


def join_ephorte_roles(source, target):
    from Cerebrum.modules.no.uio.Ephorte import EphorteRole
    assert source._db is target._db
    logger.debug("ephorte: moving from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    _join_ephorte_roles(source, target, EphorteRole(target._db),
                        role_sys_hint="ephorte")


def join_elements_roles(source, target):
    from Cerebrum.modules.no.uio.Elements import ElementsRole
    assert source._db is target._db
    logger.debug("elements: moving from id=%d to id=%d",
                 source.entity_id, target.entity_id)
    _join_ephorte_roles(source, target, ElementsRole(target._db),
                        role_sys_hint="elements")


def join_uio_voip_objects(source, target):
    """
    Transfer voip objects from *source* to *target*.

    We need to maintain that a person can have *at most* one voip_address.

    This means a transfer only happens if *source* owns one address, and
    *target* owns none.  If both objects own addresses, or the *source* somehow
    owns multiple addresses, we need to abort and clean up manually!
    """
    from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
    assert source._db is target._db
    source_id = int(source.entity_id)
    target_id = int(target.entity_id)

    voip_addr = VoipAddress(target._db)
    voip_addr.clear()
    old_person_voip_addr = voip_addr.search(owner_entity_id=source_id)
    new_person_voip_addr = voip_addr.search(owner_entity_id=target_id)
    if (len(old_person_voip_addr) == 1 and not new_person_voip_addr):
        # Transfer
        voip_addr.clear()
        try:
            voip_addr.find_by_owner_id(source_id)
        except Errors.NotFoundError:
            logger.info("No voip address found for owner id %s", source_id)
            return
        logger.debug("Change owner of voip_address %s to %s",
                     voip_addr.entity_id, target_id)
        voip_addr.populate(target_id)
        voip_addr.write_db()
    elif not old_person_voip_addr:
        logger.debug("voip: person id=%d owns no voip addresses", source_id)
    else:
        logger.warning("Source person %s owns voip addresses: %s",
                       source_id, old_person_voip_addr)
        logger.warning("Target person %s owns voip addresses:%s",
                       target_id, new_person_voip_addr)
        raise RuntimeError(
            "Both persons own voip addresses: "
            "Manual intervention required to join voip objects.")

def main(argv=None):
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
            Merge two person objects into one.

            Merges all information from an *old* person object into the *new*
            person object.  The script will not replace any info in the *new*
            person object, and the *old* person object is deleted.
            """
        ).lstrip(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--old",
        dest="source_id",
        type=int,
        required=True,
        help="Merge from, and delete person object %(metavar)s",
        metavar="ID",
    )
    parser.add_argument(
        "--new",
        dest="target_id",
        type=int,
        required=True,
        help="Merge to, and keep person object %(metavar)s",
        metavar="ID",
    )
    parser.add_argument(
        "--ephorte-uio",
        dest="with_uio_ephorte",
        help="Transfer ephorte/elements roles",
        action="store_true",
    )
    parser.add_argument(
        "--voip-uio",
        dest="with_uio_voip",
        help="Transfer VoIP addresses",
        action="store_true",
    )
    parser = add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)
    Cerebrum.logutils.autoconf_interactive(args)  # console or tee
    logger.info("start %s", parser.prog)
    logger.debug('args: %r', args)

    database = Factory.get('Database')()
    database.cl_init(change_program="join_persons")
    clconst = Factory.get('CLConstants')(database)

    source = _get_person_by_id(database, args.source_id)
    target = _get_person_by_id(database, args.target_id)

    database.log_change(
        target.entity_id,
        clconst.person_join,
        None,
        change_params={
            "old": source.entity_id,
            "new": target.entity_id
        },
    )

    logger.info("Joining person id=%d into person id=%d",
                source.entity_id, target.entity_id)
    person_join(source, target, args.with_uio_ephorte, args.with_uio_voip)

    logger.info("Deleting person id=%d", source.entity_id)
    source.delete()

    if args.commit:
        database.commit()
        logger.info("commit")
    else:
        database.rollback()
        logger.info("rollback (dryrun)")
    logger.info("done %s", parser.prog)


if __name__ == '__main__':
    main()
