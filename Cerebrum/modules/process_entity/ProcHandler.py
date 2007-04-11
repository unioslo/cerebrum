#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2006 University of Oslo, Norway
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

import cerebrum_path
import cereconf
import procconf

from mx import DateTime

from Cerebrum import Errors
from Cerebrum.Utils import Factory, auto_super
from Cerebrum.Constants import _SpreadCode

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
        

    def _make_str2const(self):
        if not self.str2const:
            self.str2const = dict()
            for c in dir(self._co):
                tmp = getattr(self._co, c)
                if isinstance(tmp, _SpreadCode):
                    self.str2const[str(tmp)] = tmp



    def _create_account(self, owner):
        """Create a standard account."""

        # str2const is something we need if we create new accounts.
        if not self.str2const:
            self._make_str2const()

        if self._ac is None:
            self._ac = Factory.get('Account')(self.db)

        # default_creator_id is needed for new accounts
        if not self.default_creator_id:
            self._ac.clear()
            self._ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self.default_creator_id = self._ac.entity_id
        
        self._ac.clear()
        ac = owner.get_primary_account()
        if not ac:
            firstname = owner.get_name(self._co.system_cached, self._co.name_first)
            lastname = owner.get_name(self._co.system_cached, self._co.name_last)
            unames = self._ac.suggest_unames(self._co.account_namespace,
                                             firstname, lastname)
            self._ac.populate(unames[0], owner.entity_type, owner.entity_id,
                              None, self.default_creator_id, None)
            # Give the account a password
            pwd = self._ac.make_passwd(unames[0])
            self._ac.write_db()
            self._ac.set_password(pwd)
            self._ac.write_db()
        else:
            self._ac.find(ac)
            
        change = False
        for spread in cereconf.BOFHD_NEW_USER_SPREADS:
            if not self._ac.has_spread(int(self.str2const[spread])):    
                self._ac.add_spread(int(self.str2const[spread]))
                change = True
        if change:
            self._ac.write_db()
            
        return self._ac
                    

    def process_person(self, person):
        """Sync spreads between a person and it's accounts."""
        
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
        for row in person.list_affiliations(person_id=person.entity_id):
            person_affiliations.append((row['ou_id'], row['affiliation']))

        # If the person in question doesn't have any affiliations, we
        # don't create any account.
        accounts = person.get_accounts()
        if len(accounts) == 0:
            if person_affiliations:
                ac = self._create_account(person)
                self.logger.info("Person '%d' got new account '%s'." % (person.entity_id, ac.account_name))
                # Take care of person affiliations too
                
            else:
                self.logger.info("Person '%d' have no affiliations. No account created." % person.entity_id)

        # Loop over the person's account(s) and correct affiliations
        for account in person.get_accounts():
            account_affiliations = []
            self._ac.clear()
            self._ac.find(account['account_id'])
            for row in self._ac.get_account_types(all_persons_types=True,
                                                  filter_expired=False):
                account_affiliations.append((row['ou_id'], row['affiliation']))

            rem, add = _diff_aff(person_affiliations, account_affiliations)
            changed = False
            for r in rem:
                self._ac.del_account_type(r[0], r[1])
                changed = True
                self.logger.info("Account '%s' removed type '%s', '%s'." % (self._ac.account_name, r[0], r[1]))
            for a in add:
                self._ac.set_account_type(a[0], a[1])
                changed = True
                self.logger.info("Account '%s' added type '%s', '%s'." % (self._ac.account_name, a[0], a[1]))
            # TBD: set expire_date if no types remain?
            if changed:
                self._ac.write_db()


    def _diff_groups(self, grp, shdw_grp):
        """Make sure grp's persons' accounts are represented in the
        shdw_grp."""

        person = Factory.get('Person')(self.db)
        grp_accounts = list()
        for member in grp.list_members()[0]:
            person.clear()
            person.entity_id = int(member[1])
            a_id = person.get_primary_account()
            if not a_id:
                self.logger.info("Person '%d' has no account. Skipping" % person.entity_id)
                continue
            grp_accounts.append(person.get_primary_account())
        shdw_grp_accounts = list()
        for member in shdw_grp.list_members()[0]:
            shdw_grp_accounts.append(member[1])
        # Sync shdw_grp with grp
        change = False
        for a_id in grp_accounts:
            if a_id not in shdw_grp_accounts:
                shdw_grp.add_member(a_id, self._co.entity_account,
                                    self._co.group_memberop_union)
                change = True
        for a_id in shdw_grp_accounts:
            if a_id not in grp_accounts:
                shdw_grp.remove_member(a_id, self._co.group_memberop_union)
                change = True
        if change:
            shdw_grp.write_db()
        return change
        

    def process_group(self, group_name):
        """Check the group's `shadow group`."""

        if not self.str2const:
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
            self.logger.warning("prc_grp: Group '%s' has a name not compatible with the shadow naming scheme." % group_name) 
            return
                        
        # Try to initialize the object
        try:
            self._group.clear()
            self._group.find_by_name(group_name)
            self.logger.debug("prc_grp: Group '%s' found." % group_name)
            # We found a group that something potentially happened to.
            # Check if it is a shadow group. If it is, skip it.
            if self._group.get_trait(self._co.trait_group_derived):
                self.logger.debug("prc_grp: Group '%s' is a shadow group." % group_name)
                return
            
            try:
                shdw_grp.find_by_name(shadow)
                self.logger.debug("prc_grp: Group '%s' has a shadow group '%s'." % (group_name, shadow))
                
            except Errors.NotFoundError:
                # None found, so we make one. Populate it with
                # trait_group_derived
                shdw_grp.clear()
                shdw_grp.populate(self.default_creator_id,
                                  self._co.group_visibility_all,
                                  shadow)
                shdw_grp.write_db()
                shdw_grp.populate_trait(self._co.trait_group_derived,
                                        date=DateTime.now())
                shdw_grp.write_db()
                self.logger.info("prc_grp: Shadow group '%s' created." % shadow)
            change = False
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
                self.logger.info("prc_grp: Shadow group '%s' synced with group '%s' successfully." % (shadow,group_name))
        except Errors.NotFoundError:
            # Group we have gotten is deleted. Try to look up it's potential
            # shadow group
            try:                
                self._group.clear()
                self._group.find_by_name(shadow)
                self.logger.debug("prc_grp: Group '%s' not found, but name matching '%s' found" % (group_name,shadow))
                # Name matches a shadow group. Check if it actually is.
                # If it is, we delete it, if not, do nothing.
                if self._group.get_trait(self._co.trait_group_derived):
                    self._group.delete()
                    self.logger.info("prc_grp: Shadow group '%s' deleted." % shadow)
                return
            except Errors.NotFoundError:
                # No shadow group found. Do nothing.
                self.logger.debug("prc_grp: Group '%s' and shadow group '%s' not found." % (group_name,shadow))
                return
        

    def process_ou(self, ou):
        """Check the OU's data."""

        if not self.str2const:
            self._make_str2const()
        
        change = False
        for spread in procconf.OU_SPREADS:
            if not ou.has_spread(int(self.str2const[spread])):
                ou.add_spread(int(self.str2const[spread]))
                self.logger.info("prc_ou: OU '%s' got spread '%s'." % (ou.entity_id, spread))
                change = True
        if change:
            ou.write_db()


    def ac_type_add(self, account_id, affiliation, ou_id):
        """Adds an account to special groups which represent an
        affiliation at an OU. Make the group if it's not present."""

        if not self.str2const:
            self._make_str2const()
        
        if self._ac is None:
            self._ac = Factory.get('Account')(self.db)
            self._ac.clear()

        ou = Factory.get("OU")(self.db)
        ou.find(ou_id)

        aff2txt = { int(self._co.affiliation_ansatt) : 'Tilsette',
                    int(self._co.affiliation_teacher) : 'Tilsette',
                    int(self._co.affiliation_elev) : 'Elevar' }

        # Look up the group
        grp_name = "%s %s" % (ou.acronym, aff2txt[int(affiliation)])
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
                                 grp_name)
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
        if not self._group.has_member(account_id, self._co.entity_account,
                                      self._co.group_memberop_union):
            self._group.add_member(account_id, self._co.entity_account,
                                   self._co.group_memberop_union)
            self._group.write_db()
            self.logger.info("ac_type_add: Account '%s' added to group '%s'." % (account_id, grp_name))

    def ac_type_del(self, account_id, affiliation, ou_id):
        """Deletes an account from special groups which represent an
        affiliation at an OU. Delete the group if no members are present."""
        ou = Factory.get("OU")(self.db)
        ou.find(ou_id)

        aff2txt = { int(self._co.affiliation_ansatt) : 'Tilsette',
                    int(self._co.affiliation_teacher) : 'Tilsette',
                    int(self._co.affiliation_elev) : 'Elevar' }

        # Look up the group
        grp_name = "%s %s" % (ou.acronym, aff2txt[int(affiliation)])
        if not self._group:
            self._group = Factory.get('Group')(self.db)
        try:
            self._group.clear()
            self._group.find_by_name(grp_name)
            self.logger.debug("ac_type_del: Group '%s' found." % grp_name)
            if self._group.has_member(account_id, self._co.entity_account,
                                      self._co.group_memberop_union):
                self._group.remove_member(account_id, self._co.group_memberop_union)
                self._group.write_db()
                self.logger.info("ac_type_del: Account '%s' deleted from group '%s'." % (account_id, grp_name))
            # Deal with empty groups as well
            if len(self._group.get_members()) == 0:
                self._group.delete()
                self._group.write_db()
        except Errors.NotFoundError:
            self.logger.debug("ac_type_del: Group '%s' not found. Nothing to do" % grp_name)

    def commit(self):
        """Clean up if needed."""
        self.db.commit()


    def rollback(self):
        """Roll back all changes done."""
        self.db.rollback()
