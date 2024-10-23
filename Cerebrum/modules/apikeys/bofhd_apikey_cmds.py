# -*- coding: utf-8 -*-
#
# Copyright 2019-2024 University of Oslo, Norway
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

.. important::
   These classes should not be used directly.  Always make subclasses of
   BofhdCommandBase classes, and add a proper auth class/mixin to the class
   authz.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

from Cerebrum import Errors
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd import bofhd_core
from Cerebrum.modules.bofhd import bofhd_core_help
from Cerebrum.modules.bofhd.bofhd_utils import format_time
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings

from .dbal import ApiMapping


no_access_error = PermissionDenied("Not allowed to access api subscriptions")


class BofhdApiKeyAuth(BofhdAuth):
    """Auth for api subscription commands."""

    def can_modify_api_mapping(self, operator, account=None,
                               query_run_any=False):
        """
        Check if an operator is allowed to set apikey on an account.
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False

        # TODO: Consider allowing owners to set this on accounts that they own
        raise no_access_error

    def can_list_api_mapping(self, operator, account=None,
                             query_run_any=False):
        """
        Check if an operator is allowed to list apikeys on an account.
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise no_access_error


HELP_GROUP = {
    'api': 'Display and modify API settings',
}

HELP_CMD = {
    'api': {
        'api_subscription_set': 'set api subscription for account',
        'api_subscription_clear': 'remove api subscription for account',
        'api_subscription_list': 'list api subscriptions for account',
        'api_subscription_info': 'show info on a subscription identifier',
    },
}

HELP_ARGS = {
    'api-client-id': [
        "api-client-id",
        "Enter client identifier",
        "A client subscription identifier",
    ],
    'api-client-desc': [
        "api-client-desc",
        "Enter description",
        "A description of this client subscription",
    ],
}


class BofhdApiKeyCommands(bofhd_core.BofhdCommandBase):
    """API subscription commands."""

    all_commands = {}
    authz = BofhdApiKeyAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            (HELP_GROUP, HELP_CMD, HELP_ARGS),
            bofhd_core_help.get_help_strings(),
        )

    #
    # api subscription_set <identifier> <account> [description]
    #
    all_commands['api_subscription_set'] = cmd_param.Command(
        ('api', 'subscription_set'),
        cmd_param.SimpleString(help_ref='api-client-id'),
        cmd_param.AccountName(),
        cmd_param.SimpleString(help_ref='api-client-desc', optional=True),
        fs=cmd_param.FormatSuggestion(
            "Set subscription='%s' for account %s (%d)",
            ('identifier', 'account_name', 'account_id')
        ),
        perm_filter='can_modify_api_mapping',
    )

    def api_subscription_set(self, operator, identifier, account_id,
                             description=None):
        """Set api client identifier to user mapping"""
        # check araguments
        if not identifier:
            raise CerebrumError("Invalid identifier")
        account = self._get_account(account_id)

        # check permissions
        self.ba.can_modify_api_mapping(operator.get_entity_id(),
                                       account=account)

        keys = ApiMapping(self.db)
        try:
            row = keys.get(identifier)
            if row['account_id'] != account.entity_id:
                raise CerebrumError("Identifier already assigned")
        except Errors.NotFoundError:
            pass

        keys.set(identifier, account.entity_id, description)
        return {
            'identifier': identifier,
            'account_id': account.entity_id,
            'account_name': account.account_name,
            'description': description,
        }

    #
    # api subscription_clear <identifier>
    #
    all_commands['api_subscription_clear'] = cmd_param.Command(
        ('api', 'subscription_clear'),
        cmd_param.SimpleString(help_ref='api-client-id'),
        fs=cmd_param.FormatSuggestion(
            "Cleared subscription='%s' from account %s (%d)",
            ('identifier', 'account_name', 'account_id')
        ),
        perm_filter='can_modify_api_mapping',
    )

    def api_subscription_clear(self, operator, identifier):
        """Remove mapping for a given api client identifier"""
        if not identifier:
            raise CerebrumError("Invalid identifier")

        keys = ApiMapping(self.db)
        try:
            mapping = keys.get(identifier)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown subscription identifier %r" %
                                (identifier,))

        # check permissions
        account = self.Account_class(self.db)
        account.find(mapping['account_id'])
        self.ba.can_modify_api_mapping(operator.get_entity_id(),
                                       account=account)

        if not mapping:
            raise CerebrumError('No identifier=%r for account %s (%d)' %
                                (identifier, account.account_name,
                                 account.entity_id))
        keys.delete(identifier)
        return {
            'identifier': mapping['identifier'],
            'account_id': account.entity_id,
            'account_name': account.account_name,
            'description': mapping['description'],
        }

    #
    # api subscription_list <account>
    #
    all_commands['api_subscription_list'] = cmd_param.Command(
        ('api', 'subscription_list'),
        cmd_param.AccountName(),
        fs=cmd_param.get_format_suggestion_table(
            ("identifier", "Identifier", 36, "s", True),
            (format_time("updated_at"), "Last update", 16, "s", True),
            ("description", "Description", 28, "s", True),
        ),
        perm_filter='can_list_api_mapping',
    )

    def api_subscription_list(self, operator, account_id):
        """List api client mappings for a given user."""
        account = self._get_account(account_id)
        self.ba.can_list_api_mapping(operator.get_entity_id(), account=account)
        keys = ApiMapping(self.db)

        return [
            {
                'account_id': row['account_id'],
                'identifier': row['identifier'],
                'updated_at': row['updated_at'],
                'description': row['description'],
            }
            for row in keys.search(account_id=account.entity_id)
        ]

    #
    # api subscription_info <identifier>
    #
    all_commands['api_subscription_info'] = cmd_param.Command(
        ('api', 'subscription_info'),
        cmd_param.SimpleString(help_ref='api-client-id'),
        fs=cmd_param.FormatSuggestion(
            textwrap.dedent(
                """
                Identifier:  %s
                Account:     %s (%d)
                Last update: %s
                Description: %s
                """
            ).strip(),
            (
                'identifier',
                'account_name', 'account_id',
                format_time('updated_at'),
                'description',
            ),
        ),
        perm_filter='can_list_api_mapping',
    )

    def api_subscription_info(self, operator, identifier):
        """List api client mappings for a given user."""
        if not self.ba.can_list_api_mapping(operator.get_entity_id(),
                                            query_run_any=True):
            # Abort early if user has no access to list *any* api mappings,
            # otherwise we may leak info on valid identifiers.
            raise no_access_error

        keys = ApiMapping(self.db)
        try:
            mapping = keys.get(identifier)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown subscription identifier %r" %
                                (identifier,))
        account = self.Account_class(self.db)
        account.find(mapping['account_id'])
        self.ba.can_list_api_mapping(operator.get_entity_id(), account=account)

        return {
            'account_id': account.entity_id,
            'account_name': account.account_name,
            'identifier': mapping['identifier'],
            'updated_at': mapping['updated_at'],
            'description': mapping['description'],
        }
