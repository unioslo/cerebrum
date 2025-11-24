# -*- coding: utf-8 -*-
#
# Copyright 2005-2025 University of Oslo, Norway
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
Trait mixin for Cerebrum.Entity.

See :mod:`Cerebrum.modules.trait` for more info.

TODO
----
This module should be refactored to use :mod:`Cerebrum.modules.trait.trait_db`,
and moved to ``Cerebrum.modules.trait.trait_mixins``.

We may want to get rid of some old Cerebrum-isms here as well.  The trait
caching (per entity) doesn't really help much, as we still need to do an
expensive `Entity.find()` on every entity we want to update.  We could probably
get rid of the `populate_trait() + write_db()` pattern, and replace it with
`trait_db.set_trait` for most scenarios.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from Cerebrum import Errors
from Cerebrum.Constants import _ChangeTypeCode, _get_code
from Cerebrum.Entity import Entity
from Cerebrum.Utils import NotSet
from Cerebrum.modules.trait.constants import _EntityTraitCode
from Cerebrum.modules.trait import trait_db
from Cerebrum.utils import text_compat
from Cerebrum.utils.date_compat import get_datetime_naive


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
                # TODO: Figure out what to do with this - we *should* changelog
                # date changes as well.
                #
                # We should find all places where we actually update traits
                # with a new `date`, and check whether this is neccessary.  If
                # we want to update a date, it *should* be changelogged.  If we
                # just set a date for debugging, we should reconsider...
                assignments = ", ".join("%s=:%s" % (c, c)
                                        for c in self.__traits[code])
                changelog = True
                old_trait = trait_db.get_trait(self._db, self.entity_id, code)
                if old_trait:
                    changelog = False
                    for i in ('target_id', 'numval', 'strval'):
                        if old_trait[i] != self.__traits[code].get(i):
                            changelog = True
                self.execute(
                    """
                    UPDATE [:table schema=cerebrum name=entity_trait]
                    SET {}
                    WHERE entity_id = :entity_id AND code = :code
                    """.format(assignments),
                    self.__traits[code],
                )
                if changelog:
                    self._db.log_change(
                        self.entity_id,
                        self.clconst.trait_mod,
                        None,
                        change_params=params,
                    )
            else:
                values = self.__traits[code]
                trait_db.set_trait(self._db, **values)
        self.__trait_updates = {}

    def delete_trait(self, code):
        """Remove the entity's trait identified by code value."""
        code = _EntityTraitCode(code)
        # get_traits populates __traits as a side effect
        if code not in self.get_traits():
            raise Errors.NotFoundError(code)
        if code in self.__trait_updates:
            if self.__trait_updates[code] == 'INSERT':
                del self.__trait_updates[code]
                del self.__traits[code]
                return
            del self.__trait_updates[code]

        trait_db.clear_trait(self._db, self.entity_id, code)
        if code in self.__traits:
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
            for row in trait_db.search_traits(self._db,
                                              entity_id=int(self.entity_id)):
                row = dict(row)
                row['date'] = get_datetime_naive(row['date'])
                self.__traits[_EntityTraitCode(row['code'])] = row
        return self.__traits

    def get_trait(self, trait):
        """Return the trait value (as a dict), or None."""
        traits = self.get_traits()
        if traits is None:
            return None
        return traits.get(_EntityTraitCode(trait))

    def list_traits(self, code=NotSet, target_id=NotSet, entity_id=NotSet,
                    date=NotSet, numval=NotSet, strval=NotSet,
                    strval_like=NotSet, fetchall=False):
        """Returns all the occurrences of specified trait(s), optionally
        filtered on values.

        Multiple filters work akin to set intersection; i.e. specifying both
        code and target_id would constrain the result to those rows that match
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
          1) NotSet OR 2) int/EntityTrait instance or a sequence thereof.
        @param code:
          Filter the result by specific trait(s).

        @type target_id:
          1) NotSet OR 2) int or a sequence thereof.
        @param target_id:
          Filter the result by specific target_id(s) associated with the trait.

        @type entity_id
          1) NotSet OR 2) int or a sequence thereof.
        @param entity_id
          Filter the result by specific entity_id(s) associated with the trait.

        @type date:
          1) NotSet OR 2) an date/datetime/mx-like object.
        @param date:
          Filter the result by a specific date.

        @type numval:
          1) NotSet OR 2) int or a sequence thereof.
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

        @type fetchall: bool
        @param fetchall:
          Controls whether to fetch all rows into memory at once.
        """
        # This is a legacy search function with some truly odd behaviour:
        #
        # - Searching for an empty list turns into a `column IS NULL` criteria.
        #   In all other equivalent functions and methods, it turns into
        #   `column IN ()` - i.e. no match.
        #
        # - Searching for `None` results in a `IS NULL` check, even for values
        #    that cannot be `NULL`
        #
        # - Searching for a pattern ignores any `strval` given.  If the pattern
        #   is `None`, we force a `strval IS NULL` check, regardless of any
        #   value given as `strval` argument to this method.
        #
        # We should probably find all use of `EntityTrait.list_traits` and
        # replace it with `trait_db.search_traits`

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
            strval = add_cond("strval", strval, normalise=text_compat.to_text)
        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        return self.query("""
        SELECT t.entity_id, t.entity_type, t.code, t.target_id,
               t.date, t.numval, t.strval
        FROM [:table schema=cerebrum name=entity_trait] t
        %s""" % where, locals(), fetchall=fetchall)
