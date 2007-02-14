# -*- coding: iso-8859-1 -*-
# Copyright 2005 University of Oslo, Norway
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

import re
from mx import DateTime

from Cerebrum import Errors
from Cerebrum import Constants
from Cerebrum.Utils import Factory
from Cerebrum.extlib.doc_exception import DocstringException
from Cerebrum.Constants import _SpreadCode
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.abcenterprise.Object2Cerebrum import Object2Cerebrum

class ABCMultipleEntitiesExistsError(DocstringException):
    """Several Entities exist with the same ID."""

class ABCErrorInData(DocstringException):
    """We hit an error in the data."""


class GiskeObject2Cerebrum(Object2Cerebrum):

    def store_group(self, group):
        """Apply a trait to groups made by this import."""
        self.__super.store_group(group)
        self._group.populate_trait(self.co.trait_group_imported,
                                   date=DateTime.now())
        self._group.write_db()
 

class OfkObject2Cerebrum(Object2Cerebrum):

    def __init__(self, source_system, logger):
        self.__super.__init__(source_system, logger)
        self._ac = Factory.get("Account")(self.db)
        # Create a dict of spreads to Constants.
        self.str2const = dict()
        for c in dir(self.co):
            tmp = getattr(self.co, c)
            if isinstance(tmp, _SpreadCode):
                self.str2const[str(tmp)] = tmp
        

    def _add_external_ids(self, entity, id_dict):
        if int(id_type) == self.co.externalid_fodselsnr:
            # Check fnr with the fnr module.
            try:
                fodselsnr.personnr_ok(id_dict[id_type])
            except fodselsnr.InvalidFnrError:
                raise ABCErrorInData, "fnr not valid: '%s'" %  id_dict[id_type]
        return self.__super._add_external_ids(entity, id_dict)

       
    def store_person(self, person):
        self.__super.store_person(person)
        if not self._person.has_spread(int(self.co.spread_ldap_per)):
            self._person.add_spread(int(self.co.spread_ldap_per))
        self._person.write_db()
        return ret


    def store_group(self, group):
        self.__super.store_group(group)
        self._group.populate_trait(self.co.trait_group_imported,
                                   date=DateTime.now())
        ret = self._group.write_db()
        return ret


    def create_account(self, owner):
        """Create a standard account."""
        if self._ac is None:
            self._ac = Factory.get('Account')(self.db)
        self._ac.clear()
        ac = owner.get_primary_account()
        if not ac:
            firstname = owner.get_name(self.co.system_cached, self.co.name_first)
            lastname = owner.get_name(self.co.system_cached, self.co.name_last)
            
            unames = self._ac.suggest_unames(self.co.account_namespace,
                                             firstname, lastname)
            self._ac.populate(unames[0], owner.entity_type, owner.entity_id,
                              None, self.default_creator_id, None)
            # Give tha account a password
            pwd = self._ac.make_passwd(unames[0])
            self._ac.write_db()
            self._ac.set_password(pwd)
            self._ac.write_db()
        else:
            self._ac.find(ac)
        for spread in cereconf.BOFHD_NEW_USER_SPREADS:
            try:
                self._ac.add_spread(int(self.str2const[spread]))
            except self.db.DatabaseError:
                pass
        self._ac.write_db()

        
    def add_group_member(self, group, entity_type, member):
        """Add an entity to a group."""
        self._group.clear()
        self._group.find_by_name(group[1])
        e_t = None
        if entity_type == "person":
            self._person.clear()
            self._person.find_by_external_id(member[0], member[1])

            ac = self._person.get_accounts()
            if len(ac) == 1:
                self._ac.clear()
                self._ac.find(ac[0][0])
            elif len(ac) == 0:
                self.create_account(self._person)
            else:
                # Multiple accounts
                for account in ac:
                    self._ac.clear()
                    self._ac.find(account[0])

                    # Add user to cache
                    self._add_group_cache(group[1], self._ac.account_name)
                    
                    if self._group.has_member(self._ac.entity_id,
                                              self.co.entity_account,
                                              self.co.group_memberop_union):
                        continue
                    self._group.add_member(self._ac.entity_id,
                                           self.co.entity_account,
                                           self.co.group_memberop_union)
                return self._group.write_db()
                
            # Add user to cache
            self._add_group_cache(group[1], self._ac.account_name)
            
            if self._group.has_member(self._ac.entity_id,
                                   self.co.entity_account,
                                   self.co.group_memberop_union):
                return
            self._group.add_member(self._ac.entity_id,
                                   self.co.entity_account,
                                   self.co.group_memberop_union)
            return self._group.write_db()


    def add_person_affiliation(self, ou, person, affiliation, status):
        """Add affiliations to a person's accounts as well."""
        self.__super.add_person_affiliation(ou, person, affiliation, status)
        
        ac = self._person.get_accounts()
        if len(ac) == 1:
            self._ac.clear()
            self._ac.find(ac[0][0])
        elif len(ac) == 0:
            self.create_account(self._person)
        # At this point we know self._ac to be the account we're after.
        # We don't want to call set_account_type if it already exists
        # so we search for it first. Hack-ish since we have no idea
        # what priority is, but no race-condition.
        aff_found = False
        for row in self._ac.get_account_types(all_persons_types=True,
                                              filter_expired=False):
            if(self._ou.entity_id == row['ou_id'] and affiliation == row['affiliation'] and
               self.entity_id == row['account_id']):
                aff_found = True
        if not aff_found:
            self._ac.set_account_type(self._ou.entity_id, affiliation)
            self._ac.write_db()
        else:
            # Multiple accounts
            for account in ac:
                self._ac.clear()
                self._ac.find(account[0])
                # We don't want to call set_account_type if it already exists
                # so we search for it first. Hack-ish since we have no idea
                # what priority is, but no race-condition.
                aff_found = False
                for row in self._ac.get_account_types(all_persons_types=True,
                                                      filter_expired=False):
                    if(self._ou.entity_id == row['ou_id'] and affiliation == row['affiliation'] and
                       self.entity_id == row['account_id']):
                        aff_found = True
                if not aff_found:
                    self._ac.set_account_type(self._ou.entity_id, affiliation)
                    self._ac.write_db()        
        return ret


    def __schoolyear(self):
        now = DateTime.now()
        year = str(now.year)
        year = year[2:]
        if now.month < 7:
            return int(year) - 1
        return int(year)


    def __active_group(self, group):
        m = re.search("^(\w+:)(\d\d)(:(.+))?", group)
        if not m:
            raise ABCErrorInData, "no year in group '%s'" % group
        y = int(m.group(2))
        if y == self.__schoolyear():
            if len(m.groups()) == 4:
                return "%s%s" % (m.group(1),m.group(4))
            else:
                return "%s" % m.group(1)
        return None


    def __diff_groups(self, new_grp, old_grp):
        remove = list()
        add = list()
        for mbr in new_grp:
            if mbr not in old_grp:
                add.append(mbr)
        for mbr in old_grp:
            if mbr not in new_grp:
                remove.append(mbr)
        return remove, add

    
    def commit(self):
        """Do cleanups and call db.commit()"""

        # Process the cache before calling commit. The following code
        # also operates with "autogroups" which are groups based on
        # this semester's active groups. They are created to always
        # have a active group "foo", based on "foo:04", "foo:05" and
        # so forth.

        # Get group names
        group_names = dict()
        for row in self._group.list_names(self.co.group_namespace):
            group_names[int(row['entity_id'])] = row['entity_name']

        # Set status on autogroups already in the database
        seen_autogroups = dict()
        for row in self._group.list_traits(self.co.trait_group_derived):
            name = group_names[int(row['entity_id'])]
            seen_autogroups.setdefault(name, False)

        # Traverse the groups we've seen during import, create groups
        # not found in the database and set their status to active
        for grp in self._groups.keys():
            a_grp = self.__active_group(grp)
            # We don't care about old groups.
            if not a_grp:
                continue
            # We see if the aouto group is in the database
            if not seen_autogroups.has_key(a_grp):
                # TODO: create the autogroup
                self._group.clear()
                self._group.populate(self.default_creator_id,
                                     self.co.group_visibility_all,
                                     a_grp, description=a_grp)
                self._group.write_db()
                self._group.populate_trait(self.co.trait_group_derived,
                                           date=DateTime.now())
                self._group.write_db()

                org_group = Factory.get('Group')(self.db)
                org_group.find_by_name(grp)
                # Get union types
                for member in org_group.list_members(member_type=self.co.entity_account)[0]:
                    self._group.add_member(member[1],
                                           self.co.entity_account,
                                           self.co.group_memberop_union)
                self._group.write_db()
            else:
                # Update the autogroup with new date in Trait
                self._group.clear()
                self._group.find_by_name(a_grp)
                self._group.populate_trait(self.co.trait_group_imported,
                                           date=DateTime.now())
                self._group.write_db()
            seen_autogroups[a_grp] = True

        # Add spread for new groups and remove spread for groups no longer
        # in the data file.
        for grp in seen_autogroups.keys():
            self._group.clear()
            self._group.find_by_name(grp)
            if seen_autogroups[grp]:
                if not self._group.has_spread(int(self.co.spread_oid_grp)):
                    self._group.add_spread(int(self.co.spread_oid_grp))
                    self._group.write_db()
            else:
                if self._group.has_spread(int(self.co.spread_oid_grp)):
                    self._group.delete_spread(int(self.co.spread_oid_grp))
                    self._group.write_db()
                    
        # Diff members in groups from the data file and in the database
        # and create the correct member list for autogroups
        autogroup_members = dict()
        for grp in self._groups.keys():
            self._group.clear()
            self._group.find_by_name(grp)
            for member in self._group.list_members(get_entity_name=True)[0]:
                if member[2] not in self._groups[grp]:
                    self._group.remove_member(member[1], self.co.group_memberop_union)
            self._group.write_db()
            agrp = self.__active_group(grp)
            if agrp:
                autogroup_members[agrp] = self._groups[grp]

        # Update the active autogroups
        for grp in autogroup_members.keys():
            self._group.clear()
            self._group.find_by_name(grp)
            current = dict()
            for member in self._group.list_members(get_entity_name=True)[0]:
                current.setdefault(member[2], [member[1], []])
                current[member[2]][1].append(self.co.group_memberop_union)
            remove, add = self.__diff_groups(autogroup_members[grp], current.keys())
            for mbr in remove:
                for op in current[mbr][1]:
                    self._group.remove_member(current[mbr][0], op)
            for mbr in add:
                self._ac.clear()
                self._ac.find_by_name(mbr)
                self._group.add_member(self._ac.entity_id,
                                       self.co.entity_account,
                                       self.co.group_memberop_union)
            self._group.write_db()
              
        self.db.commit()

    def rollback(self):
        self.db.rollback()

# arch-tag: d11dead8-9fd6-11da-8e4b-0869872fe5ca
