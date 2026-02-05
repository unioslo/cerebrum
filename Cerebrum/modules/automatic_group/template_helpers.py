# coding: utf-8
#
# Copyright 2020-2026 University of Oslo, Norway
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
Utilities for building group hierarchies based on org trees.

Example use:
::

    class FooGroups(AutomaticGroupCache):
        '''
        Define a group template + naming and spread rules
        '''

        template = GroupTypeTemplate(
            group_type="internal-group",
            group_visibility="I",
            conflict=GroupTypeTemplate.CONFLICT_UPDATE,
        )
        prefix = "foo-"
        description_fmt = "Foo-group {}"
        required_spreads = frozenset(("group@ldap",))

    # Use as a cache
    my_foo_groups = FooGroups(db)
    foo_bar = my_foo_groups.get_group("bar")

    # Look up all current groups
    foo_groups = FooGroups.list_groups(db)

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

from Cerebrum.Constants import _SpreadCode
from Cerebrum.Utils import Factory
from Cerebrum.group.template import _get_group_type
from Cerebrum.group.template import GroupTypeTemplate
from Cerebrum.utils import reprutils

logger = logging.getLogger(__name__)


class DefaultSpreads(reprutils.ReprEvalMixin):
    """ A set of default spreads to an entity. """

    repr_module = False
    repr_args_attr = "spreads"

    @classmethod
    def lookup_spreads(cls, const, spread_values):
        """ get spread constants from a sequence of values. """
        for value in (spread_values or ()):
            yield const.get_constant(const.Spread, value)

    def __init__(self, spreads):
        spreads = tuple(spreads)
        for spread in spreads:
            if not isinstance(spread, _SpreadCode):
                raise ValueError("Invalid spread type: " + repr(spread))
        self.spreads = frozenset(spreads)
        if len(self.spreads) != len(spreads):
            raise ValueError("Duplicate spreads: " + repr(spreads))

        self.entity_type = None
        entity_types = set(s.entity_type for s in spreads)
        if len(entity_types) > 1:
            raise ValueError("Incompatible spread types: "
                             + repr(self.spreads))
        if len(entity_types) == 1:
            self.entity_type = entity_types.pop()

    def __call__(self, entity):
        """ Add missing default spreads to *entity*. """
        if not self.spreads:
            return
        if entity.entity_type != self.entity_type:
            raise ValueError("Incompatible entity: id=%d, type=%s "
                             "(expected type: %s)"
                             % (entity.entity_id, entity.entity_type,
                                self.entity_type))
        current_spreads = set(s['spread'] for s in entity.get_spread())
        to_add = sorted(self.spreads - current_spreads)
        if not to_add:
            return
        logger.info("Adding missing spreads to entity type=%s, id=%d: %s",
                    self.entity_type, entity.entity_id, repr(to_add))
        for spread in to_add:
            entity.add_spread(spread)


class AutomaticGroupRules(object):
    """
    A naming rule helper for automatic group type templates.

    Provides:

    1. Group name and description formatting
    2. Group lookup
    """
    template = None
    GroupTypeTemplate(
        group_type="internal-group",
        group_visibility="I",
        conflict=GroupTypeTemplate.CONFLICT_ERROR,
    )

    prefix = None
    suffix = None
    description_fmt = "automatic group {}"

    @classmethod
    def format_name(cls, ident):
        """ Format group name from identifier. """
        name = ident
        if cls.prefix:
            name = cls.prefix + name
        if cls.suffix:
            name = name + cls.suffix
        return name

    @classmethod
    def format_description(cls, ident):
        """ Format group description from identifier. """
        return cls.description_fmt.format(ident)

    @classmethod
    def assert_group(cls, db, ident):
        """ Make sure a minimal group exists for ident. """
        name = cls.format_name(ident)
        desc = cls.format_description(ident)
        return cls.template(db, name, desc)

    @classmethod
    def list_groups(cls, db, include_expired=False, **kwargs):
        """ Get the id of all groups managed by this manager. """
        for arg in ("name", "group_type", "filter_expired", "fetchall"):
            if arg in kwargs:
                raise TypeError("invalid search term: " + arg)
        gr = Factory.get("Group")(db)
        pattern = cls.format_name("*")
        if pattern == "*":
            pattern = None
        group_type = _get_group_type(gr.const, cls.template.group_type)
        return set(
            r['group_id']
            for r in gr.search(
                name=pattern,
                group_type=group_type,
                filter_expired=not include_expired,
                fetchall=False,
                **kwargs
            )
        )


class AutomaticGroupCache(AutomaticGroupRules):
    """
    Automatic group cache, with default spread check + update for groups.
    """
    def __init__(self, db):
        if self.required_spreads:
            default_spreads = DefaultSpreads.lookup_spreads(
                Factory.get("Constants")(db),
                self.required_spreads)
        else:
            default_spreads = []

        self.db = db
        self._cache = {}
        self.update_spreads = DefaultSpreads(default_spreads)

    def _get_group(self, ident):
        group = self.assert_group(self.db, ident)
        self.update_spreads(group)
        return group

    def get_group(self, ident):
        """ Make sure an up-to-date group exists for ident. """
        if ident in self._cache:
            group = self._cache[ident]
        else:
            group = self._cache[ident] = self._get_group(ident)
        return group
