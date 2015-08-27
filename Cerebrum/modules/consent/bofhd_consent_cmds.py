#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 University of Oslo, Norway
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
""" This is a bofhd module for guest functionality.

The guest commands in this module creates guest accounts.

Guests created by these bofhd-commands are non-personal, owned by a group. A
trait associates the guest with an existing personal account.

TODO: More info
"""

from mx import DateTime

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.guest.bofhd_consent_auth import BofhdAuth

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (Parameter,
                                              Command,
                                              AccountName,
                                              Integer,
                                              GroupName,
                                              PersonName,
                                              FormatSuggestion)


class ConsentType(Parameter):
    _type = 'consent_type'
    _help_ref = 'consent_type'


def format_date(field):
    """ Date format for FormatSuggestion. """
    fmt = "yyyy-MM-dd"  # 10 characters wide
    return ":".join((field, "date", fmt))


class BofhdExtension(BofhdCommonMethods):
    """
    Consent related commands.
    """
    hidden_commands = {}  # Not accessible through bofh
    all_commands = {}

    def __init__(self, server):
        """
        """
        super(BofhdExtension, self).__init__(server)
        self.ba = BofhdAuth(self.db)

    def get_help_strings(self):
        """
        Help strings for our commands and arguments.
        """
        group_help = {'consent': 'Commands for handling consents', }
        command_help = {
            'consent': {
                'consent_create': 'Create / give a new consent',
                'consent_remove': 'Remove / deactivate a given consent',
                'consent_info': ('View consent information for '
                                 'a given account or person'),
                'consent_list': 'List all available types of consent'
            }
        }
        arg_help = {
            'consent_type': ['type', 'Enter consent type',
                             "'consent list' lists defined consents"],
        }
        return (group_help, command_help, arg_help)

    # consent create
    all_commands['consent_create'] = Command(
        ('consent', 'create'),
        ConsentType(),
        EntityType(default="account"),
        SimpleString(),
        perm_filter='can_create_consent')

    def consent_create(self,
                       operator,
                       consent_type,
                       entity_type,
                       search_value):
        """
        Create / activate consent
        """
        entity = self._get_entity(entity_type, search_value)
        self.ba.can_create_consent(operator.get_entity_id(), entity)
        pass  # TODO

    # consent remove
    all_commands['consent_remove'] = Command(
        ('consent', 'remove'),
        ConsentType(),
        EntityType(default="account"),
        SimpleString(),
        perm_filter='can_remove_consent')

    def consent_remove(self,
                       operator,
                       consent_type,
                       entity_type,
                       search_value):
        """
        Remove / deactivate consent
        """
        entity = self._get_entity(entity_type, search_value)
        self.ba.can_remove_consent(operator.get_entity_id(), entity)
        pass  # TODO

    # consent info
    all_commands['consent_info'] = Command(
        ('consent', 'info'),
        EntityType(default="account"),
        SimpleString(),
        fs=FormatSuggestion(
            '%-16s  %s',
            ('name', 'value'),
            hdr='%-15s %s' % ('Name', 'Value')),
        perm_filter='can_do_consent_info')

    def consent_info(self, operator, entity_type, search_value):
        """
        View consent information for a given account or person
        """
        entity = self._get_entity(entity_type, search_value)
        self.ba.can_do_consent_info(operator.get_entity_id(), entity)
        pass  # TODO

    # consent list
    all_commands['consent_list'] = Command(
        ('consent', 'list'),
        fs=FormatSuggestion(
            '%-16s  %1s  %s',
            ('name', 'default', 'desc'),
            hdr='%-15s %-4s %s' % ('Name', 'Default', 'Description')),
        perm_filter='can_list_consents')  # Do we really need this? TODO

    def consent_list(self, operator):
        """
        View consent information for a given account or person
        """
        self.ba.can_list_consents(operator.get_entity_id())
        ret = []
        pass  # TODO

    def _get_entity(self, entity_type, value=None):
        """
        """
        if not value:  # None, '', 0 ... etc.
            raise CerebrumError('Invalid value')
        if entity_type == 'account':
            return self._get_account(value)
        if entity_type == 'person':
            return self._get_person(*self._map_person_id(value))
        raise CerebrumError("Invalid entity type. "
                            "Entity type can be either 'account' or 'person'")

    def _get_account(self, value):
        """
        """
        ac = self.Account_class(self.db)
        ac.clear()
        try:
            if value.isdigit():
                ac.find(int(value))
            else:
                ac.find_by_name(value)
            return ac
        except Errors.NotFoundError as e:
            raise CerebrumError('Could not find Account {0}: {1}'.format(value,
                                                                         e))
        except Exception as e:
            raise CerebrumError('{0}'.format(e))
