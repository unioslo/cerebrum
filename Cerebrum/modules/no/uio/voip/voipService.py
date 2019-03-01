#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2010 University of Oslo, Norway
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

"""This module implements voip_service functionality for voip.

Each voip_address is either personal or non-personal. The latter category is
meant to cover situations like phones in elevators, meeting rooms, etc. These
'non-personal' locations are represented by voip_service in voip; so that a
voip_address is bound either to a person or to a voip_service entity.
"""

import cereconf

from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.Entity import EntityContactInfo
from Cerebrum.Utils import argument_to_sql





class VoipService(EntityTrait, EntityContactInfo):
    """voip_service interface.
    """

    __read_attr__ = ("__in_db",)
    __write_attr__ = ("description",
                      "service_type",
                      "ou_id")


    def clear(self):
        self.__super.clear()
        self.clear_class(VoipService)
        self.__updated = list()
    # end clear


    def populate(self, description, service_type, ou_id):
        """Create a new VoipService instance in memory.
        """
        EntityTrait.populate(self, self.const.entity_voip_service)

        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False

        self.description = description
        self.service_type = self.const.VoipServiceTypeCode(int(service_type))
        self.ou_id = int(ou_id)
    # end populate


    def write_db(self):
        """Synchronise the object in memory with the database."""

        self.__super.write_db()
        if not self.__updated:
            return

        is_new = not self.__in_db
        binds = {"entity_type": int(self.const.entity_voip_service),
                 "entity_id": int(self.entity_id),
                 "description": self.description,
                 "service_type": int(self.const.VoipServiceTypeCode(self.service_type)),
                 "ou_id": int(self.ou_id),}
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=voip_service]
            VALUES (:entity_type, :entity_id, :description,
                    :service_type, :ou_id)
            """, binds)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=voip_service]
            SET description = :description,
                service_type = :service_type,
                ou_id = :ou_id
            WHERE entity_id = :entity_id
            """, binds)

        del self.__in_db
        self.__in_db = True
        self.__updated = list()
        return is_new
    # end write_db



    def delete(self):
        """Remove a specified entry from the voip_service table."""

        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=voip_service]
            WHERE entity_id = :entity_id
            """, {"entity_id": int(self.entity_id)})

        self.__super.delete()
    # end delete


    
    def find(self, entity_id):
        """Locate VoipService by its entity_id."""

        self.__super.find(entity_id)

        (self.description,
         self.service_type,
         self.ou_id) = self.query_1("""
         SELECT description, service_type, ou_id
         FROM [:table schema=cerebrum name=voip_service]
         WHERE entity_id = :entity_id
         """, {"entity_id": int(self.entity_id)})
        self.__in_db = True
    # end find



    def search(self, entity_id=None, description=None, service_type=None,
               ou_id=None):
        """Search for voip_services matching the filtering criteria."""

        where = list()
        binds = dict()

        if entity_id is not None:
            where.append(argument_to_sql(description, "vs.entity_id", binds,
                                         int))
        if description is not None:
            where.append(argument_to_sql(description, "vs.description", binds))
        if service_type is not None:
            where.append(argument_to_sql(service_type, "vs.service_type",
                                         binds, int))
        if ou_id is not None:
            where.append(argument_to_sql(ou_id, "vs.ou_id", binds, int))
        if where:
            where = "WHERE " + " AND ".join(where)
        else:
            where = ""

        return self.query("""
        SELECT entity_id, description, service_type, ou_id
        FROM [:table schema=cerebrum name=voip_service] vs
        """ + where, binds)
    # end search

    

    def search_voip_service_by_description(self, description, exact_match=False):
        """Locate voip_service by its description.

        The match could be either exact, or approximate (default). In the
        latter case, a substring search on the description is performed. 
        """

        if exact_match:
            where = "description = :description"
            binds = {"description": description}
        else:
            where = "description LIKE :description"
            binds = {"description": "%" + description + "%"}

        return self.query("""
        SELECT entity_id, description, service_type, ou_id
        FROM [:table schema=cerebrum name=voip_service]
        WHERE """ + where, binds)
    # end search_voip_service_by_description
        
# end voipService
