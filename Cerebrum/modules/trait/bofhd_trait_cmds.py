# -*- coding: utf-8 -*-
#
# Copyright 2022-2023 University of Oslo, Norway
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
""" Trait-related bofhd commands. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
from operator import itemgetter

import six

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import parsers
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    Id,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.EntityTrait import EntityTrait
from Cerebrum.utils import date_compat

from . import trait_db
from .constants import _EntityTraitCode

logger = logging.getLogger(__name__)


class TraitAuth(BofhdAuth):
    """
    Common auth implementation for trait commands.

    .. note::
       This class should always be subclassed, so that any environment specific
       overrides takes effect (e.g. `is_superuser()`):

       - Subclass this class, mixin any custom authz classes (e.g.
         Cerebrum.modules.no.uio.bofhd_auth), and implement overrides if
         required.
       - Subclass the common command class, and set authz=<custom auth class>
       - Update bofhd config to use custom command class
    """

    def _has_trait_perm(self, operator, op_type, trait, entity_id, target_id):
        op_attr = six.text_type(trait) if trait else None
        return self._has_target_permissions(
                operator=operator,
                operation=op_type,
                target_type=self.const.auth_target_type_host,
                target_id=entity_id,
                victim_id=target_id,
                operation_attr=op_attr)

    def can_view_trait(self, operator, trait=None, ety=None,
                       target=None, query_run_any=False):
        """
        Check for access to see trait(s).

        Default is that operators can see their own person's and user's traits.

        :param trait: trait code
        :param ety: entity object (from the trait[entity_id])
        :param target: entity_id of the trait target (trait[target_id])

        Note: args are only required if checking a specific trait value.  This
        method can still be called as `can_view_traits(operator)`.
        """
        if query_run_any:
            return True

        if self.is_superuser(operator):
            return True

        if ety and ety.entity_id == operator:
            return True

        account = Factory.get('Account')(self._db)
        account.find(operator)
        if ety and ety.entity_id == account.owner_id:
            # TODO: should probably be limited to owner_type == person
            return True

        op_attr = six.text_type(trait) if trait else None
        if self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_view_trait,
                target_type=self.const.auth_target_type_host,
                target_id=int(ety.entity_id),
                victim_id=target,
                operation_attr=op_attr):
            return True
        raise PermissionDenied("Not allowed to see trait")

    def can_list_trait(self, operator, trait=None, query_run_any=False):
        """
        Check for access to list entities with a given trait.
        """
        # TODO: `trait` is never given - should it be removed?
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(operator,
                                              self.const.auth_list_trait):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to list traits")

    def can_set_trait(self, operator, trait=None, ety=None,
                      target=None, query_run_any=False):
        """
        Check for access to set trait.
        """
        # TODO: `target` is never used - should it be removed? or should it be
        #       used as victim_id?
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        op_attr = six.text_type(trait) if trait else None
        if trait and self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_set_trait,
                target_type=self.const.auth_target_type_host,
                target_id=int(ety.entity_id),
                # TODO: Shouldn't victim_id be target.entity_id or None?
                victim_id=int(ety.entity_id),
                operation_attr=op_attr):
            return True
        raise PermissionDenied("Not allowed to set trait")

    def can_remove_trait(self, operator, trait=None, ety=None,
                         target=None, query_run_any=False):
        """
        Check for access to remove trait.
        """
        # TODO: `target` is never used - should it be removed? or should it be
        #       used as victim_id?
        if query_run_any:
            return True
        if self.is_superuser(operator):
            return True
        op_attr = six.text_type(trait) if trait else None
        if trait and self._has_target_permissions(
                operator=operator,
                operation=self.const.auth_remove_trait,
                target_type=self.const.auth_target_type_host,
                target_id=int(ety.entity_id),
                # TODO: Shouldn't victim_id be target_id of the actual trait,
                #       if set?
                victim_id=int(ety.entity_id),
                operation_attr=op_attr):
            return True
        raise PermissionDenied("Not allowed to remove trait")

    def can_search_traits(self, operator, filters=None, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("No access to trait search")


class TraitCommands(BofhdCommonMethods):
    """
    Trait related commands.

    This module provides commands to inspect and modify traits on any entity
    that supports it.

    This class should always be subclassed, and use a custom authz with
    environment specific overrides for e.g. `is_superuser()`.
    """

    all_commands = {}
    parent_commands = False
    authz = TraitAuth

    def _search_traits(self, filter_d, limit=50):
        """
        Search for tasks.

        :param dict filter_d: task search params (see trait_search)
        :param int limit: max number of tasks to get
        :returns generator:
            Generates matching task dicts.

            If there are more than <limit> matching tasks, the list of
            results will be truncated, and a final sentinel item
            `{'limit': <limit>}` will be included.
        """
        # TODO: remap trait code to trait code strval
        trait_map = {
            int(c): six.text_type(c)
            for c in self.const.fetch_constants(_EntityTraitCode)
        }

        filter_d = dict(filter_d)
        filter_d['limit'] = limit + 1
        for i, row in enumerate(trait_db.search_traits(self.db, **filter_d)):
            if i < limit:
                # Note: trait 'date' is actually a naive datetime ('TIMESTAMP')
                _date = date_compat.get_datetime_naive(row['date'])
                trait_repr = ", ".join(
                    "{}={}".format(k, repr(v))
                    for k, v in (
                        ("date", _date.isoformat() if _date else None),
                        ("numval", row['numval']),
                        ("strval", row['strval']),
                        ("target_id", row['target_id']),
                    )
                    if v is not None
                )

                yield {
                    'code_int': row['code'],
                    'code_str': trait_map[row['code']],
                    'entity_id': row['entity_id'],
                    'target_id': row['target_id'],
                    'date': _date,
                    'numval': row['numval'],
                    'strval': row['strval'],
                    'trait_repr': trait_repr,
                }
            else:
                # if there are more than `limit` results, we add a
                # sentinel value to indicate that not all matches were
                # included.
                yield {'limit': limit}
                break

    _search_traits_list_fs = cmd_param.get_format_suggestion_table(
        ("entity_id", "Entity Id", 10, "d", False),
        ("code_str", "Trait", 18, "s", True),
        ("trait_repr", "Values", 50, "s", True),
        limit_key='limit',
    )

    #
    # trait search [filter...]
    #
    all_commands['trait_search'] = Command(
        ("trait", "search"),
        SimpleString(help_ref='trait-filter', optional=True, repeat=True),
        fs=_search_traits_list_fs,
        perm_filter="can_search_traits",
    )

    def trait_search(self, operator, *search_filters):
        """ Get traits given to an entity. """
        raw_filters = _trait_filter_parser.parse_items(search_filters)
        filters = _trait_filter_parser.map_params(self.db,
                                                  self.const, raw_filters)
        self.ba.can_search_traits(operator.get_entity_id(), filters)
        return list(self._search_traits(filters))

    #
    # trait info -- show trait values for an entity
    #
    all_commands['trait_info'] = Command(
        ("trait", "info"),
        Id(help_ref="id:target:account"),
        # Since the FormatSuggestion sorts by the type and not the order of the
        # return data, we send both a string to make it pretty in jbofh, and a
        # list to be used by brukerinfo, which is ignored by jbofh.
        fs=FormatSuggestion("%s", ('text',)),
        perm_filter="can_view_trait",
    )

    def trait_info(self, operator, ety_id):
        """ Get traits given to an entity. """
        ety = self.util.get_target(ety_id, restrict_to=[])
        self.ba.can_view_trait(operator.get_entity_id(), ety=ety)

        entity_name = self._get_name_from_object(ety)
        entity_type = self.const.EntityType(ety.entity_type)

        # Pre-formatted text templates
        text_head = [
            ("Entity:        {} ({})", ("entity_name", "entity_type")),
        ]
        text_vals = [
            ("  Trait:       {}", ("trait_name",)),
            ("    Numeric:   {:d}", ("numval",)),
            ("    String:    {}", ("strval",)),
            ("    Target:    {} ({})", ("target_name", "target_type")),
            ("    Date:      {}", ("date",)),
        ]

        def format_tpl(tpl, data):
            for fmt, keys in tpl:
                values = tuple(data.get(k) for k in keys)
                if all(v is None for v in values):
                    continue
                yield fmt.format(*values)

        text = []
        trait_items = []

        for trait, values in ety.get_traits().items():
            try:
                self.ba.can_view_trait(operator.get_entity_id(), trait=trait,
                                       ety=ety, target=values['target_id'])
            except PermissionDenied:
                continue

            # Structured data
            item = dict(values)
            item.update({
                'entity_name': entity_name,
                'entity_type': six.text_type(entity_type),
                'trait_name': six.text_type(trait),
            })
            if item['target_id']:
                target = self.util.get_target(int(values['target_id']))
                target_type = self.const.EntityType(target.entity_type)
                target_name = self._get_entity_name(target.entity_id,
                                                    target_type)
                item.update({
                    'target_name': target_name,
                    'target_type': six.text_type(target_type),
                })
            trait_items.append(item)
            text.extend(list(format_tpl(text_vals, item)))

        if text:
            data = trait_items[0]
            text = list(format_tpl(text_head, data)) + text

            return {
                'text': "\n".join(text),
                'traits': trait_items,
            }
        # TODO: Should `raise CerebrumError(msg)`, but that could break
        #       existing use
        return "%s has no traits" % entity_name

    #
    # trait list <trait> -- list all entities with a given trait
    #
    all_commands['trait_list'] = Command(
        ("trait", "list"),
        SimpleString(help_ref="trait"),
        fs=FormatSuggestion(
            "%-16s %-16s %s", ('trait', 'type', 'name'),
            hdr="%-16s %-16s %s" % ('Trait', 'Type', 'Name')
        ),
        perm_filter="can_list_trait",
    )

    def trait_list(self, operator, trait_name):
        """ List entities with a given trait. """
        trait = self._get_constant(self.const.EntityTrait, trait_name, "trait")
        self.ba.can_list_trait(operator.get_entity_id(), trait=trait)

        entity_type = self.const.EntityType(trait.entity_type)
        trait_db = EntityTrait(self.db)

        ret = []
        for row in trait_db.list_traits(trait):
            entity_id = row['entity_id']
            name = self._get_entity_name(entity_id, entity_type)

            ret.append({
                'id': int(entity_id),
                'trait': six.text_type(trait),
                'type': six.text_type(entity_type),
                'name': name,
            })
        ret.sort(key=itemgetter('name'))
        return ret

    #
    # trait remove <entity> <trait> -- remove trait from entity
    #
    all_commands['trait_remove'] = Command(
        ("trait", "remove"),
        Id(help_ref="id:target:account"),
        SimpleString(help_ref="trait"),
        perm_filter="can_remove_trait",
    )

    def trait_remove(self, operator, ety_id, trait_name):
        """ Remove a trait from an entity. """
        entity = self.util.get_target(ety_id, restrict_to=[])
        trait = self._get_constant(self.const.EntityTrait, trait_name, "trait")
        self.ba.can_remove_trait(operator.get_entity_id(),
                                 ety=entity, trait=trait)
        entity_name = self._get_name_from_object(entity)
        if entity.get_trait(trait) is None:
            # TODO: Should `raise CerebrumError(msg)`, but that could break
            #       existing use
            return "%s has no %s trait" % (entity_name, six.text_type(trait))
        entity.delete_trait(trait)
        # TODO: Should use FormatSuggestion, but that could break existing use
        return "OK, deleted trait %s from %s" % ((six.text_type(trait),
                                                  entity_name))

    #
    # trait set <entity> <trait> <field>=<value>... -- add or update a trait
    #
    all_commands['trait_set'] = Command(
        ("trait", "set"),
        Id(help_ref="id:target:account"),
        SimpleString(help_ref="trait"),
        SimpleString(help_ref="trait-value", repeat=True),
        perm_filter="can_set_trait",
    )

    def trait_set(self, operator, ident, trait_name, *values):
        entity = self.util.get_target(ident, restrict_to=[])
        trait = self._get_constant(self.const.EntityTrait, trait_name, "trait")
        self.ba.can_set_trait(operator.get_entity_id(),
                              trait=trait, ety=entity)
        entity_name = self._get_name_from_object(entity)

        # We should use bofhd.parsers.ParamParser, but that would break
        # existing use/syntax:
        #
        # - no abbreviation support (get_abbr_type)
        # - hard-coded ':' as separator (vs. current '=')
        # - empty values must include separator ('foo=', vs current 'foo')
        #
        params = {}
        for v in values:
            key, value = v.split('=', 1) if ('=' in v) else (v, '')
            key = self.util.get_abbr_type(key, ('target_id', 'date', 'numval',
                                                'strval'))
            if not value:
                params[key] = None
            elif key == 'target_id':
                target = self.util.get_target(value, restrict_to=[])
                params[key] = int(target.entity_id)
            elif key == 'date':
                # Optional is odd here, but it's how the old parser worked...
                params[key] = parsers.parse_datetime(value, optional=True)
            elif key == 'numval':
                params[key] = int(value)
            elif key == 'strval':
                # TODO: normalize text?
                params[key] = value

        entity.populate_trait(trait, **params)
        entity.write_db()
        # TODO: Should use FormatSuggestion, but that could break existing use
        return "Ok, set trait %s for %s" % (six.text_type(trait),
                                            entity_name or ident)

    #
    # trait types -- list out the defined trait types
    #
    # TODO: can_set_trait permission - why protect this command?
    #
    all_commands['trait_types'] = Command(
        ("trait", "types"),
        fs=FormatSuggestion(
            "%-25s %s", ('trait', 'description'),
            hdr="%-25s %s" % ('Trait', 'Description')
        ),
        perm_filter="can_set_trait",
    )

    def trait_types(self, operator):
        self.ba.can_set_trait(operator.get_entity_id())
        types = [
            {
                "trait": six.text_type(const),
                "description": const.description,
            }
            for const in self.const.fetch_constants(self.const.EntityTrait)
        ]
        return sorted(types, key=itemgetter('trait'))

    @classmethod
    def get_help_strings(cls):
        """ Help texts for trait commands. """
        # TODO: Consider listing traits and appending to HELP_ARG["trait"][2]?
        return merge_help_strings(get_help_strings(),
                                  (HELP_GRP, HELP_CMD, HELP_ARG))


#
# Trait params/input parsing
#


def _parse_required_text(value):
    if value:
        return value
    raise CerebrumError("value cannot be empty")


class TraitSearchParams(parsers.ParamsParser):
    """
    Parse trait search params from user input.

    This class can convert a sequence of strings like
    `("str:foo", "min:bar", "target:1234", "date:2022-01-21")`
    into a dict of search params for the `trait` module

    Typical use:
    ::

        # Example user input:

        search_filters = ["min:3", "before:now", "entity:account:foo",
                          "target:group:bar", "trait:trait-a", "trait:trait-b"]

        # Parse keyword arguments
        raw_filters = _trait_filter_parser.parse_items(search_filters)

        # Map trait codes and entity ids to intvals
        search_args = _trait_filter_parser.map_params(db, const, raw_filters)

        # Search
        results = trait_db.search_traits(db, **search_args)
    """

    fields = {
        'min': "Limit to traits with `numval >= <n>`",
        'max': "Limit to traits with `numval < <n>`",
        'before': "Limit to traits with `date < <datetime>`",
        'after': "Limit to traits with `date > <datetime>`",
        'text': "Limit to traits with a strval matching <ipattern>",
        'trait': "Limit to specific trait types",
        # 'entity': "Limit to traits for a a given <entity>",
        # 'target': "Limit to traits targetting a given <entity>",
    }
    params = {
        # Regular params - can be used directly with trait search
        'min': 'numval_min',
        'max': 'numval_max',
        'before': 'date_before',
        'after': 'date_after',
        'text': 'strval_ilike',

        # Typically needs to be translated using `map_params` before use:
        'trait': 'trait_lookup',
        # 'entity': 'entity_lookup',
        # 'target': 'target_lookup',

    }
    parsers = {
        'min': int,
        'max': int,
        'before': parsers.parse_datetime,
        'after': parsers.parse_datetime,
        'text': parsers.parse_ipattern,
        'trait': _parse_required_text,
        # 'entity': _parse_required_text,
        # 'target': _parse_required_text,
    }
    multivalued = set(('trait', 'entity', 'target'))

    @classmethod
    def translate_trait(cls, const, lookup):
        try:
            return const.get_constant(_EntityTraitCode, lookup)
        except LookupError:
            raise CerebrumError("invalid trait: " + repr(lookup))

    @classmethod
    def translate_entity(cls, db, lookup):
        # key, _, value = lookup.partition(":")
        raise NotImplementedError("entity lookup not supported yet")

    @classmethod
    def map_params(cls, db, const, params):
        params = dict(params)

        # Translate traits
        trait_lookup = params.pop('trait_lookup', None)
        if trait_lookup:
            params['code'] = [cls.translate_trait(const, t)
                              for t in trait_lookup]

        # Translate entity - not yet implemented
        entity_lookup = params.pop('entity_lookup', None)
        if entity_lookup:
            params['entity_id'] = [cls.translate_entity(db, v)
                                   for v in entity_lookup]

        target_lookup = params.pop('target_lookup', None)
        if target_lookup:
            params['target_id'] = [cls.translate_entity(db, v)
                                   for v in target_lookup]

        return params


_trait_filter_parser = TraitSearchParams()


#
# Help texts
#

_trait_value_text_blurb = """
Enter the trait value as key=value.  'key' is one of:

Valid trait params:

 - target_id    value is an <entity> (e.g. id:123, group:foo)
 - date         value is a <datetime> (e.g. 2023-02-20)
 - numval       value is an integer
 - strval       value is a string

Note: To include whitespace in values, the whole key=value expression must be
quoted: "key=hello world" (*not* key="hello world").  Updating an existing
trait will blank all unnamed keys.

Valid <datetime> values:

{datetime}

Valid <entity> values are any lookup string that works for other, generic
entity commands, e.g.:

 - id:123           look up any entity by its entity id
 - account:example  look up account by account name "example"
 - person:example   look up person by owned account name "example"
 - group:example    look up group by group name "example"
 - ou:102030        look up org-unit by location code "102030'

""".format(
    datetime=parsers.parse_datetime_help_blurb,
)

_trait_filter_text_blurb = """
Each trait-filter follows a format of <param>:<value>.

Example:  Find all traits with both a numval = 10 *and* a strval = "foo
bar".

    `trait search min:10 max:10 "text:foo bar"`

Valid filter <param> values
----------------------------
{filters}


Valid <datetime> values
-----------------------
{datetime}


Matching with <ipattern>
------------------------
{ipattern}


""".format(
    filters="\n".join(
        " - {}: {}".format(f, h)
        for f, h in _trait_filter_parser.get_help()
    ),
    # TODO: Add entity lookup blurb when implemented
    datetime=parsers.parse_datetime_help_blurb.strip(),
    ipattern=parsers.parse_ipattern_help_blurb.strip(),
)


HELP_GRP = {
    "trait": "Trait related commands",
}
HELP_CMD = {
    "trait": {
        "trait_info": "Display all traits associated with an entity",
        "trait_list": "List all entities which have specified trait",
        "trait_remove": "Remove a trait from an entity",
        "trait_search": "Search for given trait types or values",
        "trait_set": "Add or update an entity's trait.",
        "trait_types": "List all defined trait types (not all are editable)",
    },
}
HELP_ARG = {
    "trait": [
        "trait",
        "Name of trait",
        "Name of trait.  Use `trait types` to list all available traits.",
    ],
    "trait-value": [
        "trait-value",
        "Trait value",
        _trait_value_text_blurb,
    ],
    "trait-filter": [
        "trait-filter",
        "Trait filter",
        _trait_filter_text_blurb,
    ],
}
