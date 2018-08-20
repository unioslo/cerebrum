#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# Copyright 2009 University of Oslo, Norway
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


"""Non-unique entity names extension.

This file contains the API code for supporting non-unique entity
names. Inheriting the EntityNonUniqueName-mixin gives a class an API for
storing non-unique names associated with that particular
Entity. EntityNonUniqueName is similar to EntityName, with the notable
exception of name uniqueness (all EntityNames have to be unique within a given
domain; this requirement has been lifted for EntityNonUniqueName)
"""

import cerebrum_path
import cereconf

from Cerebrum.Entity import Entity
from Cerebrum.Errors import NoEntityAssociationError

from Cerebrum.Constants import Constants
from Cerebrum.Constants import _ChangeTypeCode as ChangeType





class EntityNUNameConstants(Constants):
    entity_nu_name_add = ChangeType(
        'entity_nu_name', 'add', 'add (non-unique) entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))

    entity_nu_name_mod = ChangeType(
        'entity_nu_name', 'mod', 'mod (non-unique) entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))

    entity_nu_name_del = ChangeType(
        'entity_nu_name', 'del', 'del (non-unique) entity_name for %(subject)s',
        ('domain=%(value_domain:domain)s, name=%(string:name)s',))
# end Constants



class EntityNonUniqueName(Entity):
    """Mixin class usable alongside Entity for entities with names.

    Unlike EntityName, this class allows non-unique names for the same
    domain. I.e. do NOT use it for storing things like POSIX usernames.

    IVR 2009-03-23 TBD: Human names should be migrated here.
    IVR 2009-03-23 TBD: This should be a part of core.
    IVR 2009-03-23 FIXME: Insert a check in __new__() that makes sure that
                   EntityName and EntityNonUniqueName cannot co-exist (does it
                   make sense?)
    """


    def delete(self):
        """Remove all non-unique names belonging to this entity from the db.

        If an entity with non-unique names is to be removed from Cerebrum, we
        have to clear all its non-unique names.
        """

        if self.entity_id is None:
            raise NoEntityAssociationError("Unable to determine which "
                                           "non-unique name to delete")

        for row in self.get_nu_names():
            self.delete_entity_nu_name(row["domain_code"])

        self.__super.delete()
    # end delete
        

    def get_nu_name(self, domain):
        """Search for a name within the specified domain for a given entity.

        @type domain: ValueDomainCode instance
        @param domain:
          Name domain where we look for a name for this entity.

        @rtype: basestring
        @return: 
          Name of self.entity_id within the specified domain, or raises an
          exception if no name is found.
        """
        
        return self.query_1("""
        SELECT entity_name FROM [:table schema=cerebrum name=entity_nonunique_name]
        WHERE entity_id=:e_id AND value_domain=:domain""",
                          {'e_id': self.entity_id,
                           'domain': int(domain)})
    # end get_nu_name


    def get_nu_names(self):
        """Locate all names belonging to a given entity.

        Much like get_names, except this method search for all names.
        """
        
        return self.query("""
        SELECT en.entity_name AS name, en.value_domain AS domain_code
        FROM [:table schema=cerebrum name=entity_nonunique_name] en
        WHERE en.entity_id=:e_id""",
                          {'e_id': self.entity_id})
    # end get_nu_names


    def add_entity_nu_name(self, domain, name):
        self._db.log_change(self.entity_id, self.clconst.entity_nu_name_add, None,
                            change_params={'domain': int(domain),
                                           'name': name})
        return self.execute("""
        INSERT INTO [:table schema=cerebrum name=entity_nonunique_name]
          (entity_id, value_domain, entity_name)
        VALUES (:e_id, :domain, :name)""", {'e_id': self.entity_id,
                                            'domain': int(domain),
                                            'name': name})
    # end add_entity_nu_name


    def delete_entity_nu_name(self, domain):
        self._db.log_change(self.entity_id, self.clconst.entity_nu_name_del, None,
                            change_params={'domain': int(domain),
                                           'name': self.get_name(int(domain))})
        return self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_nonunique_name]
        WHERE entity_id=:e_id AND value_domain=:domain""",
                            {'e_id': self.entity_id,
                             'domain': int(domain)})
    # end delete_entity_nu_name


    def update_entity_nu_name(self, domain, name):
        self._db.log_change(self.entity_id, self.clconst.entity_nu_name_mod, None,
                            change_params={'domain': int(domain),
                                           'name': name})
        if int(domain) in [int(self.const.ValueDomain(code_str))
                           for code_str in cereconf.NAME_DOMAINS_THAT_DENY_CHANGE]:
            raise self._db.IntegrityError("Name change illegal for the domain: %s"
                                          % domain)
        
        self.execute("""
        UPDATE [:table schema=cerebrum name=entity_nonunique_name]
        SET entity_name=:name
        WHERE entity_id=:e_id AND value_domain=:domain""",
                     {'e_id': self.entity_id,
                      'domain': int(domain),
                      'name': name})
    # end update_entity_nu_name
    

    def find_by_nu_name(self, name, value_domain):
        """Locate all entities with the specified name in the specified
        domain.

        Naturally, since MULTIPLE entities may match a specified name, this
        method always returns a sequence (as opposed to
        EntityName.find_by_name). 
        """
        
        return self.query("""
        SELECT entity_id, value_domain, entity_name
        FROM [:table schema=cerebrum name=entity_nonunique_name]
        WHERE value_domain=:value_domain and entity_name = :name""",
                            {'value_domain': int(value_domain),
                             'name': name})
    # end list_by_nu_name


    def list_nu_names(self, value_domain):
        return self.query("""
        SELECT entity_id, value_domain, entity_name
        FROM [:table schema=cerebrum name=entity_nonunique_name]
        WHERE value_domain=:value_domain""",
                          {'value_domain': int(value_domain)})
    # end list_nu_names
# end EntityNonUniqueName



