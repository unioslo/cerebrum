# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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
"""Commands for the bofh daemon regarding the AD module."""
import six

import cereconf

from Cerebrum import Errors
from Cerebrum.modules.ad2.Entity import EntityADMixin
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import (
    Command, EntityType, FormatSuggestion, Id, Parameter, SimpleString, Spread)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied


class AttributeType(Parameter):
    _type = 'AD-attribute-type'
    _help_ref = 'attr_type'


def _get_spread(co, value):
    """ Strict Spread(<value>) lookup. """
    # sigh, human2constant is broken.  we *should* always refer to constants
    # with their code string anyway though...
    # TODO: Generalize into a bofhd lookup util, we do this all the time
    try:
        const = co.Spread(value)
        int(const)
        return const
    except Errors.NotFoundError:
        raise CerebrumError('Unknown Spread: %r' % value)


def _get_attr(co, value):
    """ Strict ADAttribute(<value>) lookup. """
    try:
        const = co.ADAttribute(value)
        int(const)
        return const
    except Errors.NotFoundError:
        raise CerebrumError('Unknown AD-attribute type: %r' % value)


class BofhdExtension(BofhdCommandBase):
    """The BofhdExctension for AD related commands and functionality."""

    all_commands = {}
    parent_commands = False
    authz = BofhdAuth

    @classmethod
    def get_help_strings(cls):
        group_help = {
            'ad': "Commands for AD related functionality",
            }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'ad': {
                'ad_attributetypes':
                    'List out all defined AD-attribute types',
                'ad_list_attributes':
                    'List all attributes related to given spread',
                'ad_info':
                    'Get AD-related information about an entity',
                'ad_set_attribute':
                    'Set a given AD-attribute for an entity',
                'ad_remove_attribute':
                    'Remove a given AD-attribute for an entity',
                },
            }

        arg_help = {
            'attr_type':
                ['attr_type', 'Type of AD-attribute',
                 'See "ad attributetypes" for a list of defined types'],
            'attr_value':
                ['value', 'Value of AD-attribute',
                 'A string value for the AD-attribute'],
            'id':
                ['id', 'Id',
                 'The identity of an entity'],
            'spread':
                ['spread', 'Spread',
                 'The spread for the attribute'],
            }
        return (group_help, command_help, arg_help)

    # ad_attributetypes
    all_commands['ad_attributetypes'] = Command(
        ("ad", "attributetypes"),
        fs=FormatSuggestion(
            "%-14s %-8s %s", ('name', 'multi', 'desc'),
            hdr="%-14s %-8s %s" % ('Name', 'Multival', 'Description')
        )
    )

    def ad_attributetypes(self, operator):
        """List out all types of AD-attributes defined in Cerebrum."""
        return [
            {
                'name': six.text_type(c),
                'multi': c.multivalued,
                'desc': c.description,
            }
            for c in self.const.fetch_constants(self.const.ADAttribute)
        ]

    #
    # ad_list_attributes
    #
    all_commands['ad_list_attributes'] = Command(
        ("ad", "list_attributes"),
        AttributeType(optional=True),
        Spread(optional=True),
        fs=FormatSuggestion(
            "%-20s %-20s %-20s %s", ('attr_type', 'spread', 'entity', 'value'),
            hdr="%-20s %-20s %-20s %s" % ('Attribute', 'Spread', 'Entity',
                                          'Value')
        ),
        perm_filter='is_superuser'
    )  # TODO: fix BA!

    def ad_list_attributes(self, operator, attr_type=None, spread=None):
        """List all attributes, limited to given input."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only for superusers, for now")
        # TODO: check if operator has access to the entity

        atr = spr = None
        if attr_type:
            atr = _get_attr(self.const, attr_type)
        if spread:
            spr = _get_spread(self.const, spread)

        ent = EntityADMixin(self.db)
        return [
            {
                'attr_type': six.text_type(
                    self.const.ADAttribute(row['attr_code'])),
                'spread': six.text_type(
                    self.const.Spread(row['spread_code'])),
                'entity': self._get_entity_name(row['entity_id']),
                'value': row['value'],
            }
            for row in ent.list_ad_attributes(spread=spr, attribute=atr)
        ]

    #
    # ad_info
    #
    all_commands['ad_info'] = Command(
        ("ad", "info"),
        EntityType(),
        Id(),
        fs=FormatSuggestion([
            ('AD-id: %-12s %s', ('id_type', 'ad_id')),
            ('%-20s %-20s %s', ('spread', 'attr_type', 'attr_value'),
             '%-20s %-20s %s' % ('Spread', 'Attribute', 'Value')),
        ]),
        perm_filter='is_superuser'
    )

    def ad_info(self, operator, entity_type, ident):
        """Return AD related information about a given entity."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only for superusers, for now")
        ent = self._get_entity(entity_type, ident)
        # TODO: check if operator has access to the entity?
        ret = []
        for row in ent.list_external_ids(
                source_system=self.const.system_ad,
                entity_id=ent.entity_id):
            ret.append({
                'id_type': six.text_type(
                    self.const.EntityExternalId(row['id_type'])),
                'ad_id': row['external_id'],
            })
        for row in ent.list_ad_attributes(entity_id=ent.entity_id):
            ret.append({
                'attr_type': six.text_type(
                    self.const.ADAttribute(row['attr_code'])),
                'spread': six.text_type(
                    self.const.Spread(row['spread_code'])),
                'attr_value': row['value'],
            })
        return ret

    #
    # ad_set_attribute <entity-type> <entity-id> <attr> <spread> <value>
    #
    all_commands['ad_set_attribute'] = Command(
        ("ad", "set_attribute"),
        EntityType(),
        Id(),
        AttributeType(),
        Spread(),
        SimpleString(help_ref='attr_value'),
        fs=FormatSuggestion([
            ("AD-attribute %s set for %s, limited to spread %s: %s",
             ('attribute', 'entity_name', 'spread', 'value')),
            ('WARNING: %s', ('warning', ))
        ]),
        perm_filter='is_superuser'
    )  # TODO: fix BA!

    def ad_set_attribute(self, operator,
                         entity_type, ident, attr_type, spread, value):
        """Set an attribute for a given entity."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only for superusers, for now")
        # TODO: check if operator has access to the entity
        ent = self._get_entity(entity_type, ident)
        atr = _get_attr(self.const, attr_type)
        spr = _get_spread(self.const, spread)
        ent.set_ad_attribute(spread=spr, attribute=atr, value=value)
        ent.write_db()

        # We keep using the constant strvals:
        spread = six.text_type(spr)
        attr_type = six.text_type(atr)

        # Check if the spread and attribute is defined for an AD-sync. If not,
        # add a warning to the output.

        retval = [{
            'attribute': attr_type,
            'entity_name': self._get_entity_name(ent.entity_id),
            'entity_type': six.text_type(ent.entity_type),
            'spread': spread,
            'value': value,
        }]

        config = getattr(cereconf, 'AD_SPREADS', None)
        if config:
            if spread not in config:
                retval.append({
                    'warning': 'No AD-sync defined for spread: %s' % spread,
                })
            elif attr_type not in config[spread].get('attributes', ()):
                retval.append({
                    'warning': 'AD-sync for %s does not know of: %s' % (
                        attr_type, spread),
                })

        return retval

    #
    # ad_remove_attribute <entity-type> <entity-id> <attr> <spread>
    #
    all_commands['ad_remove_attribute'] = Command(
        ("ad", "remove_attribute"),
        EntityType(),
        Id(),
        AttributeType(),
        Spread(),
        fs=FormatSuggestion(
            "AD-attribute %s removed for %s, for spread %s",
            ('attribute', 'entity_name', 'spread')
        ),
        perm_filter='is_superuser'
    )  # TODO: fix BA!

    def ad_remove_attribute(self, operator,
                            entity_type, id, attr_type, spread):
        """Remove an AD-attribute for a given entity."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only for superusers, for now")
        # TODO: check if operator has access to the entity
        ent = self._get_entity(entity_type, id)
        atr = _get_attr(self.const, attr_type)
        spr = _get_spread(self.const, spread)
        ent.delete_ad_attribute(spread=spr, attribute=atr)
        ent.write_db()

        return {
            'attribute': six.text_type(atr),
            'entity_name': self._get_entity_name(ent.entity_id),
            'entity_type': six.text_type(ent.entity_type),
            'spread': six.text_type(spr),
        }
