# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
This module contains apikey module commands for bofhd.

..warning::
    The classes in this module should *not* be used directly. Make subclasses
    of the classes here, and mix in the proper auth classes.

    E.g. given a ``FooAuth`` class that implements or overrides the core
    ``BofhdAuth`` authorization checks, you should create:
    ::

        class FooApiKeyAuth(FooAuth, BofhdApiKeyAuth):
            pass


        class FooApiKeyCmds(BofhdApiKeyCommands):
            authz = FooApiKeyAuth

    Then list the FooApiKeyCmds in your bofhd configuration file. This way, any
    override done in FooAuth (e.g. is_superuser) will also take effect in these
    classes.
"""
from __future__ import unicode_literals

import logging

import six

from Cerebrum import Errors
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (AccountName, Command,
                                              FormatSuggestion, SimpleString,)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from .dbal import ApiKeys

logger = logging.getLogger(__name__)


class BofhdApiKeyAuth(BofhdAuth):
    """ Auth for entity contactinfo_* commands. """

    def can_modify_apikey(self, operator, account=None, query_run_any=False):
        """
        Check if an operator is allowed to set apikey on an account.
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return True

        # TODO: Is this ok? We probably want:
        # - operator == account
        # - operator == owner of account
        # - operator is member of group that owns account
        # - Maybe implement separate auth const?
        try:
            return self.can_set_password(operator, account=account,
                                         query_run_any=False)
        except PermissionDenied:
            pass
        raise PermissionDenied(
            "Not allowed to modify apikey for {}".format(account))


CMD_HELP = {
    'user': {
        'user_apikey_set': 'set a new apikey for account',
        'user_apikey_clear': 'remove apikey for account',
    },
}

CMD_ARGS = {
    'account_apikey_label': [
        'label',
        'Enter label',
        'A unique label to tag the API with.',
    ],
    'account_apikey_value': [
        'value',
        'Enter api key',
        'The API key to set for a given user.',
    ],
}


class BofhdApiKeyCommands(BofhdCommandBase):

    all_commands = {}
    authz = BofhdApiKeyAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            ({}, CMD_HELP, CMD_ARGS),
            get_help_strings())

    #
    # user apikey_set <account> <label> <value>
    #
    all_commands['user_apikey_set'] = Command(
        ('user', 'apikey_set'),
        AccountName(),
        SimpleString(help_ref='account_apikey_label'),
        SimpleString(help_ref='account_apikey_value'),
        fs=FormatSuggestion(
            "Updated apikey for account %s (%d) with label '%s'",
            ('account_name', 'account_id', 'label')
        ),
        perm_filter='can_modify_apikey',
    )

    def user_apikey_set(self, operator, account_id, label, value):
        """Add an API key to an account."""

        # check araguments
        account = self._get_account(account_id)
        if not label:
            raise CerebrumError("Invalid apikey label")
        if not value:
            raise CerebrumError("Invalid apikey value")

        # check permissions
        self.ba.can_modify_apikey(operator.get_entity_id(), account=account)

        keys = ApiKeys(self.db)

        try:
            other_account_id, other_label = keys.map(value)
            # Not ideal, we leak information about a key being valid, but on
            # the other hand - the operator is already in posession of a valid
            # key, it can be validated simply by querying the API...
            if other_account_id != account.entity_id or other_label != label:
                raise CerebrumError("Key already in use")
        except Errors.NotFoundError:
            pass

        keys.set(account.entity_id, label, value)

        return {
            'account_id': account.entity_id,
            'account_name': account.account_name,
            'label': label,
        }

    #
    # user apikey_clear <account> <label>
    #
    all_commands['user_apikey_clear'] = Command(
        ('user', 'apikey_clear'),
        AccountName(),
        SimpleString(help_ref='account_apikey_label'),
        fs=FormatSuggestion(
            "Cleared apikey for account %s (%d) with label '%s'",
            ('account_name', 'account_id', 'label')
        ),
        perm_filter='can_modify_apikey',
    )

    def user_apikey_clear(self, operator, account_id, label):
        """Add an API key to an account."""

        # check araguments
        account = self._get_account(account_id)
        if not label:
            raise CerebrumError("Invalid apikey label")

        # check permissions
        self.ba.can_modify_apikey(operator.get_entity_id(), account=account)

        keys = ApiKeys(self.db)

        try:
            keys.delete(account.entity_id, label)
        except Errors.NotFoundError as e:
            raise CerebrumError(six.text_type(e))

        return {
            'account_id': account.entity_id,
            'account_name': account.account_name,
            'label': label,
        }
