#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2011, 2012 University of Oslo, Norway
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
This module handles all functionality related to 'roles' and 'atoms', as used
in Cfengine-configuration.
"""

from Cerebrum.Utils import Factory, prepare_string, argument_to_sql
from Cerebrum.Entity import EntityName

Entity_class = Factory.get("Entity")
class PolicyComponent(EntityName, Entity_class):
    """Base class for policy component, i.e. roles and atoms."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('component_name', 'description', 'foundation', 'create_date')

    def __init__(self, db):
        super(PolicyComponent, self).__init__(db)

    def clear(self):
        """Clear all data residing in this component instance."""
        self.__super.clear()
        self.clear_class(PolicyComponent)
        self.__updated = []

    def new(self, entity_type, component_name, description, foundation, create_date=None):
        """Insert a new policy component into the database.

        This will be called by subclasses in order to have the entity_type set
        appropriately."""
        # TODO: is this correct syntax? running self.populate() runs the
        # subclass' populate, which doesn't have entity_type as an argument
        PolicyComponent.populate(self, entity_type=entity_type, component_name=component_name,
                      description=description, foundation=foundation,
                      create_date=create_date)
        self.write_db()
        # TODO: why have find() here? find creates bugs here, and Group does not
        # have that. Don't know what's correct to do.
        #self.find(self.entity_id)

    def populate(self, entity_type, component_name, description, foundation,
                 create_date=None):
        """Populate a component instance's attributes."""
        Entity_class.populate(self, entity_type)
        # If __in_db is present, it must be True; calling populate on an
        # object where __in_db is present and False is very likely a
        # programming error.
        #
        # If __in_db is not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False

        self.entity_type = entity_type
        self.component_name = component_name
        self.description = description
        self.foundation = foundation
        if not self.__in_db or create_date is not None:
            self.create_date = create_date

    def write_db(self):
        """Write component instance to database.

        If this instance has a ``entity_id`` attribute (inherited from
        class Entity), this Component entity is already present in the
        Cerebrum database, and we'll use UPDATE to bring the instance
        in sync with the database.

        Otherwise, a new entity_id is generated and used to insert
        this object.
        """
        self.__super.write_db()
        if not self.__updated:
            return

        is_new = not self.__in_db

        if is_new:
            cols = [('entity_type', ':e_type'),
                    ('component_id', ':component_id'),
                    ('description', ':description'),
                    ('foundation', ':foundation'),]
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=hostpolicy_component] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                                    {'e_type': int(self.entity_type),
                                     'component_id': self.entity_id,
                                     'description': self.description,
                                     'foundation': self.foundation,
                                     # The create_date might not be included
                                     # in the binds, but it's safe to put it
                                     # here in any case. If it's not in binds,
                                     # it's not included from here.
                                     'create_date': self.create_date})
            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.const.hostpolicy_atom_create
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.const.hostpolicy_role_create
            else:
                raise RuntimeError('Unknown entity_type=%s for entity_id=%s' %
                                   (self.entity_type, self.entity_id))
            self._db.log_change(self.entity_id, event, None)
            self.add_entity_name(self.const.hostpolicy_component_namespace,
                                 self.component_name)
        else:
            cols = [('description', ':description'),
                    ('foundation', ':foundation'),]
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            self.execute("""
            UPDATE [:table schema=cerebrum name=hostpolicy_component]
            SET %(defs)s
            WHERE component_id=:component_id""" %
                    {'defs': ", ".join(["%s=%s" % x for x in cols])},
                    {'component_id': self.entity_id,
                     'description': self.description,
                     'foundation': self.foundation,
                     'create_date': self.create_date})
                   

            # TODO: check if any in __updated before do changes. no need to
            # log then either, except if update_entity_name doesn't do that

            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.const.hostpolicy_atom_mod
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.const.hostpolicy_role_mod
            else:
                raise RuntimeError('Unknown entity_type=%s for entity_id=%s' %
                                   (self.entity_type, self.entity_id))
            self._db.log_change(self.entity_id, event, None, change_params=binds)

            if 'component_name' in self.__updated:
                self.update_entity_name(self.const.hostpolicy_component_namespace,
                                        self.component_name)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        """Deletes this policy component from DB."""
        if self.__in_db:

            # TODO: might have to delete its relations?

            self.execute("""
            DELETE FROM [:table schema=cerebrum name=hostpolicy_component]
            WHERE component_id=:component_id""", 
                                        {'component_id': self.entity_id})
            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.const.hostpolicy_atom_delete
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.const.hostpolicy_role_delete
            else:
                raise RuntimeError("Unknown entity_type=%s for entity_id=%s" %
                                    (self.entity_type, self.entity_id))
            self._db.log_change(self.entity_id, event, None)
        self.__super.delete()

    def find(self, component_id):
        """Fill this component instance with data from the database."""
        self.__super.find(component_id)
        (self.description, self.foundation, self.create_date,
         self.component_name) = self.query_1(
            """SELECT 
                co.description, co.foundation, co.create_date, en.entity_name
            FROM
                [:table schema=cerebrum name=hostpolicy_component] co,
                [:table schema=cerebrum name=entity_name] en
            WHERE
                en.entity_id = co.component_id AND
                en.value_domain = :domain AND
                co.component_id = :component_id
            """, {'component_id': component_id,
                  'domain': self.const.hostpolicy_component_namespace,})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        # drop changes, since we got them from db:
        self.__updated = []

    def find_by_name(self, component_name):
        self.__super.find_by_name(component_name, self.const.hostpolicy_component_namespace)

    def list_hostpolicies(self):
        """List out all hostpolicies together with their dns owners."""
        # TODO: should functionality regarding dns owners be moved to DnsOwner?
        return self.query("""
            SELECT
                co.entity_type AS entity_type,
                hp.policy_id AS policy_id,
                hp.dns_owner_id AS dns_owner_id,
                en.entity_name AS dns_owner_name
            FROM
              [:table schema=cerebrum name=hostpolicy_component] co,
              [:table schema=cerebrum name=hostpolicy_host_policy] hp,
              [:table schema=cerebrum name=dns_owner] dnso,
              [:table schema=cerebrum name=entity_name] en
            WHERE 
              co.component_id = hp.policy_id AND
              hp.dns_owner_id = dnso.dns_owner_id AND
              en.entity_id = hp.dns_owner_id""")

    def search(self, entity_id=None, entity_type=None, description=None,
               foundation=None):
        """Search for components that satisfy given criteria.

        @type component_id: int or sequence of ints.
        @param component_id:
            Component ids to search for. If given, only the given components
            are returned.

        @type entity_type: int or sequence of ints.
        @param entity_type:
            If given, only components of the given type(s) are returned.

        @type description: basestring
        @param description:
            Filter the results by their description. May contain SQL wildcard
            characters.

        @type foundation: basestring
        @param foundation:
            Filter the results by their foundation variable. May contain SQL
            wildcard characters.

        @rtype: iterable db-rows
        @return:
            An iterable with db-rows with information about each component
            that matched the given criterias.
        """
        # TODO: add fetchall
        where = ['en.entity_id = co.component_id']
        binds = dict()

        if entity_type is not None:
            where.append(argument_to_sql(entity_type, 'co.entity_type',
                                         binds, int))
        if description is not None:
            where.append('(LOWER(co.description) LIKE :description)')
            binds['description'] = prepare_string(description)
        if foundation is not None:
            where.append('(LOWER(co.foundation) LIKE :foundation)')
            binds['foundation'] = prepare_string(foundation)
        return self.query("""
            SELECT DISTINCT co.entity_type AS entity_type,
                            co.component_id AS component_id,
                            co.description AS description,
                            co.foundation AS foundation,
                            co.create_date AS create_date,
                            en.entity_name AS name
            FROM 
              [:table schema=cerebrum name=hostpolicy_component] co,
              [:table schema=cerebrum name=entity_name] en
            WHERE
              %(where)s
            """ % {'where': ' AND '.join(where)}, binds)

class Role(PolicyComponent):
    def new(self, component_name, description, foundation, create_date=None):
        self.__super.new(self.const.entity_hostpolicy_role, component_name,
                     description, foundation, create_date)

    def populate(self, component_name, description, foundation,
                 create_date=None):
        self.__super.populate(self.const.entity_hostpolicy_role, component_name,
                              description, foundation, create_date)

    def search(self, *args, **kwargs):
        """Sarch for roles by different criterias."""
        return self.__super.search(entity_type=self.const.entity_hostpolicy_role,
                                   *args, **kwargs)

    def search_relations(self, source_id=None, target_id=None,
                         relationship_code=None):
        """Search for role relations by different criterias.

        @type source_id: int or sequence of ints
        @param source_id:
            If given, all relations that has the given components as source
            are returned.

        @type target_id: int or sequence of ints
        @param target_id:
            If given, all relations that has the given components as targets
            are returned.

        @type relationship_code: int or sequence of ints
        @param relationship_code:
            If given, only relations of the given type(s) are returned.

        @rtype: iterable with db-rows
        @return:
            An iterator with db-rows with data about each relationship.
        """
        binds = dict()
        where = []
        tables = ['[:table schema=cerebrum name=hostpolicy_component] co',
                  '[:table schema=cerebrum name=hostpolicy_relationship] re']

        if source_id is not None:
            where.append(argument_to_sql(source_id, 're.source_policy', binds, int))
        if target_id is not None:
            where.append(argument_to_sql(target_id, 're.target_policy', binds, int))
        if relationship_code is not None:
            tables.append('[:table schema=cerebrum name=hostpolicy_relationship_code] rc')
            where.append('(rc.code = co.relationship)')
            where.append(argument_to_sql(relationship_code, 're.relationship', binds, int))

        where_str = ''
        if where:
            where_str = 'WHERE ' + ' AND '.join(where)

        # TODO; should we include source and target names?
        return self.query("""
            SELECT DISTINCT co.entity_type AS entity_type,
                            co.component_id AS component_id
            FROM
                %(tables)s
            %(where)s
            """ % {'where': where_str, 'tables': ', '.join(tables)}, binds)

class Atom(PolicyComponent):
    def new(self, component_name, description, foundation, create_date=None):
        self.__super.new(self.const.entity_hostpolicy_atom, component_name,
                     description, foundation, create_date)

    def populate(self, component_name, description, foundation,
                 create_date=None):
        self.__super.populate(self.const.entity_hostpolicy_atom, component_name,
                              description, foundation, create_date)

    def search(self, *args, **kwargs):
        """Search for atoms by different criterias."""
        return self.__super.search(entity_type=self.const.entity_hostpolicy_atom,
                                   *args, **kwargs)

