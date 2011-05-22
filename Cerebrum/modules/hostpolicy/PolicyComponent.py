#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2011 University of Oslo, Norway
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


from Cerebrum.Utils import Factory


"""
This module handles all functionality related to 'roles' and 'atoms',
as used in Cfengine-configuration.

"""

__version__ = "$Revision$"
# $URL$
# $Source$



Entity_class = Utils.Factory.get("Entity")
class PolicyComponent(EntityName, Entity_class):
    """Base class for policy component, i.e. roles and atoms."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('entity_name', 'description', 'foundation', 'date')


    def __init__(self, db):
        super(PolicyComponent, self).__init__(db)
        

    def clear(self):
        """Clear all data residing in this Role-instance."""
        super(PolicyComponent, self).clear()
        self.clear_class(PolicyComponent)
        self.__updated = []


    def new(self, entity_type, component_name, description, foundation, create_date=None):
        """Insert a new policy component into the database.

        This will be called by subclasses in order to have the
        entity_type set appropriately.

        """
        self.populate(entity_type, component_name, description, foundation, create_date=None)
        self.write_db()
        self.find(self.entity_id)


    def populate(self, entity_type, component_name, description,
                 foundation, create_date=None):
        """Populate subnet instance's attributes."""
        Entity.populate(self, entity_type)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False

        self.entity_type = entity_type
        self.component_name = component_name
        self.description = description
        self.foundation = foundation
        self.date = date


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
            # Only need to check for overlaps when subnet is being
            # added, since a subnet's ip-range is never changed.
            self.check_for_overlaps()

            cols = [('entity_type', ':e_type'),
                    ('component_id', ':component_id'),
                    ('component_name', ':component_name'),
                    ('description', ':description'),
                    ('foundation', ':foundation'),
                    ('create_date', ':create_date'),]
                    
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=dns_policy_component] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                                    {'e_type': int(self.entity_type),
                                     'component_id': self.entity_id,
                                     'description': self.description,
                                     'foundation': self.foundation,
                                     'create_date': self.create_date})
            if self.entity_type == self.const.entity_dns_atom:
                event = self.const.dns_atom_create
            else:
                event = self.const.dns_role_create
            self._db.log_change(self.entity_id, event, None)

            self.add_entity_name(self.const.dns_policy_namespace, self.component_name)
            
        else:
            cols = [('description', ':description'),
                    ('foundation', ':foundation',
                    ('create_date', ':create_date'))]
            binds = {'component_id': self.entity_id,
                     'description': self.description,
                     'foundation': self.foundation,
                     'create_date': self.create_date}
            self.execute("""
            UPDATE [:table schema=cerebrum name=dns_policy_component]
            SET %(defs)s
            WHERE component_id=:component_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols if x[0] <> 'component_id'])},
                         binds)

            if self.entity_type == self.const.entity_dns_atom:
                event = self.const.dns_atom_mod
            else:
                event = self.const.dns_role_mod
            self._db.log_change(self.entity_id, event, None, change_params=binds)

            if 'component_name' in self.__updated:
                self.update_entity_name(self.const.dns_policy_namespace,
                                        self.component_name)
        
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new


    def delete(self):
        """Deletes this policy component from DB.

        Called by subclasses who first have made sure the deletion has
        been logged.

        """
        if self.__in_db:
             self.execute("""
             DELETE FROM [:table schema=cerebrum name=dns_policy_component]
             WHERE component_id=:component_id""", {'component_id': self.entity_id})            
        self.__super.delete()


    def find(self, component_id):
        pass


    def find_by_name(self, component_name):
        self.__super.find_by_name(component_name, self.const.dns_policy_namespace)


    def search(self):
        """Search for components that satisfy given criteria.

        Currently, no criteria can be given, hence all components are
        returned.

        """
        return self.query(
            """SELECT entity_type, component_id, component_name,
                      description, foundation, create_date
               FROM [:table schema=cerebrum name=dns_configuration_component]""")



class Role(PolicyComponent):
    def new(self, component_name, description, foundation, create_date=None):
        self.__super.new(self.const.entity_dns_role, component_name,
                     description, foundation, create_date)


    def populate(self, component_name, description,
                 foundation, create_date=None):
        self.__super.populate(self.const.entity_dns_role, component_name,
                              description, foundation, create_date)
        

    def delete(self):
        """Deletes this role from the DB."""
        self._db.log_change(self.entity_id, const.dns_role_delete, None)
        self.__super.delete()



class Atom(PolicyComponent):
    def new(self, component_name, description, foundation, create_date=None):
        self.__super.new(self.const.entity_dns_atom, component_name,
                     description, foundation, create_date)


    def populate(self, component_name, description,
                 foundation, create_date=None):
        self.__super.populate(self.const.entity_dns_atom, component_name,
                              description, foundation, create_date)
        

    def delete(self):
        """Deletes this atom from the DB."""
        self._db.log_change(self.entity_id, const.dns_atom_delete, None)
        self.__super.delete()

