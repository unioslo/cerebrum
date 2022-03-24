# -*- coding: utf-8 -*-
#
# Copyright 2022 University of Oslo, Norway
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
from __future__ import absolute_import, print_function, unicode_literals

import logging
from operator import itemgetter

import six

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    Id,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.EntityTrait import EntityTrait


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
            ("    Target:    {} ({})", ("target_name", "target_type")),
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

        # TODO: We should use bofhd.parsers.ParamParser, but that could break
        #       existing use (no get_abbr_type(), ':'/'=' as separator, parsing
        #       'foo' as 'foo=')
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
                # TODO: _parse_date only handles dates, not hours etc.
                # TODO: Parse date returns in mx.DateTime - use
                #       .parsers.parse_datetime?
                params[key] = self._parse_date(value)
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
# Help texts
#

_trait_value_text_blurb = """
Enter the trait value as key=value.  'key' is one of:

- target_id    value is an entity, entered as type:name
- date         value is on format YYYY-MM-DD
- numval       value is an integer
- strval       value is a string

The key name may be abbreviated.  If value is left empty, the value
associated with key will be cleared.  Updating an existing trait will
blank all unnamed keys.
"""

HELP_GRP = {
    "trait": "Trait related commands",
}
HELP_CMD = {
    "trait": {
        "trait_info": "Display all traits associated with an entity",
        "trait_list": "List all entities which have specified trait",
        "trait_remove": "Remove a trait from an entity",
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
}
