# -*- coding: utf-8 -*-
# Copyright 2005-2009 University of Oslo, Norway
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
from Cerebrum.Constants import (_CerebrumCodeWithEntityType, Constants,
                                _get_code)
from Cerebrum.modules.CLConstants import _ChangeTypeCode
from Cerebrum import Errors
from Cerebrum.Utils import NotSet
try:
    set()
except:
    from Cerebrum.extlib.sets import Set as set

__version__ = "1.1"

class _EntityTraitCode(_CerebrumCodeWithEntityType):
    """Code values for entity traits, used in table entity_trait."""
    _lookup_table = '[:table schema=cerebrum name=entity_trait_code]'
    pass


class TraitConstants(Constants):
    trait_add = _ChangeTypeCode("trait", "add",
                                "new trait for %(subject)s",
                                ("%(trait:code)s",
                                 "numval=%(int:numval)s",
                                 "strval=%(string:strval)s",
                                 "date=%(string:date)s",
                                 "target=%(entity:target_id)s"))
    trait_del = _ChangeTypeCode("trait", "del",
                                "removed trait from %(subject)s",
                                ("%(trait:code)s",
                                 "numval=%(int:numval)s",
                                 "strval=%(string:strval)s",
                                 "date=%(string:date)s",
                                 "target=%(entity:target_id)s"))
    trait_mod = _ChangeTypeCode("trait", "mod",
                                "modified trait for %(subject)s",
                                ("%(trait:code)s",
                                 "numval=%(int:numval)s",
                                 "strval=%(string:strval)s",
                                 "date=%(string:date)s",
                                 "target=%(entity:target_id)s"))

    # There are no mandatory EntityTraitCodes

    EntityTrait = _EntityTraitCode


@_ChangeTypeCode.formatter('trait')
def format_cl_trait(co, val):
    return _get_code(co.EntityTrait, val, '<unknown>')

class EntityTrait(Entity):
    """Mixin class which adds generic traits to an entity."""

    def clear(self):
        super(EntityTrait, self).clear()
        self.__traits = {}
        self.__trait_updates = {}

    def _pickle_fixup(self, params):
        """pickle can't handle datetime objects"""
        if params.get('date'):
            params = params.copy()
            params['date'] = str(params['date'])
        return params


    def write_db(self):
        self.__super.write_db()

        for code in self.__trait_updates:
            params = self._pickle_fixup(self.__traits[code])
            if self.__trait_updates[code] == 'UPDATE':
                binds = ", ".join(["%s=:%s" % (c, c)
                                   for c in self.__traits[code]])
                # Find out if we are simply "touch"-ing a trait thus
                # updating its date. We shouldn't changelog such an event.
                #
                # Old trait is fished out of the database with a query. get_traits()
                # ignore the database when self.__traits is set (as it should).
                changelog = True
                try:
                    old_trait = self.query_1("""
                    SELECT *
                    FROM [:table schema=cerebrum name=entity_trait]
                    WHERE entity_id=:entity_id AND code=:code
                    """, {'entity_id': self.entity_id, 'code': int(code)})

                    changelog = False
                    for i in ('target_id', 'numval', 'strval'):
                        if old_trait.get(i) != self.__traits[code].get(i):
                            changelog = True
                except Errors.NotFoundError:
                    pass
                self.execute("""
                UPDATE [:table schema=cerebrum name=entity_trait]
                SET %s
                WHERE entity_id = :entity_id AND code = :code
                """ % binds,
                             self.__traits[code])
                if changelog:
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
        params = self._pickle_fixup(self.__traits[code])
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_trait]
        WHERE entity_id=:entity_id AND code=:code
        """, {'entity_id': self.entity_id, 'code': int(code)})
        self._db.log_change(self.entity_id, self.const.trait_del, None,
                            change_params=params)
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
                               'entity_type': int(self.entity_type),
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

    def list_traits(self, code=NotSet, target_id=NotSet, entity_id=NotSet,
                    date=NotSet, numval=NotSet, strval=NotSet,
                    strval_like=NotSet, return_name=False, fetchall=False):
        """Returns all the occurences of specified trait(s), optionally
        filtered on values.

        Multiple filters work akin to set intersection; i.e. specifying both
        code and target_id would constrait the result to those rows that match
        *both* code and trait_id. If a specified filter is a sequence, then
        any row matching any one of the values in that sequence will be
        returned. E.g. specifying code=(trait1, trait2) will result in rows
        that have either trait1 or trait2 in their code attribute.

        To match SQL NULL, use None.

        To ignore a column, use NotSet (by default all columns are ignored;
        i.e. *all* traits will be returned).

        code, target_id, strval may be sequences as well as scalars. date and
        strval_like, if specified, MUST be scalars. An empty sequence is
        equivalent to specifying None.

        @type code:
          1) NotSet OR 2) int/long/EntityTrait instance or a sequence thereof.
        @param code:
          Filter the result by specific trait(s).

        @type target_id:
          1) NotSet OR 2) int/long or a sequence thereof.
        @param target_id:
          Filter the result by specific target_id(s) associated with the trait.

        @type entity_id
          1) NotSet OR 2) int/long or a sequence thereof.
        @param entity_id
          Filter the result by specific entity_id(s) associated with the trait.

        @type date:
          1) NotSet OR 2) an mx.DateTime object.
        @param date:
          Filter the result by a specific date.

        @type numval:
          1) NotSet OR 2) int/long or a sequence thereof.
        @param numval:
          Filter the result by specific numval(s) associated with the trait.

        @type strval:
          1) NotSet OR 2) basestring or a sequence thereof.
        @param strval:
          Filter the result by specific strval(s) associated with the trait.

        @type strval_like:
          1) NotSet OR 2) basestring.
        @param strval_like:
          Filter the result by specific strval associated with the
          trait. strval_like will apply DWIM case sensitivity (see
          Utils.prepare_sql_pattern).

        @type return_name: bool
        @param return_name:
          Controls whether to return the entity name, if available, for
          entities that have traits.

        @type fetchall: bool
        @param fetchall:
          Controls whether to fetch all rows into memory at once.
        """
        # TBD: we may want additional filtering parameters, ie.
        # date_before, date_after, numval_lt and numval_gt.
        #
        # TBD: sequences for date may be desireable. For strval_like they
        # would be quite difficult to implement (SQL has no LIKE IN ()).

        # If value is a sequence, then normalise *MUST* be a callable.
        def add_cond(col, value, normalise=False):
            # if the value is a scalar and None -> NULL in SQL
            if value is None:
                conditions.append("%s IS NULL" % col)
            # else if the value is a sequence ...
            elif isinstance(value, (list, set, tuple)):
                # ... and the sequence is empty -> NULL in SQL
                if not value:
                    conditions.append("%s IS NULL" % col)
                # ... and the sequence has elements -> column IN (...) in SQL
                else:
                    # type(value) is to preserve the exact type of the
                    # sequence passed. TBD: As of python 2.4, we will not need
                    # the temporary list (the generator would do just fine)
                    value = type(value)([normalise(x) for x in value])
                    conditions.append("%s IN (%s)" %
                                      (col, ", ".join(map(str, value))))
            # else if the value is set to a scalar -> equality in SQL
            elif value is not NotSet:
                conditions.append("%s = :%s" % (col, col))
                if normalise:
                    value = normalise(value)

            # otherwise (i.e. NotSet) disregard the column.

            return value
        # end add_cond

        conditions = []
        code = add_cond("code", code, normalise=int)

        add_cond("entity_id", entity_id, normalise=int)
        add_cond("target_id", target_id, normalise=int)
        add_cond("date", date)
        numval = add_cond("numval", numval, normalise=int)
        if strval_like is not NotSet:
            expr, strval = self._db.sql_pattern('strval', strval_like)
            conditions.append(expr)
        else:
            # strval_like has precedence over strval
            strval = add_cond("strval", strval, normalise=str)
        attrs = join = ""
        if return_name:
            attrs += ", en.entity_name AS name"
            join += """
            LEFT JOIN [:table schema=cerebrum name=entity_name] en
              ON en.entity_id = t.entity_id"""
        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        return self.query("""
        SELECT t.entity_id, t.entity_type, t.code, t.target_id,
               t.date, t.numval, t.strval %s
        FROM [:table schema=cerebrum name=entity_trait] t
        %s
        %s""" % (attrs, join, where), locals(), fetchall=fetchall)
