# -*- coding: utf-8 -*-
#
# Copyright 2013-2025 University of Oslo, Norway
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
AD attribute commands for bofhd.

Configuration
=============

``cereconf.AD_SPREADS``
    Configuration for a given spread.  TODO: Is this used for anything other
    than generating warnings here?
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap
import six

import cereconf

from Cerebrum import Errors
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.cmd_param import (
    EntityType,
    FormatSuggestion,
    Id,
    Parameter,
)
from Cerebrum.modules.bofhd.errors import (
    CerebrumError,
    PermissionDenied,
)
from Cerebrum.modules.bofhd.help import merge_help_strings

from . import adattr_constants
from . import adattr_db


class AttributeType(Parameter):
    _type = 'AD-attribute-type'
    _help_ref = 'attr-name'


def _get_spread(co, value):
    """ helper - get spread from user input. """
    try:
        return co.get_constant(co.Spread, value)
    except Errors.NotFoundError:
        raise CerebrumError('Unknown Spread: %r' % value)


def _get_attr(co, value):
    """ helper - get attribute type from user input. """
    try:
        return co.get_constant(adattr_constants._ADAttrCode, value)
    except Errors.NotFoundError:
        raise CerebrumError('Unknown AD-attribute type: %r' % value)


class BofhdAdAttrAuth(BofhdAuth):
    """ Auth for ad * commands. """

    def _can_access_adattr(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("No access to ad attributes")

    can_list_ad_attrs = _can_access_adattr
    can_show_ad_attrs = _can_access_adattr
    can_set_ad_attr = _can_access_adattr
    can_remove_ad_attr = _can_access_adattr


class BofhdAdAttrCommands(BofhdCommandBase):
    """ Bofhd commands for managing ad attributes. """

    all_commands = {}
    parent_commands = False
    authz = BofhdAdAttrAuth

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            (HELP_GROUP, {}, {}),
            super(BofhdAdAttrCommands, cls).get_help_strings(),
            ({}, HELP_COMMANDS, HELP_ARGS),
        )

    #
    # ad attributetypes
    #
    all_commands['ad_attributetypes'] = cmd_param.Command(
        ("ad", "attributetypes"),
        fs=cmd_param.get_format_suggestion_table(
            ("name", "Name", 14, "s", True),
            ("multi", "Multival", 8, "s", True),
            ("desc", "Description", 50, "s", True),
        ),
    )

    def ad_attributetypes(self, operator):
        """ List available attributes. """
        return sorted(
            [
                {
                    'name': six.text_type(c),
                    'multi': c.multivalued,
                    'desc': c.description,
                }
                for c in self.const.fetch_constants(
                    adattr_constants._ADAttrCode)
            ],
            key=lambda d: d['name'],
        )

    #
    # ad list_attributes [attr-name] [attr-spread]
    #
    all_commands['ad_list_attributes'] = cmd_param.Command(
        ("ad", "list_attributes"),
        AttributeType(optional=True),
        cmd_param.Spread(help_ref="attr-spread", optional=True),
        fs=cmd_param.get_format_suggestion_table(
            ("attr_type", "Attribute", 20, "s", True),
            ("spread", "Spread", 20, "s", True),
            ("entity", "Entity", 20, "s", True),
            ("value", "Value", 20, "s", True),
        ),
        perm_filter="can_list_ad_attrs",
    )

    def ad_list_attributes(self, operator, _attr=None, _spread=None):
        """List all attributes, limited to given input."""
        self.ba.can_list_ad_attrs(operator.get_entity_id())

        attr = None if _attr is None else _get_attr(self.const, _attr)
        spread = None if _spread is None else _get_spread(self.const, _spread)

        spread_map = {
            int(c): six.text_type(c)
            for c in self.const.fetch_constants(self.const.Spread)
        }
        attr_map = {
            int(c): six.text_type(c)
            for c in self.const.fetch_constants(adattr_constants._ADAttrCode)
        }

        return [
            {
                'attr_type': attr_map[row['attr_code']],
                'spread': spread_map[row['spread_code']],
                'entity': self._get_entity_name(row['entity_id']),
                'value': row['value'],
            }
            for row in adattr_db.search_ad_attributes(self.db,
                                                      spread_code=spread,
                                                      attr_code=attr)
        ]

    #
    # ad_info - TODO: move this elsewhere?
    # Create a separate command to list attribtues for a given entity?
    # This commands is more closely related to the ad2 module.
    #
    all_commands['ad_info'] = cmd_param.Command(
        ("ad", "info"),
        EntityType(),
        Id(),
        fs=cmd_param.FormatSuggestion([
            ('AD id: %-12s %s', ('id_type', 'ad_id')),
            ('%-20s %-20s %s', ('spread', 'attr_type', 'attr_value'),
             '%-20s %-20s %s' % ('Spread', 'Attribute', 'Value')),
        ]),
        perm_filter="can_show_ad_attrs",
    )

    def ad_info(self, operator, entity_type, ident):
        """Return AD related information about a given entity."""
        self.ba.can_show_ad_attrs(operator.get_entity_id())

        ent = self._get_entity(entity_type, ident)

        # TODO: check if operator has access to the entity?
        ret = []
        for row in ent.search_external_ids(
                source_system=self.const.system_ad,
                entity_id=ent.entity_id, fetchall=False):
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
    # ad set_attribute <entity-type> <entity-id> <attr> <spread> <value>
    #
    all_commands['ad_set_attribute'] = cmd_param.Command(
        ("ad", "set_attribute"),
        cmd_param.EntityType(),
        cmd_param.Id(),
        AttributeType(),
        cmd_param.Spread(help_ref="attr-spread"),
        cmd_param.SimpleString(help_ref='attr-value'),
        fs=cmd_param.FormatSuggestion([
            ("Set attribute %s=%s for entity=%s @ spread=%s",
             ('attribute', 'value', 'entity_name', 'spread')),
            ('WARNING: %s', ('warning', ))
        ]),
        perm_filter="can_set_ad_attr",
    )

    def ad_set_attribute(self, operator,
                         entity_type, ident, _attr, _spread, value):
        """Set an attribute for a given entity."""
        ent = self._get_entity(entity_type, ident)
        attr = _get_attr(self.const, _attr)
        spread = _get_spread(self.const, _spread)

        self.ba.can_set_ad_attr(operator.get_entity_id())

        ent.set_ad_attribute(spread=spread, attribute=attr, value=value)

        retval = [{
            'attribute': six.text_type(attr),
            'entity_name': self._get_entity_name(ent.entity_id),
            'entity_type': six.text_type(ent.entity_type),
            'spread': six.text_type(spread),
            'value': value,
        }]

        # Check if the spread and attribute is defined for an AD-sync.
        # If not, add a warning to the output.
        config = getattr(cereconf, 'AD_SPREADS', None)
        if config:
            settings = config.get(six.text_type(spread))
            if settings is None:
                retval.append({
                    'warning': 'No AD-sync defined for spread: %s' % (spread,),
                })
            elif six.text_type(attr) not in settings.get("attributes", ()):
                retval.append({
                    'warning': ('AD-sync for %s does not know of: %s'
                                % (spread, attr)),
                })
        return retval

    #
    # ad remove_attribute <entity-type> <entity-id> <attr> <spread>
    #
    all_commands['ad_remove_attribute'] = cmd_param.Command(
        ("ad", "remove_attribute"),
        cmd_param.EntityType(),
        cmd_param.Id(),
        AttributeType(),
        cmd_param.Spread(help_ref="attr-spread"),
        fs=FormatSuggestion(
            "Removed attribute %s for entity=%s @ spread=%s",
            ('attribute', 'entity_name', 'spread')
        ),
        perm_filter="can_remove_ad_attr",
    )

    def ad_remove_attribute(self, operator,
                            entity_type, ident, _attr, _spread):
        """Remove an AD-attribute for a given entity."""
        ent = self._get_entity(entity_type, ident)
        attr = _get_attr(self.const, _attr)
        spread = _get_spread(self.const, _spread)

        self.ba.can_remove_ad_attr(operator.get_entity_id())

        try:
            ent.delete_ad_attribute(spread=spread, attribute=attr)
        except Errors.NotFoundError:
            raise CerebrumError(
                '%s does not have AD attribute %s with spread %s'
                % (ent.entity_id, six.text_type(attr), six.text_type(spread))
            )

        return {
            'attribute': six.text_type(attr),
            'entity_name': self._get_entity_name(ent.entity_id),
            'entity_type': six.text_type(ent.entity_type),
            'spread': six.text_type(spread),
        }


HELP_GROUP = {
    'ad': "Active Directory (AD) related commands",
}

HELP_COMMANDS = {
    'ad': {
        'ad_attributetypes': "List available AD attribute names",
        'ad_list_attributes': "List attribute values",
        'ad_info': "Show attributes for a given entity",
        'ad_set_attribute': "Set an AD attribute value",
        'ad_remove_attribute': "Remove an AD attribute value",
    },
}

HELP_ARGS = {
    'attr-name': [
        "attr-name",
        "Attribute name",
        textwrap.dedent(
            """
            Enter a valid attribute name.

            Only pre-defined attributes can be set.  See `ad attributetypes`
            for a list of defined attributes.
            """
        ).lstrip(),
    ],
    'attr-value': [
        "attr-value",
        "Attribute value",
        "Enter an attribute value.",
    ],
    'attr-spread': [
        "attr-spread",
        "Attribute spread",
        textwrap.dedent(
            """
            Enter a spread to set the attribute for.

            Active Directory (AD) attributes in Cerebrum are scoped to
            individual spreads.
            """
        ).lstrip(),

    ],
}
