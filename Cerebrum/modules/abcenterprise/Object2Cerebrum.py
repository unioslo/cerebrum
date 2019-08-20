# -*- coding: utf-8 -*-
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

from __future__ import unicode_literals
import cereconf
import abcconf

from mx import DateTime

from Cerebrum import Errors
from Cerebrum.Utils import Factory, auto_super
from Cerebrum.extlib.doc_exception import DocstringException


class ABCMultipleEntitiesExistsError(DocstringException):
    """Several Entities exist with the same ID."""


class ABCErrorInData(DocstringException):
    """We hit an error in the data."""


class Object2Cerebrum(object):
    __metaclass__ = auto_super

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

        self._person = Factory.get("Person")(self.db)
        self._ou = None
        self._group = None

        # Set up the spread, group and affiliation cache
        # This is updated in store_group and add_group_member.
        self._spreads = dict()
        self._groups = dict()
        self._affiliations = dict()

    def _add_external_ids(self, entity, id_dict):
        """Common external ID operations."""
        entity.affect_external_id(self.source_system, *id_dict.keys())
        for id_type in id_dict.keys():
            if id_type is None:
                raise ABCErrorInData(
                    "None not allowed as type: '{}'".format(id_type))
            elif id_dict[id_type] is None:
                raise ABCErrorInData(
                    "None not alowed as a value: '{}': '{}'"
                        .format(id_type, id_dict[id_type]))
            entity.populate_external_id(self.source_system,
                                        id_type,
                                        id_dict[id_type])
        # Remove external IDs not seen in the ABC file but present in the
        # database with source_system equal to ours.
        # New entities have no entity_id but have no depricated ext IDs either.
        if hasattr(entity, 'entity_id'):
            for row in entity.get_external_id(
                    source_system=self.source_system):
                id_type = row['id_type']
                if id_type not in id_dict.keys():
                    entity._delete_external_id(self.source_system, id_type)
                    self.logger.info(
                        "Entity: '%d' removed external ID type '%s'." %
                        (entity.entity_id, id_type))

    def _process_tags(self, entity, tag_dict):
        """Process an entity's tags."""
        for tag_type in tag_dict.keys():
            if tag_type is None:
                raise ABCErrorInData(
                    "None not allowed as type: '{}'".format(tag_type))
            elif tag_dict[tag_type] is None:
                raise ABCErrorInData(
                    "None not alowed as a value: '{}': '{}'"
                        .format(tag_type, tag_dict[tag_type]))
            # Add other actions to the following list if general events.
            # Otherwise override through Mixin
            if tag_type == "ADD_SPREAD":
                for spread in tag_dict[tag_type]:
                    if not entity.has_spread(spread):
                        entity.add_spread(spread)
                        self.logger.info("Entity: '%d' got spread '%s'." %
                                         (entity.entity_id, spread))
                    self._spreads.setdefault(entity.entity_id,
                                             []).append(spread)
            else:
                raise ABCErrorInData(
                    "Type: '{}' is not known in _process_tags()"
                        .format(tag_type))

    def _check_entity(self, entity, data_entity):
        """Check for conflicting entities or return found or None."""
        entities = list()
        for id_type in data_entity._ids.keys():
            lst = entity.search_external_ids(
                id_type=id_type,
                external_id=data_entity._ids[id_type],
                fetchall=False)
            for row in lst:
                entities.append(row['entity_id'])
        entity_id = None
        for id in entities:
            if entity_id != id and entity_id is not None:
                # There are entities out there with our IDs.
                # Fat error and exit
                ou = Factory.get('OU')(self.db)
                ou.find(id)
                found = ou.get_external_id(id_type=id_type)
                raise ABCMultipleEntitiesExistsError(
                    "found: '{}', current: '{}'".format(found, data_entity))
            entity_id = id

        if entity_id:
            # We found one
            return entity_id
        else:
            # Noone in the database could be found with our IDs.
            # This is fine, write_db() figures it up.
            return None

    def _add_entity_addresses(self, entity, addresses):
        """Add an entity's addresses."""
        for addr in addresses.keys():
            entity.populate_address(self.source_system, type=addr,
                                    address_text=addresses[addr].street,
                                    p_o_box=addresses[addr].pobox,
                                    postal_number=addresses[addr].postcode,
                                    city=addresses[addr].city)

    def _add_entity_contact_info(self, entity, contact_info):
        """Add contact info for an entity."""
        for cont in contact_info.keys():
            if cont in getattr(abcconf, 'WITH_PHONE_FILTER', ()):
                contact_info[cont] = self._filter_phone_number(
                    contact_info[cont])
            entity.populate_contact_info(self.source_system, type=cont,
                                         value=contact_info[cont])

    def _filter_phone_number(self, number):
        """Filter a phone number to follow a more correct format, if wrong."""
        if len(number) > 8 and not number.startswith('+'):
            number = "+%s" % number
        return number

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

        self._ou.populate()
        self._ou.write_db()

        # Handle names
        for type, name in ou.ou_names.items():
            self._ou.add_name_with_language(name_variant=type,
                                            name_language=self.co.language_nb,
                                            name=name)
        self._process_tags(self._ou, ou._tags)
        self._add_external_ids(self._ou, ou._ids)
        self._add_entity_addresses(self._ou, ou._address)
        self._add_entity_contact_info(self._ou, ou._contacts)
        return self._ou.write_db(), self._ou.entity_id

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
        # This is fine, write_db() figures it out.

        if person.birth_date is None:
            raise ABCErrorInData("No birthdate for person: {}."
                                 .format(person._ids))

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
        self._process_tags(self._person, person._tags)
        self._add_entity_addresses(self._person, person._address)
        self._add_entity_contact_info(self._person, person._contacts)
        ret = self._person.write_db()
        return ret

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
        self._add_external_ids(self._group, group._ids)
        ret = self._group.write_db()
        self._process_tags(self._group, group._tags)
        self._group.populate_trait(self.co.trait_group_imported,
                                   date=DateTime.now())
        self._group.write_db()
        # Add group to "seen" cache.
        self._groups.setdefault(group.name, [])
        return ret

    def _add_group_cache(self, group, member):
        if group in self._groups:
            if member not in self._groups[group]:
                self._groups[group].append(member)
        else:
            self.logger.warning("Group '%s' is not in the file." % group)

    def add_group_member(self, group, entity_type, member):
        """Add an entity to a group."""
        self._group.clear()
        self._group.find_by_name(group[1])
        if entity_type == "person":
            self._person.clear()
            self._person.find_by_external_id(member[0], member[1])

            if not self._group.has_member(self._person.entity_id):
                self._group.add_member(self._person.entity_id)
            self._add_group_cache(group[1], self._person.entity_id)
            return self._group.write_db()

    def add_person_affiliation(self, ou, person, affiliation, status):
        """Add an affiliation for a person."""
        self._person.clear()
        try:
            self._person.find_by_external_id(person[0], person[1])
        except Errors.NotFoundError:
            raise ABCErrorInData("no person with id: {}, {}"
                                 .format(person[0], person[1]))
        if self._ou is None:
            self._ou = Factory.get("OU")(self.db)
        self._ou.clear()
        self._ou.find_by_external_id(ou[0], ou[1])
        self._person.add_affiliation(self._ou.entity_id, affiliation,
                                     self.source_system, status)
        ret = self._person.write_db()

        # Submit affiliation data to the cache.
        self._affiliations.setdefault(self._person.entity_id, [])
        self._affiliations[self._person.entity_id].append((affiliation,
                                                           self._ou.entity_id))
        return ret

    def _post_process_tags(self):
        """Process possible after-effects of tags. This may include removing
        spreads, roles and such.

        Currently only spreads are supported."""
        # Do nothing if the config doesn't have TAG_REWRITE or it's empty.
        # In the latter case you get very serious side-effects that will wipe
        # all spreads on all entities due to entity.list_all_with_spread()'s
        # way of handling an empty argument.
        if not hasattr(abcconf, "TAG_REWRITE") or not abcconf.TAG_REWRITE:
            return
        # Access Entity objects directly.
        from Cerebrum.Entity import EntitySpread
        es = EntitySpread(self.db)
        for row in es.list_all_with_spread(
                [int(s) for s in abcconf.TAG_REWRITE.values()]):
            if int(row['entity_id']) in self._spreads:
                # Entity found, check spreads in database
                if (not int(row['spread']) in
                        self._spreads[int(row['entity_id'])]):
                    es.clear()
                    es.find(int(row['entity_id']))
                    es.delete_spread(int(row['spread']))
                    self.logger.info("Entity: '%d', removed spread '%s'" %
                                     (es.entity_id, int(row['spread'])))
            else:
                # Entity missing from file, remove all spreads
                es.clear()
                es.find(int(row['entity_id']))
                es.delete_spread(int(row['spread']))
                self.logger.info("Entity: '%d', removed spread '%s'" %
                                 (es.entity_id, int(row['spread'])))

    def _update_groups(self):
        """Run through the cache and remove people's group membership if it hasn't
        been seen in this push."""
        if self._group is None:
            self._group = Factory.get("Group")(self.db)
        self._group.clear()
        for grp in self._groups.keys():
            self._group.clear()
            self._group.find_by_name(grp)

            for member in self._group.search_members(
                    group_id=self._group.entity_id):
                member_id = int(member["member_id"])
                if member_id not in self._groups[grp]:
                    self._group.remove_member(member_id)
                    self.logger.debug("'%s' removed '%s'", grp, member_id)
            self._group.write_db()
        # Get group names
        group_names = dict()
        for row in self._group.list_names(self.co.group_namespace):
            group_names[int(row['entity_id'])] = row['entity_name']
        # See which groups are gone from the file and remove them from the
        # database if the cache doesn't have them.
        for row in self._group.list_traits(self.co.trait_group_imported):
            name = group_names[int(row['entity_id'])]
            if name not in self._groups:
                self._group.clear()
                self._group.find_by_name(name)
                if self._group.get_extensions():
                    self.logger.warning(
                        "Unable to delete group '%s' because it's a %r group",
                        name, self._group.get_extensions())
                else:
                    self._group.delete()
                    self.logger.info(
                        "Group '%s' deleted as it is no longer in file.", name)

    def _update_person_affiliations(self):
        """Run through the cache and remove people's affiliation if it hasn't
        been seen in this push."""
        for row in self._person.list_affiliations(
                source_system=self.source_system):
            p_id = int(row['person_id'])
            aff = row['affiliation']
            ou_id = row['ou_id']
            # If we find an entry both in the database and the cache, continue
            if (p_id in self._affiliations and
                    (aff, ou_id) in self._affiliations[p_id]):
                continue

            if (not hasattr(self._person, "entity_id") or
                    not self._person.entity_id == p_id):
                self._person.clear()
                self._person.find(p_id)
            self._person.delete_affiliation(ou_id, aff, self.source_system)
            self.logger.info(
                "Person '%d', removed affiliation '%d' from ou '%d'" %
                (p_id, aff, ou_id))

    def commit(self):
        """Do some cleanups and call db.commit()"""
        # TODO:
        # - Diff OUs as well.

        # Process the cache before calling commit.
        self._post_process_tags()
        self._update_groups()
        # Update affiliations for people
        self._update_person_affiliations()
        self.db.commit()

    def rollback(self):
        # Process the cache before calling commit.
        self._post_process_tags()
        self._update_groups()
        # Update affiliations for people
        self._update_person_affiliations()
        self.db.rollback()
