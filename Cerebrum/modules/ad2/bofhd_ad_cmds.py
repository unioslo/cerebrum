#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2016 University of Oslo, Norway
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

from mx import DateTime

import cereconf

from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.auth import BofhdAuth

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import Parameter, Command, \
                FormatSuggestion, EntityType, Id, Spread, SimpleString

from Cerebrum.modules.ad2.Entity import EntityADMixin

class AttributeType(Parameter):
    _type = 'AD-attribute-type'
    _help_ref = 'attr_type'

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
            'ad_attributetypes': 'List out all defined AD-attribute types',
            'ad_list_attributes': 'List all attributes related to given spread',
            'ad_info': 'Get AD-related information about an entity',
            'ad_set_attribute': 'Set a given AD-attribute for an entity',
            'ad_remove_attribute': 'Remove a given AD-attribute for an entity',
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
            fs=FormatSuggestion("%-14s %-8s %s", ('name', 'multi', 'desc'),
                                hdr="%-14s %-8s %s" % ('Name',
                                                       'Multival',
                                                       'Description')))
    def ad_attributetypes(self, operator):
        """List out all types of AD-attributes defined in Cerebrum."""
        return [{'name': str(c), 'multi': c.multivalued, 'desc': c.description}
                for c in self.const.fetch_constants(self.const.ADAttribute)]

    # ad_list_attributes
    all_commands['ad_list_attributes'] = Command(
            ("ad", "list_attributes"),
            AttributeType(optional=True), Spread(optional=True),
            fs=FormatSuggestion("%-20s %-20s %-20s %s", ('attr_type', 'spread',
                                                         'entity', 'value'),
                                hdr="%-20s %-20s %-20s %s" % ('Attribute',
                                                              'Spread',
                                                              'Entity',
                                                              'Value')),
            perm_filter='is_superuser') # TODO: fix BA!
    def ad_list_attributes(self, operator, attr_type=None, spread=None):
        """List all attributes, limited to given input."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only for superusers, for now")
        # TODO: check if operator has access to the entity

        atr = spr = None
        if attr_type:
            atr = self.const.ADAttribute(attr_type)
            try:
                int(atr)
            except Errors.NotFoundError:
                raise CerebrumError('Unknown AD-attribute type: %s' % attr_type)
        if spread:
            spr = self.const.Spread(spread)
            try:
                int(spr)
            except Errors.NotFoundError:
                raise CerebrumError('Unknown spread: %s' % spread)
        ent = EntityADMixin(self.db)
        return [{'attr_type': str(self.const.ADAttribute(row['attr_code'])),
                 'spread': str(self.const.Spread(row['spread_code'])),
                 'entity': self._get_entity_name(row['entity_id']),
                 'value': row['value']} for row in
                            ent.list_ad_attributes(spread=spr, attribute=atr)]

    # ad_info
    all_commands['ad_info'] = Command(
            ("ad", "info"),
            EntityType(), Id(),
            fs=FormatSuggestion([
                ('AD-id: %-12s %s', ('id_type', 'ad_id')),
                ('%-20s %-20s %s', ('spread', 'attr_type', 'attr_value'),
                 '%-20s %-20s %s' % ('Spread', 'Attribute', 'Value')),
                ]),
            perm_filter='is_superuser')
    def ad_info(self, operator, entity_type, id):
        """Return AD related information about a given entity."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only for superusers, for now")
        ent = self._get_entity(entity_type, id)
        # TODO: check if operator has access to the entity?
        ret = []
        for row in ent.list_external_ids(source_system=self.const.system_ad,
                                         entity_id=ent.entity_id):
            ret.append({'id_type': str(self.const.EntityExternalId(row['id_type'])),
                        'ad_id': row['external_id']})
        for row in ent.list_ad_attributes(entity_id=ent.entity_id):
            ret.append({'attr_type': str(self.const.ADAttribute(row['attr_code'])),
                        'spread': str(self.const.Spread(row['spread_code'])),
                        'attr_value': row['value']})
        return ret

    # ad_set_attribute
    all_commands['ad_set_attribute'] = Command(
            ("ad", "set_attribute"),
            EntityType(), Id(), AttributeType(), Spread(),
            SimpleString(help_ref='attr_value'),
            perm_filter='is_superuser') # TODO: fix BA!
    def ad_set_attribute(self, operator, entity_type, id, attr_type, spread,
                         value):
        """Set an attribute for a given entity."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only for superusers, for now")
        # TODO: check if operator has access to the entity
        ent = self._get_entity(entity_type, id)
        atr = self.const.ADAttribute(attr_type)
        try:
            int(atr)
        except Errors.NotFoundError:
            raise CerebrumError('Unknown AD-attribute type: %s' % attr_type)
        spr = self.const.Spread(spread)
        try:
            int(spr)
        except Errors.NotFoundError:
            raise CerebrumError('Unknown spread: %s' % spread)
        ent.set_ad_attribute(spread=spr, attribute=atr, value=value)
        ent.write_db()
        # Check if the spread and attribute is defined for an AD-sync. If not,
        # add a warning to the output.
        extra = ''
        config = getattr(cereconf, 'AD_SPREADS', None)
        if config:
            if spread not in config:
                extra = '\nWARNING: No AD-sync defined for spread: %s' % spread
            elif attr_type not in config[spread].get('attributes', ()):
                extra = '\nWARNING: AD-sync for %s does not know of: %s' % (
                                                              attr_type, spread)
        return "AD-attribute %s set for %s, limited to spread %s: %s%s" % (atr,
                        self._get_entity_name(ent.entity_id), spr, value, extra)

    # ad_remove_attribute
    all_commands['ad_remove_attribute'] = Command(
            ("ad", "remove_attribute"),
            EntityType(), Id(), AttributeType(), Spread(),
            perm_filter='is_superuser') # TODO: fix BA!
    def ad_remove_attribute(self, operator, entity_type, id, attr_type, spread):
        """Remove an AD-attribute for a given entity."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only for superusers, for now")
        # TODO: check if operator has access to the entity
        ent = self._get_entity(entity_type, id)
        atr = self.const.ADAttribute(attr_type)
        try:
            int(atr)
        except Errors.NotFoundError:
            raise CerebrumError('Unknown AD-attribute type: %s' % attr_type)
        spr = self.const.Spread(spread)
        try:
            int(spr)
        except Errors.NotFoundError:
            raise CerebrumError('Unknown spread: %s' % spread)
        ent.delete_ad_attribute(spread=spr, attribute=atr)
        ent.write_db()
        return "AD-attribute %s removed for %s, for spread %s" % (atr,
                                self._get_entity_name(ent.entity_id), spr)
