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


from Cerebrum.Entity import Entity
from Cerebrum.Constants import _CerebrumCodeWithEntityType, Constants
from Cerebrum import Errors


class _EntityTraitCode(_CerebrumCodeWithEntityType):
    """Code values for entity traits, used in table entity_trait."""
    _lookup_table = '[:table schema=cerebrum name=entity_trait_code]'
    pass


class TraitConstants(Constants):
    EntityTrait = _EntityTraitCode


class EntityTrait(Entity):
    """Mixin class which adds generic traits to an entity."""

    def clear(self):
        super(EntityTrait, self).clear()
        self.__traits = {}
        self.__trait_updates = {}


    # TODO: Changelog support
    def write_db(self):
        super_return = self.__super.write_db()

        for code in self.__trait_updates:
            if self.__trait_updates[code] == 'UPDATE':
                binds = ", ".join(["%s=:%s" % (c, c)
                                   for c in self.__traits[code]])
                self.execute("""
                UPDATE [:table schema=cerebrum name=entity_trait]
                SET %s
                WHERE entity_id=:entity_id
                """ % binds,
                             self.__traits[code])
            else:
                binds = ", ".join([":%s" % c
                                   for c in self.__traits[code]])
                self.execute("""
                INSERT INTO [:table schema=cerebrum name=entity_trait]
                (%s) VALUES (%s)
                """ % (", ".join(self.__traits[code].keys()), binds),
                             self.__traits[code])
        self.__trait_updates = {}
        return super_return


    def delete_trait(self, code):
        """Remove the entity's trait identified by code value."""

        code = _EntityTraitCode(code)
        # get_traits populates __traits as a side effect
        if code not in self.get_traits():
            raise Errors.NotFoundError, code
        if code in self.__trait_updates:
            if self.__trait_updates[code] == 'INSERT':
                del self.__trait_updates[code]
                del self.__traits[code]
                return
            del self.__trait_updates[code]
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_trait]
        WHERE entity_id=:entity_id AND code=:code
        """, {'entity_id': self.entity_id, 'code': int(code)})
        del self.__traits[code]


    def populate_trait(self, code, target_id=None, date=None, numval=None,
                       strval=None):
        """Adds or updates an entity trait."""

        code = _EntityTraitCode(code)
        if code in self.get_traits():
            # If the trait is already listed in updates, it may be a
            # INSERT, so don't change it.
            if code not in self.__trait_updates:
                self.__trait_updates[code] = 'UPDATE'
        else:
            self.__trait_updates[code] = 'INSERT'
        self.__traits[code] = {'entity_id': self.entity_id,
                               'entity_type': self.entity_type,
                               'code': int(code),
                               'target_id': target_id,
                               'date': date,
                               'numval': numval,
                               'strval': strval}


    def get_traits(self):
        """Returns a dict of traits associated with the current entity
        keyed by the code constant."""

        if not self.__traits:
            for row in self.query("""
            SELECT entity_id, entity_type, code,
                   target_id, date, numval, strval
            FROM [:table schema=cerebrum name=entity_trait]
            WHERE entity_id=:entity_id
            """, {'entity_id': self.entity_id}):
                self.__traits[_EntityTraitCode(row['code'])] = row.dict()
        return self.__traits


    def list_traits(self, code):
        """Returns all the occurences of a specified trait."""

        # TODO: we probably want to allow filtering based on the
        # optional values, too.  Possibly using a lot of keyword
        # arguments:
        #
        #   target_id (exact match)
        #   date_before, date_after
        #   numval (exact match), numval_lt, numval_gt
        #   strval (exact match), strval_like

        return self.query("""
        SELECT entity_id, entity_type, code,
               target_id, date, numval, strval
        FROM [:table schema=cerebrum name=entity_trait]
        WHERE code=:code""", {'code': int(code)})

# arch-tag: a834dc20-402d-11da-9b87-c30b16468bb4
