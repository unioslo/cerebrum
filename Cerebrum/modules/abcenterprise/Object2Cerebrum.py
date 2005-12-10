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

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.extlib.doc_exception import DocstringException

class ABCMultipleEntitiesExistsError(DocstringException):
    """Several Entities exist with the same ID."""

class ABCErrorInData(DocstringException):
    """We hit an error in the data."""

class Object2Cerebrum(object):

    def __init__(self, source_system):
        self.source_system = source_system

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

    def commit(self):
        """Call db.commit()"""
        self.db.commit()


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
            lst = entity.list_external_ids(source_system=self.source_system,
                                           id_type=id_type,
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

        # Deal with addresses and contacts.
        
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
        # Deal with names
        #    TODO: Names
        #    self._person.affect_names(co.system_sas, co.name_first, co.name_last)
        # Set all IDs
        self._add_external_ids(self._person, person._ids)

        # Deal with addresses and contacts.
            
        return (self._person.write_db(), self._person.entity_id)


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
                                     
        return (self._group.write_db(), self._group.entity_id)

    def store_relation(self, relation):
        """Make a relation in Cerebrum. This is usually members
        in a group, affiliations or people belonging to an OU."""

        type = relation.type
        subject = relation.subject
        object = relation.object

        
    def add_group_member(self, group, entity_type, member):
        """Add an entity to a group."""
        self._group.clear()
        self._group.find_by_name(group[1])
        e_t = None
        if entity_type == "person":
            self._person.clear()
            self._person.find_by_external_id(member[0], member[1])
            if self._group.has_member(self._person.entity_id,
                                   self.co.entity_person,
                                   self.co.group_memberop_union):
                return
            self._group.add_member(self._person.entity_id,
                                   self.co.entity_person,
                                   self.co.group_memberop_union)
            return self._group.write_db()

    def add_person_affiliation(self, ou, person, affiliation, status):
        """Add an affiliation for a person."""
        self._person.clear()
        self._person.find_by_external_id(person[0], person[1])
        self._ou.clear()
        self._ou.find_by_external_id(ou[0], ou[1])
        self._person.add_affiliation(self._ou.entity_id, affiliation,
                                     self.source_system, status)
        return self._person.write_db()
