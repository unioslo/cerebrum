# -*- coding: iso-8859-1 -*-
# Copyright 2005-2006 University of Oslo, Norway
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
from Cerebrum.modules.CLConstants import _ChangeTypeCode
from Cerebrum import Errors
from Cerebrum.Utils import NotSet


class _EntityTraitCode(_CerebrumCodeWithEntityType):
    """Code values for entity traits, used in table entity_trait."""
    _lookup_table = '[:table schema=cerebrum name=entity_trait_code]'
    pass


class TraitConstants(Constants):
    trait_add = _ChangeTypeCode("trait", "add",
                                "new trait for %(subject)s",
                                ("%(trait:code)s",
                                 "numval=%(int:numval)s",
                                 "strval=%(str:strval)s",
                                 "date=%(str:date)s",
                                 "target=%(entity:target_id)s"))
    trait_del = _ChangeTypeCode("trait", "del",
                                "removed trait from %(subject)s",
                                ("%(trait:code)s",))
    trait_mod = _ChangeTypeCode("trait", "mod",
                                "modified trait for %(subject)s",
                                ("%(trait:code)s",
                                 "numval=%(int:numval)s",
                                 "strval=%(string:strval)s",
                                 "date=%(string:date)s",
                                 "target=%(entity:target_id)s"))

    # There are no mandatory EntityTraitCodes
    
    EntityTrait = _EntityTraitCode

class EntityTrait(Entity):
    """Mixin class which adds generic traits to an entity."""

    def clear(self):
        super(EntityTrait, self).clear()
        self.__traits = {}
        self.__trait_updates = {}

    def write_db(self):
        self.__super.write_db()

        def pickle_fixup(params):
            """pickle can't handle datetime objects"""
            if params.get('date'):
                params = params.copy()
                params['date'] = str(params['date'])
                return params

        for code in self.__trait_updates:
            params = pickle_fixup(self.__traits[code])
            if self.__trait_updates[code] == 'UPDATE':
                binds = ", ".join(["%s=:%s" % (c, c)
                                   for c in self.__traits[code]])
                self.execute("""
                UPDATE [:table schema=cerebrum name=entity_trait]
                SET %s
                WHERE entity_id = :entity_id AND code = :code
                """ % binds,
                             self.__traits[code])
                self._db.log_change(self.entity_id, self.const.trait_mod, None,
                                    change_params=params)
            else:
                binds = ", ".join([":%s" % c
                                   for c in self.__traits[code]])
                self.execute("""
                INSERT INTO [:table schema=cerebrum name=entity_trait]
                (%s) VALUES (%s)
                """ % (", ".join(self.__traits[code].keys()), binds),
                             self.__traits[code])
                self._db.log_change(self.entity_id, self.const.trait_add, None,
                                    change_params=params)
        self.__trait_updates = {}

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
        self._db.log_change(self.entity_id, self.const.trait_del, None)
        del self.__traits[code]

    def delete(self):
        """To delete this entity we need to remove all traits first.
        Traits which have this entity as target_id are left alone, and
        deletion will fail if any such trait exists.

        """
        for code in self.get_traits().copy():
            self.delete_trait(code)
        self.__super.delete()

    def populate_trait(self, code, target_id=None, date=None, numval=None,
                       strval=None):
        """Adds or updates an entity trait.  Returns 'INSERT' or
        'UPDATE'.

        """
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
        return self.__trait_updates[code]

    def get_traits(self):
        """Returns a dict of traits associated with the current entity
        keyed by the code constant.

        """
        if not self.__traits:
            for row in self.query("""
            SELECT entity_id, entity_type, code,
                   target_id, date, numval, strval
            FROM [:table schema=cerebrum name=entity_trait]
            WHERE entity_id=:entity_id
            """, {'entity_id': self.entity_id}):
                self.__traits[_EntityTraitCode(row['code'])] = row.dict()
        return self.__traits

    def get_trait(self, trait):
        """Return the trait value (as a dict), or None."""
        traits = self.get_traits()
        if traits is None:
            return None
        return traits.get(_EntityTraitCode(trait))

    def list_traits(self, code, target_id=NotSet, date=NotSet,
                    numval=NotSet, strval=NotSet, strval_like=NotSet,
                    fetchall=False):
        """Returns all the occurences of a specified trait, optionally
        filtered on values. To match SQL NULL, use None.  date should
        be an mx.DateTime object.  strval_like will apply DWIM case
        sensitivity (see Utils.prepare_sql_pattern).

        """
        # TBD: we may want additional filtering parameters, ie.
        # date_before, date_after, numval_lt and numval_gt.

        def add_cond(col, value, normalise=False):
            if value is None:
                conditions.append("%s IS NULL" % col)
            elif value is not NotSet:
                conditions.append("%s = :%s" % (col, col))
                if normalise:
                    value = normalise(value)
            return value

        conditions = ["code = :code"]
        code = int(code)

        add_cond("target_id", target_id)
        add_cond("date", date)
        numval = add_cond("numval", numval, normalise=int)
        if strval_like is not NotSet:
            expr, strval = self._db.sql_pattern('strval', strval_like)
            conditions.append(expr)
        else:
            # strval_like has precedence over strval
            strval = add_cond("strval", strval, normalise=str)
        where = " AND ".join(conditions)

        # Return everything but entity_type, which is implied by code
        return self.query("""
        SELECT entity_id, code, target_id, date, numval, strval
        FROM [:table schema=cerebrum name=entity_trait]
        WHERE """ + where, locals(), fetchall=fetchall)

# arch-tag: a834dc20-402d-11da-9b87-c30b16468bb4
