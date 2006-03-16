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

class ABCMultipleEntitiesExistsError(DocstringException):
    """Several Entities exist with the same ID."""

class ABCErrorInData(DocstringException):
    """We hit an error in the data."""

class Object2Cerebrum(object):

    def __init__(self, source_system, logger):
        self.source_system = source_system
        self.logger = logger

        self.db = Factory.get('Database')()
        self.co = Factory.get("Constants")(self.db)

        self.db.cl_init(change_program="obj(%s)" % self.source_system)

        # TBD: configureable? does it belong here at all?
        ac = Factory.get("Account")(self.db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.default_creator_id = ac.entity_id

        self._person = None
        self._ou = None
        self._group = None
        self._ac = Factory.get("Account")(self.db)
        self.str2const = dict()
        for c in dir(self.co):
            tmp = getattr(self.co, c)
            if isinstance(tmp, _SpreadCode):
                self.str2const[str(tmp)] = tmp

        # Set up the group cache
        # This is updated in store_group and add_group_member.
        self._groups = dict()
        self._affiliations = dict()

    def _add_external_ids(self, entity, id_dict):
        """Common external ID operations."""
        entity.affect_external_id(self.source_system, *id_dict.keys())
        for id_type in id_dict.keys():
            if id_type is None or id_dict[id_type] is None:
                raise ABCErrorInData
            entity.populate_external_id(self.source_system,
                                        id_type,
                                        id_dict[id_type])


    def _check_entity(self, entity, data_entity):
        """Check for conflicting entities or return found or None."""
        entities = list()
        for id_type in data_entity._ids.keys():
            lst = entity.list_external_ids(id_type=id_type,
                                           external_id = data_entity._ids[id_type])
            for row in lst:
                entities.append(row['entity_id'])
        entity_id = None
        for id in entities:
            if entity_id <> id and entity_id <> None:
                # There are entities out there with our IDs.
                # Fat error and exit
                raise ABCMultipleEntitiesExistsError
            entity_id = id

        if entity_id:
            # We found one
            return entity_id
        else:
            # Noone in the database could be found with our IDs.
            # This is fine, write_db() figures it up.
            return None

        
    def store_ou(self, ou):
        """Pass a DataOU to this function and it gets stored
        in Cerebrum."""
        if self._ou is None:
            self._ou = Factory.get("OU")(self.db)
        self._ou.clear()

        entity_id = self._check_entity(self._ou, ou)

        if entity_id:
            # We found one
            self._ou.find(entity_id)

        self._ou.populate(ou.ou_names['name'],
                          ou.ou_names['acronym'],
                          ou.ou_names['short_name'],
                          ou.ou_names['display_name'],
                          ou.ou_names['sort_name'],
                          None)
        self._add_external_ids(self._ou, ou._ids)

        # TODO: Deal with addresses and contacts.
        
        return (self._ou.write_db(), self._ou.entity_id)


    def set_ou_parent(self, child_entity_id, perspective, parent):
        """Set a parent ID on an OU. Parent may be an entity_id or a
        tuple with an ext_is_type and an ext_id."""
        self._ou.clear()
        if isinstance(parent, tuple):
            self._ou.find_by_external_id(parent[0], parent[1])
            parent = self._ou.entity_id
            self._ou.clear()
        self._ou.find(child_entity_id)
        self._ou.set_parent(perspective, parent)
        return self._ou.write_db()


    def store_person(self, person):
        """Pass a DataPerson to this function and it gets stored
        in Cerebrum."""
        if self._person is None:
            self._person = Factory.get("Person")(self.db)
        self._person.clear()

        entity_id = self._check_entity(self._person, person)
        if entity_id:
            # We found one
            self._person.find(entity_id)
        # else:
            # Noone in the database could be found with our IDs.
            # This is fine, write_db() figures it up.

        # Populate the person
        self._person.populate(person.birth_date, person.gender)
        self._add_external_ids(self._person, person._ids)
        # Deal with names
        self._person.affect_names(self.source_system, *person._names.keys())
        for name_type in person._names.keys():
            self._person.populate_name(name_type,
                                       person._names[name_type])
        # Deal with addresses and contacts.
        ret = self._person.write_db()
        found_spread = False
        if not self._person.has_spread(int(self.co.spread_ldap_per)):
            self._person.add_spread(int(self.co.spread_ldap_per))
        self._person.write_db()
        return (ret, self._person.entity_id)


    def store_group(self, group):
        """Stores a group in Cerebrum."""
        if self._group is None:
            self._group = Factory.get("Group")(self.db)
        self._group.clear()

        try:
            self._group.find_by_name(group.name)
        except Errors.NotFoundError:
            # No group found
            pass
        
        self._group.populate(self.default_creator_id,
                             self.co.group_visibility_all,
                             group.name, description=group.desc)
        result = self._group.write_db()
        self._group.populate_trait(self.co.trait_group_imported,
                                   date=DateTime.now())
        self._group.write_db()
        # Add group to "seen" cache.
        self._groups.setdefault(group.name, [])
        return result


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
            self._ac.write_db()
        else:
            self._ac.find(ac)
        for spread in cereconf.BOFHD_NEW_USER_SPREADS:
            try:
                self._ac.add_spread(int(self.str2const[spread]))
            except self.db.DatabaseError:
                pass
        if not self._ac.has_spread(int(self.co.spread_oid_acc)):
            self._ac.add_spread(int(self.co.spread_oid_acc))
        self._ac.write_db()


    def _add_cache(self, group, member):
        if self._groups.has_key(group):
            if member not in self._groups[group]:
                self._groups[group].append(member)
        else:
            self.logger.warning("Group '%s' is not in the file." % group) 

        
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
                    self._add_cache(group[1], self._ac.account_name)
                    
                    if self._group.has_member(self._ac.entity_id,
                                              self.co.entity_account,
                                              self.co.group_memberop_union):
                        continue
                    self._group.add_member(self._ac.entity_id,
                                           self.co.entity_account,
                                           self.co.group_memberop_union)
                return self._group.write_db()
                
            # Add user to cache
            self._add_cache(group[1], self._ac.account_name)
            
            if self._group.has_member(self._ac.entity_id,
                                   self.co.entity_account,
                                   self.co.group_memberop_union):
                return
            self._group.add_member(self._ac.entity_id,
                                   self.co.entity_account,
                                   self.co.group_memberop_union)
            return self._group.write_db()


    def add_person_affiliation(self, ou, person, affiliation, status):
        """Add an affiliation for a person."""
        self._person.clear()
        try:
            self._person.find_by_external_id(person[0], person[1])
        except Errors.NotFoundError:
            raise ABCErrorInData, "no person with id: %s, %s" % (person[0],
                                                                 person[1]) 
        self._ou.clear()
        self._ou.find_by_external_id(ou[0], ou[1])
        self._person.add_affiliation(self._ou.entity_id, affiliation,
                                     self.source_system, status)
        ret = self._person.write_db()
        
        # Submit affiliation data to the cache.
        self._affiliations.setdefault(self._person.entity_id, [])
        self._affiliations[self._person.entity_id].append((affiliation,
                                                           self._ou.entity_id))

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
                self._ac.set_account_type(self._ou.entity_id, affiliation)
                self._ac.write_db()
                    
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
        m = re.search("^(\w+:)(\d\d):(.+)", group)
        if not m:
            raise DocstringException, "no year in group '%'" % group
        y = int(m.group(2))
        if y == self.__schoolyear():
            return "%s%s" % (m.group(1),m.group(3))
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
                if not self._group.has_spread(int(self.co.spread_oid_grp)):
                    self._group.add_spread(int(self.co.spread_oid_grp))
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

        # Update affiliations for people
        for row in self._person.list_affiliations(source_system=self.source_system):
            p_id = int(row['person_id'])
            aff = row['affiliation']
            ou_id = row['ou_id']
            if self._affiliations.has_key(p_id):
                if not (aff, ou_id) in self._affiliations[p_id]:
                    if not self._person.entity_id == p_id:
                        self._person.clear()
                        self._person.find(p_id)
                    self._person.delete_affiliation(ou_id, aff, self.source_system)
            else:
                # Person no longer in the data file
                if not self._person.entity_id == p_id:
                    self._person.clear()
                    self._person.find(p_id)
                self._person.delete_affiliation(ou_id, aff, self.source_system)
                
        self.db.commit()

    def rollback(self):
        self.db.rollback()

# arch-tag: d11dead8-9fd6-11da-8e4b-0869872fe5ca
