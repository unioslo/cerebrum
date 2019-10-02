#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2019 University of Oslo, Norway
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

import sys
import logging
import argparse

from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args

logger = logging.getLogger(__name__)


def get_constants_by_type(co, class_type):
    ret = []
    for c in dir(co):
        c = getattr(co, c)
        if isinstance(c, class_type):
            ret.append(c)
    return ret


def person_join(old_person, new_person, with_uio_ephorte, with_uio_voip, db):
    co = Factory.get('Constants')(db)
    source_systems = get_constants_by_type(co,
                                           Constants._AuthoritativeSystemCode)
    logger.debug(('source_systems: %r', source_systems))

    old_id = old_person.entity_id
    new_id = new_person.entity_id

    # birth_date
    new_person.birth_date = new_person.birth_date or old_person.birth_date
    new_person.write_db()
    # person_external_id
    types = {}
    for r in old_person.get_external_id():
        types[int(r['id_type'])] = 1
    for r in new_person.get_external_id():
        types[int(r['id_type'])] = 1
    types = types.keys()
    for ss in source_systems:
        logger.debug("person_external_id: %s" % ss)
        new_person.clear()   # Avoid "Attribute '_extid_source' is read-only."
        new_person.find(new_id)
        new_person.affect_external_id(ss, *types)
        old_person.clear()
        old_person.find(old_id)
        old_person.affect_external_id(ss, *types)
        try:
            for id in old_person.get_external_id(ss):
                new_person.populate_external_id(ss, id['id_type'],
                                                id['external_id'])
        except Errors.NotFoundError:
            continue  # Old person didn't have data, no point in continuing
        try:
            for id in new_person.get_external_id(ss):
                new_person.populate_external_id(ss, id['id_type'],
                                                id['external_id'])
        except Errors.NotFoundError:
            pass
        old_person.write_db()  # Avoids unique external_id constraint violation
        new_person.write_db()

    # person_name
    variants = []
    for c in old_person.list_person_name_codes():
        variants.append(int(c['code']))
    for ss in source_systems:
        logger.debug("person_name: %s" % ss)
        new_person.clear()
        new_person.find(new_id)
        new_person.affect_names(ss, *variants)
        for c in variants:
            try:
                new_person.populate_name(c, old_person.get_name(ss, c))
            except Errors.NotFoundError:
                pass
            try:
                new_person.populate_name(c, new_person.get_name(ss, c))
            except Errors.NotFoundError:
                pass
        new_person.write_db()

    # entity_contact_info
    for ss in source_systems:
        logger.debug("entity_contact_info: %s" % ss)
        new_person.clear()
        new_person.find(new_id)
        for ci in old_person.get_contact_info(ss):
            new_person.populate_contact_info(
                ci['source_system'], ci['contact_type'], ci['contact_value'],
                ci['contact_pref'], ci['description'], ci['contact_alias'])
        for ci in new_person.get_contact_info(ss):
            new_person.populate_contact_info(
                ci['source_system'], ci['contact_type'], ci['contact_value'],
                ci['contact_pref'], ci['description'], ci['contact_alias'])
        new_person.write_db()

    # entity_address
    for ss in source_systems:
        logger.debug("entity_address: %s" % ss)
        new_person.clear()
        new_person.find(new_id)
        try:
            for ea in old_person.get_entity_address(ss):
                new_person.populate_address(
                    ea['source_system'], ea['address_type'],
                    ea['address_text'], ea['p_o_box'], ea['postal_number'],
                    ea['city'], ea['country'])
        except Errors.NotFoundError:
            pass
        try:
            for ea in new_person.get_entity_address(ss):
                new_person.populate_address(
                    ea['source_system'], ea['address_type'],
                    ea['address_text'], ea['p_o_box'], ea['postal_number'],
                    ea['city'], ea['country'])
        except Errors.NotFoundError:
            pass
        new_person.write_db()

    # entity_quarantine
    for q in old_person.get_entity_quarantine():
        logger.debug("entity_quarantine: %s" % q)
        new_person.add_entity_quarantine(
            q['quarantine_type'], q['creator_id'],
            q['description'], q['start_date'], q['end_date'])

    # entity_spread
    for s in old_person.get_spread():
        logger.debug("entity_spread: %s" % s['spread'])
        if not new_person.has_spread(s['spread']):
            new_person.add_spread(s['spread'])

    # person_affiliation
    for ss in source_systems:
        logger.debug("person_affiliation: %s" % ss)
        new_person.clear()
        new_person.find(new_id)
        do_del = []
        for aff in old_person.list_affiliations(old_person.entity_id, ss,
                                                include_deleted=True):
            new_person.populate_affiliation(
                aff['source_system'], aff['ou_id'], aff['affiliation'],
                aff['status'], aff['precedence'])
            if aff['deleted_date']:
                do_del.append((int(aff['ou_id']), int(aff['affiliation']),
                               int(aff['source_system'])))
        for aff in new_person.list_affiliations(new_person.entity_id, ss):
            new_person.populate_affiliation(
                aff['source_system'], aff['ou_id'], aff['affiliation'],
                aff['status'], aff['precedence'])
            try:
                do_del.remove((int(aff['ou_id']), int(aff['affiliation']),
                               int(aff['source_system'])))
            except ValueError:
                pass
        new_person.write_db()
        for d in do_del:
            new_person.delete_affiliation(*d)

    # account_type
    account = Factory.get('Account')(db)
    old_account_types = []
    # To avoid FK contraint on account_type, we must first remove all
    # account_types
    for a in account.get_account_types(owner_id=old_person.entity_id,
                                       filter_expired=False):
        account.clear()
        account.find(a['account_id'])
        account.del_account_type(a['ou_id'], a['affiliation'])
        old_account_types.append(a)
        logger.debug("account_type: %s" % account.account_name)
    for r in account.list_accounts_by_owner_id(old_person.entity_id,
                                               filter_expired=False):
        account.clear()
        account.find(r['account_id'])
        account.owner_id = new_person.entity_id
        account.write_db()
        logger.debug("account owner: %s" % account.account_name)
    for a in old_account_types:
        account.clear()
        account.find(a['account_id'])
        account.set_account_type(a['ou_id'], a['affiliation'], a['priority'])

    # group_member
    group = Factory.get('Group')(db)
    for g in group.search(member_id=old_person.entity_id,
                          indirect_members=False):
        group.clear()
        group.find(g['group_id'])
        # Skip virtual groups
        if hasattr(group, 'virtual_group_type'):
            if group.virtual_group_type != co.vg_normal_group:
                logger.debug(
                    "group_member: {} (virtual group, skipping)".format(
                        group.group_name))
                continue
        logger.debug("group_member: %s" % group.group_name)
        if not group.has_member(new_person.entity_id):
            group.add_member(new_person.entity_id)
        group.remove_member(old_person.entity_id)

    if with_uio_ephorte:
        join_ephorte_roles(old_id, new_id, db)

    if with_uio_voip:
        join_uio_voip_objects(old_id, new_id, db)

    # EntityConsentMixin
    join_consents(old_person, new_person)


def join_consents(old_person, new_person):
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
            'joining with new? {} consent={}'.format(keep, dict(old_consent)))
        if keep:
            new_person.set_consent(
                consent_code=old_consent['consent_code'],
                description=old_consent['description'],
                expiry=old_consent['expiry'])
        old_person.remove_consent(consent_code=old_consent['consent_code'])
    old_person.write_db()
    new_person.write_db()


def join_ephorte_roles(old_id, new_id, db):
    # All ephorte roles belonging to old_person must be deleted.
    # Any roles that are manual (auto=F) should be given to new person
    from Cerebrum.modules.no.uio.Ephorte import EphorteRole
    ephorte_role = EphorteRole(db)

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
                logger.debug("Transferring %s to %s" % (role_str, new_id))
            except Exception, e:
                logger.warn("Couldn't transfer %s to %s\n%s" %
                            (role_str, new_id, e))
        else:
            logger.debug("Removing %s" % role_str)
        # Remove role from old_person
        ephorte_role.remove_role(old_id, int(row['role_type']),
                                 int(row['adm_enhet']),
                                 row['arkivdel'], row['journalenhet'])


def join_uio_voip_objects(old_id, new_id, db):
    """Transfer voip objects from person old_id to person new_id.

    Respect that a person can have at most one voip_address, i.e.
    transfer happens only if old_id owns one address and new_id
    owns none. In case old_id owns no voip_address, nothing is transfered
    and join continues. Otherwise, join rolls back.
    @type int
    @param old_id person id
    @type int
    @param new_id person id
    """
    from Cerebrum.modules.no.uio.voip.voipAddress import VoipAddress
    va = VoipAddress(db)
    va.clear()
    old_person_voip_addr = va.search(owner_entity_id=old_id)
    new_person_voip_addr = va.search(owner_entity_id=new_id)
    if (len(old_person_voip_addr) == 1
            and not new_person_voip_addr):
        # Transfer
        va.clear()
        try:
            va.find_by_owner_id(old_id)
        except Errors.NotFoundError:
            logger.info("No voip address found for owner id %s" % (old_id))
            return
        logger.debug("Change owner of voip_address %s to %s" % (va.entity_id,
                                                                new_id))
        va.populate(new_id)
        va.write_db()
    elif not old_person_voip_addr:
        logger.info("Nothing to transfer."
                    " Person %s owns no voip addresses" % (old_id))
    else:
        logger.warn("Source person %s owns voip addresses: %s" %
                    (old_id, old_person_voip_addr))
        logger.warn("Target person %s owns voip addresses:%s" %
                    (new_id, new_person_voip_addr))
        db.rollback()
        logger.warn("Cannot transfer, rollback all changes."
                    "Manual intervention required to join voip objects.")
        sys.exit(1)


def main():
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
    db = Factory.get('Database')()
    db.cl_init(change_program="join_persons")

    old_person = Factory.get('Person')(db)
    old_person.find(args.old)
    new_person = Factory.get('Person')(db)
    new_person.find(args.new)
    person_join(old_person, new_person,
                args.with_uio_ephorte, args.with_uio_voip, db)
    old_person.delete()

    if args.commit:
        db.commit()
        logger.info('Changes were committed to the database')
    else:
        db.rollback()
        logger.info('Dry run. Changes to the database were rolled back')

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
