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

# $Id$

"""
This module handles all functionality related to 'roles' and 'atoms', as used
in Cfengine-configuration.
"""

from Cerebrum.Utils import Factory, prepare_string
from Cerebrum.Entity import EntityName

__version__ = "$Revision$"
# $URL$
# $Source$

Entity_class = Factory.get("Entity")
class PolicyComponent(EntityName, Entity_class):
    """Base class for policy component, i.e. roles and atoms."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('entity_name', 'description', 'foundation', 'create_date')

    def __init__(self, db):
        super(PolicyComponent, self).__init__(db)

    def clear(self):
        """Clear all data residing in this component instance."""
        self.__super.clear()
        self.clear_class(PolicyComponent)
        self.__updated = []

    def new(self, entity_type, component_name, description, foundation, create_date=None):
        """Insert a new policy component into the database.

        This will be called by subclasses in order to have the
        entity_type set appropriately."""
        # TODO: is this correct syntax? running self.populate() runs the
        # subclass' populate, which doesn't have entity_type as an argument
        PolicyComponent.populate(self, entity_type=entity_type, component_name=component_name,
                      description=description, foundation=foundation,
                      create_date=create_date)
        self.write_db()
        self.find(self.entity_id)

    def populate(self, entity_type, component_name, description, foundation,
                 create_date=None):
        """Populate subnet instance's attributes."""
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
                    ('foundation', ':foundation'),
                    ('create_date', ':create_date'),]
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=hostpolicy_component] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                                    {'e_type': int(self.entity_type),
                                     'component_id': self.entity_id,
                                     'description': self.description,
                                     'foundation': self.foundation,
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
                    ('foundation', ':foundation',
                    ('create_date', ':create_date'))]
            binds = {'component_id': self.entity_id,
                     'description': self.description,
                     'foundation': self.foundation,
                     'create_date': self.create_date}
            self.execute("""
            UPDATE [:table schema=cerebrum name=hostpolicy_component]
            SET %(defs)s
            WHERE component_id=:component_id""" %
                    {'defs': ", ".join(["%s=%s" % x for x in cols])},
                    binds)

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
        # TODO
        pass

    def find_by_name(self, component_name):
        self.__super.find_by_name(component_name, self.const.hostpolicy_component_namespace)

    def search(self, entity_type=None, description=None, foundation=None):
        """Search for components that satisfy given criteria.

        Currently, no criteria can be given, hence all components are
        returned.
        """
        where = ['en.entity_id = co.component_id']

        if entity_type is not None:
            where.append('co.entity_type=:entity_type')
        if description is not None:
            description = prepare_string(description)
            where.append('LOWER(co.description) LIKE :description')
        if foundation is not None:
            foundation = prepare_string(foundation)
            where.append('LOWER(co.foundation) LIKE :foundation')
        return self.query(
            """SELECT DISTINCT co.entity_type AS entity_type,
                               co.component_id AS component_id,
                               co.description AS description,
                               co.foundation AS foundation,
                               co.create_date AS create_date,
                               en.entity_name AS entity_name
               FROM 
                 [:table schema=cerebrum name=hostpolicy_component] co,
                 [:table schema=cerebrum name=entity_name] en
               WHERE
                 %(where)s
            """ % {'where': ' AND '.join(where)}, {
                        'entity_type': int(entity_type),
                        'description': description,
                        'foundation': foundation,
            })

class Role(PolicyComponent):
    def new(self, component_name, description, foundation, create_date=None):
        self.__super.new(self.const.entity_hostpolicy_role, component_name,
                     description, foundation, create_date)

    def populate(self, component_name, description, foundation,
                 create_date=None):
        self.__super.populate(self.const.entity_hostpolicy_role, component_name,
                              description, foundation, create_date)

    # TODO: list or search?

class Atom(PolicyComponent):
    def new(self, component_name, description, foundation, create_date=None):
        self.__super.new(self.const.entity_hostpolicy_atom, component_name,
                     description, foundation, create_date)

    def populate(self, component_name, description, foundation,
                 create_date=None):
        self.__super.populate(self.const.entity_hostpolicy_atom, component_name,
                              description, foundation, create_date)

    def search(self, *args, **kwargs):
        """Sarch for atoms by different criterias.
        
        TODO: add criterias. All atoms are returned for now."""
        return self.__super.search(entity_type=self.const.entity_hostpolicy_atom,
                                   *args, **kwargs)

