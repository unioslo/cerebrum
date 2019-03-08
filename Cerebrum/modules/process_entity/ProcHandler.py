#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2006-2018 University of Oslo, Norway
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
from __future__ import unicode_literals

import cereconf
import procconf

from six import text_type
from mx import DateTime

from Cerebrum import Errors
from Cerebrum.Utils import Factory, auto_super
from Cerebrum.Constants import _SpreadCode, _PersonAffiliationCode


class ProcHandler(object):
    """Handle entities. For now, business logic is implemented in code
    as a proof of concept. The goal is that this class will implement
    most of it's business logic and rules from the config file."""

    __metaclass__ = auto_super

    def __init__(self, db, logger):
        self.db = db
        self.logger = logger
        self._co = Factory.get('Constants')(self.db)
        self._ac = None
        self._group = None
        self.db.cl_init(change_program="proc_ent")
        # Populated on demand
        self.str2const = None
        self.default_creator_id = None
        self.ou2spread = None

    def _make_str2const(self):
        """Map Constant strings to actual objects."""
        if self.str2const:
            return
        self.str2const = dict()
        for c in dir(self._co):
            tmp = getattr(self._co, c)
            self.str2const[text_type(tmp)] = tmp

    def _populate_ou2spread(self):
        """Make a dict with all OUs and their derived spread from
        OU2ACCOUNT_SPREADS. Used for OU->account spread settings."""
        if self.ou2spread:
            return
        self._make_str2const()
        self.ou2spread = dict()
        ou = Factory.get('OU')(self.db)
        for row in ou.list_entity_spreads(self._co.entity_ou):
            ou_spread_str = text_type(_SpreadCode(int(row['spread'])))
            if ou_spread_str not in procconf.OU2ACCOUNT_SPREADS:
                continue
            acc_spread_str = procconf.OU2ACCOUNT_SPREADS[ou_spread_str]
            self.ou2spread.setdefault(row['entity_id'], []).append(
                self.str2const[acc_spread_str]
            )

    def _create_account(self, owner):
        """Create a standard account."""

        # str2const is something we need if we create new accounts.
        self._make_str2const()

        if not self._ac:
            self._ac = Factory.get('Account')(self.db)

        # default_creator_id is needed for new accounts
        if not self.default_creator_id:
            self._ac.clear()
            self._ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self.default_creator_id = self._ac.entity_id

        self._ac.clear()
        ac = owner.get_primary_account()
        if not ac:
            try:
                firstname = owner.get_name(self._co.system_cached,
                                           self._co.name_first)
                lastname = owner.get_name(self._co.system_cached,
                                          self._co.name_last)
            except Errors.NotFoundError:
                self.logger.warning(
                    "Person '%d' missing first- or lastname. User not built."
                    % owner.entity_id)
                return None
            self.logger.debug("Trying to find a uname for %s %s", firstname,
                              lastname)
            unames = self._ac.suggest_unames(self._co.account_namespace,
                                             firstname, lastname)
            self.logger.debug(
                "Name: %s %s, owner ent_type: %s, owner ent_id:%s" %
                (firstname, lastname, owner.entity_type, owner.entity_id))
            if not unames:
                self.logger.debug("No uname for %s %s" % (firstname, lastname))
            self._ac.populate(unames[0], owner.entity_type, owner.entity_id,
                              None, self.default_creator_id, None)
            # Write to db before adding traits
            self._ac.write_db()

            # Set new-account-traits
            self._ac_add_new_traits(self._ac)
            self._ac.write_db()
        else:
            self._ac.find(ac)

        return self._ac

    def process_person(self, person):
        """Sync spreads between a person and it's accounts."""

        # str2const is something we need if we create new accounts.
        self._make_str2const()

        if not self._ac:
            self._ac = Factory.get('Account')(self.db)

        def _diff_aff(new_aff, old_aff):
            """Return two lists. One with affiliations to remove and one
            with affiliations to add."""
            remove = list()
            add = list()
            for tpl in new_aff:
                if tpl not in old_aff:
                    add.append(tpl)
            for tpl in old_aff:
                if tpl not in new_aff:
                    remove.append(tpl)
            return remove, add

        # Find the person's affiliations
        person_affiliations = []
        for row in person.get_affiliations():
            person_affiliations.append((row['ou_id'], row['affiliation']))

        # If the person in question doesn't have any affiliations, we
        # don't create any account.
        accounts = person.get_accounts(filter_expired=False)
        if len(accounts) == 0:
            if person_affiliations:
                ac = self._create_account(person)
                if ac:
                    self.logger.info("Person '%d' got new account '%s'." %
                                     (person.entity_id, ac.account_name))
                # Take care of person affiliations too

            else:
                self.logger.info(
                    "Person '%d' have no affiliations. No account created." %
                    person.entity_id)

        # Clean up in spreads
        change = False
        for spread in procconf.PERSON_SPREADS:
            if person_affiliations:
                if not person.has_spread(int(self.str2const[spread])):
                    person.add_spread(int(self.str2const[spread]))
                    self.logger.info("Person '%d' got spread '%s'." %
                                     (person.entity_id, spread))
                    change = True
            else:
                if person.has_spread(int(self.str2const[spread])):
                    person.delete_spread(int(self.str2const[spread]))
                    self.logger.info("Person '%d' have no affiliations. "
                                     "Spread '%s' deleted." %
                                     (person.entity_id, spread))
                    change = True
        if change:
            person.write_db()

        # Loop over the person's account(s) and correct affiliations
        # and spreads
        for account in person.get_accounts(filter_expired=False):
            account_affiliations = []
            self._ac.clear()
            self._ac.find(account['account_id'])
            # Update affiliations
            for row in self._ac.get_account_types(filter_expired=False):
                account_affiliations.append((row['ou_id'], row['affiliation']))

            rem, add = _diff_aff(person_affiliations, account_affiliations)
            change = False
            for r in rem:
                self._ac.del_account_type(r[0], r[1])
                change = True
                self.logger.info("Account '%s' removed type '%s', '%s'." %
                                 (self._ac.account_name, r[0], r[1]))
            for a in add:
                self._ac.set_account_type(a[0], a[1])
                change = True
                self.logger.info("Account '%s' added type '%s', '%s'." %
                                 (self._ac.account_name, a[0], a[1]))
            # Set expire_date if no account_types
            if not person_affiliations:
                # Don't reset expire_date on an already expired account
                if not self._ac.expire_date:
                    self._ac.expire_date = DateTime.now()
                    change = True
                    self.logger.info("Account '%s' set to expired." %
                                     self._ac.account_name)
            else:
                # The account is about to get account_types so we restore it
                # by removing expire_date
                if self._ac.expire_date:
                    self._ac.expire_date = None
                    change = True
                    self.logger.info("Account '%s' is restored." %
                                     self._ac.account_name)
                    self._ac_add_new_traits(self._ac)

            # TODO: Limit the removal of spreads to types known by proc_entity

            # Update account spreads (if set in the config)
            if (hasattr(procconf, 'ACCOUNT_SPREADS') and
                    hasattr(procconf, 'OU2ACCOUNT_SPREADS')):
                raise Errors.ProgrammingError(
                    "Both ACCOUNT_SPREADS and OU2ACCOUNT_SPREADS in procconf.")
            elif (hasattr(procconf, 'ACCOUNT_SPREADS') and
                  procconf.ACCOUNT_SPREADS):
                acc_spreads = []
                for i in person_affiliations:
                    aff_str = str(_PersonAffiliationCode(i[1]))
                    if aff_str not in procconf.ACCOUNT_SPREADS:
                        continue
                    spreads = [int(self.str2const[s]) for s in
                               procconf.ACCOUNT_SPREADS[aff_str]]
                    acc_spreads += [s for s in spreads if s not in acc_spreads]
                for row in self._ac.get_spread():
                    # Annoying "feature". get_spread() return a tuple of
                    # one-element tuples.
                    if int(row[0]) not in acc_spreads:
                        self._ac.delete_spread(row[0])
                        self.logger.info("Account '%s' removed spread '%s'." %
                                         (self._ac.account_name,
                                          str(_SpreadCode(int(row[0])))))
                        change = True
                for spread in acc_spreads:
                    if not self._ac.has_spread(spread):
                        self._ac.add_spread(spread)
                        self.logger.info("Account '%s' added spread '%s'." %
                                         (self._ac.account_name,
                                          str(_SpreadCode(int(spread)))))
                        change = True
            elif (hasattr(procconf, 'OU2ACCOUNT_SPREADS') and
                  procconf.OU2ACCOUNT_SPREADS):
                self._populate_ou2spread()
                acc_spreads = []
                for ou, aff in person_affiliations:
                    for s in self.ou2spread[ou]:
                        if s not in acc_spreads:
                            acc_spreads.append(s)
                for row in self._ac.get_spread():
                    # Annoying "feature". get_spread() return a tuple of
                    # one-element tuples.
                    if int(row[0]) not in acc_spreads:
                        self._ac.delete_spread(row[0])
                        self.logger.info("Account '%s' removed spread '%s'." %
                                         (self._ac.account_name,
                                          str(_SpreadCode(int(row[0])))))
                        change = True
                for spread in acc_spreads:
                    if not self._ac.has_spread(spread):
                        self._ac.add_spread(spread)
                        self.logger.info("Account '%s' added spread '%s'." %
                                         (self._ac.account_name,
                                          str(_SpreadCode(int(spread)))))
                        change = True

            if change:
                self._ac.write_db()
                # print(self._ac.account_name, person_affiliations,
                #       self._ac.get_spread())

    def _diff_groups(self, grp, shdw_grp):
        """Make sure grp's persons' accounts are represented in the
        shdw_grp."""

        person = Factory.get('Person')(self.db)
        grp_accounts = list()
        for member in grp.search_members(group_id=grp.entity_id):
            person.clear()
            person.entity_id = int(member["member_id"])
            a_id = person.get_primary_account()
            if not a_id:
                self.logger.info("Person '%d' has no account. Skipping",
                                 person.entity_id)
                continue
            grp_accounts.append(person.get_primary_account())
        shdw_grp_accounts = list()
        for member in shdw_grp.search_members(group_id=shdw_grp.entity_id):
            shdw_grp_accounts.append(int(member["member_id"]))
        # Sync shdw_grp with grp
        change = False
        for a_id in grp_accounts:
            if a_id not in shdw_grp_accounts:
                shdw_grp.add_member(a_id)
                change = True
        for a_id in shdw_grp_accounts:
            if a_id not in grp_accounts:
                shdw_grp.remove_member(a_id)
                change = True
        if change:
            shdw_grp.write_db()
        return change

    def process_group(self, group_name):
        """Check the group's `shadow group`."""

        self._make_str2const()

        # Init the needed objects if not already done
        if not self._group:
            self._group = Factory.get('Group')(self.db)
        if not self.default_creator_id:
            if self._ac is None:
                self._ac = Factory.get('Account')(self.db)
            self._ac.clear()
            self._ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self.default_creator_id = self._ac.entity_id

        # See if there is a shadow group
        shdw_grp = Factory.get('Group')(self.db)
        shadow = procconf.SHADOW(group_name)
        # See if this group got a shadow name
        if not shadow:
            self.logger.warning(
                "prc_grp: Group '%s' has a name not compatible with the "
                "shadow naming scheme." % group_name)
            return

        # Try to initialize the object
        try:
            self._group.clear()
            self._group.find_by_name(group_name)
            source_system_str = procconf.SOURCE['source_system']
            for row in self._group.get_external_id(source_system=int(
                    self._co.AuthoritativeSystem(source_system_str))):
                grp_id_type = str(self._co.EntityExternalId(row['id_type']))

            shdw_trait_str = procconf.GRP_TYPE_TO_GRP_TRAIT[grp_id_type]

            self.logger.debug("prc_grp: Group '%s' found." % group_name)
            # We found a group that something potentially happened to.
            # Check if it is a shadow group. If it is, skip it.
            if self._group.get_trait(self._co.trait_group_derived):
                self.logger.debug("prc_grp: Group '%s' is a shadow group." %
                                  group_name)
                return

            try:
                shdw_grp.find_by_name(shadow)
                self.logger.debug(
                    "prc_grp: Group '%s' has a shadow group '%s'." %
                    (group_name, shadow))

            except Errors.NotFoundError:
                # None found, so we make one. Populate it with
                # trait_group_derived
                shdw_grp.clear()
                shdw_grp.populate(self.default_creator_id,
                                  self._co.group_visibility_all,
                                  shadow,
                                  self._group.description)
                shdw_grp.write_db()
                shdw_grp.populate_trait(self._co.trait_group_derived,
                                        date=DateTime.now())
                shdw_grp.write_db()
                self.logger.info("prc_grp: Shadow group '%s' created." %
                                 shadow)
            change = False
            if shdw_trait_str is not None:
                if not shdw_grp.get_trait(
                        int(self._co.EntityTrait(shdw_trait_str))):
                    shdw_grp.populate_trait(int(self._co.EntityTrait(
                        shdw_trait_str)), date=DateTime.now())
                    change = True
            for spread in procconf.SHADOW_GROUP_SPREAD:
                if not shdw_grp.has_spread(int(self.str2const[spread])):
                    shdw_grp.add_spread(int(self.str2const[spread]))
                    change = True
            if change:
                shdw_grp.write_db()
            # At this point, we have the master group, and a shadow group
            # which we know exists. Diff members.
            change = self._diff_groups(self._group, shdw_grp)
            if change:
                self.logger.info(
                    "prc_grp: Shadow group '%s' synced with group '%s' "
                    "successfully." % (shadow, group_name))
        except Errors.NotFoundError:
            # Group we have gotten is deleted. Try to look up it's potential
            # shadow group
            try:
                self._group.clear()
                self._group.find_by_name(shadow)
                self.logger.debug("prc_grp: Group '%s' not found, but name "
                                  "matching '%s' found" % (group_name, shadow))
                # Name matches a shadow group. Check if it actually is.
                # If it is, we delete it, if not, do nothing.
                if self._group.get_trait(self._co.trait_group_derived):
                    self._group.delete()
                    self.logger.info("prc_grp: Shadow group '%s' deleted." %
                                     shadow)
                return
            except Errors.NotFoundError:
                # No shadow group found. Do nothing.
                self.logger.debug("prc_grp: Group '%s' and shadow group '%s' "
                                  "not found." % (group_name, shadow))
                return

    def process_ou(self, ou):
        """Check the OU's data."""

        self._make_str2const()

        change = False
        if not hasattr(procconf, "OU_SPREADS"):
            return
        for spread in procconf.OU_SPREADS:
            if not ou.has_spread(int(self.str2const[spread])):
                ou.add_spread(int(self.str2const[spread]))
                self.logger.info("prc_ou: OU '%s' got spread '%s'." %
                                 (ou.entity_id, spread))
                change = True
        if change:
            ou.write_db()

    def ac_type_add(self, account_id, affiliation, ou_id):
        """Adds an account to special groups which represent an
        affiliation at an OU. Make the group if it's not present."""

        self._make_str2const()

        if self._ac is None:
            self._ac = Factory.get('Account')(self.db)
            self._ac.clear()

        ou = Factory.get("OU")(self.db)
        ou.find(ou_id)

        aff2txt = {int(self._co.affiliation_ansatt): 'Tilsette',
                   int(self._co.affiliation_teacher): 'Tilsette',
                   int(self._co.affiliation_elev): 'Elevar'}

        # Look up the group
        grp_name = "%s %s" % (self._get_ou_acronym(ou),
                              aff2txt[int(affiliation)])
        if not self._group:
            self._group = Factory.get('Group')(self.db)
        if not self.default_creator_id:
            if self._ac is None:
                self._ac = Factory.get('Account')(self.db)
            self._ac.clear()
            self._ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self.default_creator_id = self._ac.entity_id
        try:
            self._group.clear()
            self._group.find_by_name(grp_name)
            self.logger.debug("ac_type_add: Group '%s' found." % grp_name)
        except Errors.NotFoundError:
            self._group.populate(self.default_creator_id,
                                 self._co.group_visibility_all,
                                 grp_name,
                                 description=grp_name)
            self._group.write_db()
            for spread in procconf.AC_TYPE_GROUP_SPREAD:
                if not self._group.has_spread(int(self.str2const[spread])):
                    self._group.add_spread(int(self.str2const[spread]))
            self._group.write_db()
            self.logger.info("ac_type_add: Group '%s' created." % grp_name)
        if not self._group.get_trait(self._co.trait_group_affiliation):
            self._group.populate_trait(self._co.trait_group_affiliation,
                                       date=DateTime.now())
            self._group.write_db()
        if not self._group.has_member(account_id):
            self._group.add_member(account_id)
            self._group.write_db()
            self.logger.info("ac_type_add: Account '%s' added to group '%s'." %
                             (account_id, grp_name))

    def ac_type_del(self, account_id, affiliation, ou_id):
        """Deletes an account from special groups which represent an
        affiliation at an OU. Delete the group if no members are present."""
        ou = Factory.get("OU")(self.db)
        ou.find(ou_id)

        # Look up the group
        grp_name = "%s %s" % (self._get_ou_acronym(ou), affiliation)
        if not self._group:
            self._group = Factory.get('Group')(self.db)
        try:
            self._group.clear()
            self._group.find_by_name(grp_name)
            self.logger.debug("ac_type_del: Group '%s' found." % grp_name)
            if self._group.has_member(account_id):
                self._group.remove_member(account_id)
                self._group.write_db()
                self.logger.info(
                    "ac_type_del: Account '%s' deleted from group '%s'." %
                    (account_id, grp_name))
            # Deal with empty groups as well
            if len(list(self._group.search_members(
                    group_id=self._group.entity_id,
                    indirect_members=True,
                    member_type=self._co.entity_account))) == 0:
                self._group.delete()
                self._group.write_db()
        except Errors.NotFoundError:
            self.logger.debug(
                "ac_type_del: Group '%s' not found. Nothing to do" % grp_name)

    @staticmethod
    def _ac_add_new_traits(ac):
        """Give an account new traits, as defined in
        procconf.NEW_ACCOUNT_TRAITS. This method should be called when creating
        and restoring accounts.
        """
        for trait in getattr(procconf, 'NEW_ACCOUNT_TRAITS', ()):
            ac.populate_trait(code=trait, date=DateTime.now())
        # write_db is handled outside of this method

    def _get_ou_acronym(self, ou):
        """Retrieve ou's acronym.

        If none is present in Norwegian bokmål, return ''.
        """

        return ou.get_name_with_language(name_variant=self._co.ou_name_acronym,
                                         name_language=self._co.language_nb,
                                         default="")

    # end _get_ou_acronym

    def commit(self):
        """Clean up if needed."""
        self.db.commit()

    def rollback(self):
        """Roll back all changes done."""
        self.db.rollback()
