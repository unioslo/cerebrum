# -*- coding: utf-8 -*-
#
# Copyright 2009-2023 University of Oslo, Norway
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
Pan-institutional 'user create_unpersonal' bofh daemon functionality.

This module contains class, functions, etc. related to the command
'user create_unpersonal'
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    # TODO: unicode_literals,
)

import six

from Cerebrum.Errors import InvalidAccountCreationArgument
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.AccountPolicy import AccountPolicy
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_user_create import BofhdUserCreateMethod
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.modules.bofhd.cmd_param import (AccountName,
                                              EmailAddress,
                                              GroupName,
                                              Command,
                                              FormatSuggestion,
                                              SimpleString)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings


class BofhdUnpersonalAuth(BofhdAuth):
    """ Auth for user create command. """

    def can_create_user_unpersonal(self, operator, group=None, disk=None,
                                   query_run_any=False):
        """Check if operator could create an account with group owner.

        You need access to the given disk. If no disk is given, you only need
        to have access to create unpersonal users *somewhere* to be allowed -
        for now.

        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return self._has_operation_perm_somewhere(
                operator, self.const.auth_create_user_unpersonal)
        if disk:
            return self._query_disk_permissions(
                operator, self.const.auth_create_user_unpersonal,
                self._get_disk(disk), None)
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_create_user_unpersonal):
            return True
        raise PermissionDenied("No access")


CMD_HELP = {
    'user': {
        'user_create_unpersonal': 'Create user account owned by a group',
    }
}

CMD_ARGS = {
    'unpersonal_account_type': [
        'account_type',
        'Enter account type',
        'The type of unpersonal account.',
    ],
}


@copy_func(
    BofhdUserCreateMethod,
    methods=[
        '_user_create_set_account_type',
        '_user_create_basic',
        '_user_password',
    ]
)
class BofhdExtension(BofhdCommandBase):
    """Class with 'user create_unpersonal' method."""

    all_commands = {}
    authz = BofhdUnpersonalAuth

    @classmethod
    def get_help_strings(cls):
        const = Factory.get('Constants')()
        account_types = const.fetch_constants(const.Account)
        cmd_args = {}
        list_sep = '\n - '
        for key, value in CMD_ARGS.items():
            cmd_args[key] = value[:]
            if key == 'unpersonal_account_type':
                cmd_args[key][2] += '\nValid account types:'
                cmd_args[key][2] += list_sep + list_sep.join(
                    six.text_type(c) for c in account_types)
        del const
        return merge_help_strings(
            ({}, {}, cmd_args),  # We want _our_ cmd_args to win!
            get_help_strings(),
            ({}, CMD_HELP, {}))

    #
    # user create_unpersonal
    #
    all_commands['user_create_unpersonal'] = Command(
        ('user', 'create_unpersonal'),
        AccountName(),
        GroupName(),
        EmailAddress(),
        SimpleString(help_ref="unpersonal_account_type"),
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='can_create_user_unpersonal',
    )

    def user_create_unpersonal(self, operator,
                               account_name, group_name,
                               contact_address, account_type):
        """Bofh command: user create_unpersonal"""
        self.ba.can_create_user_unpersonal(operator.get_entity_id(),
                                           group=self._get_group(group_name))

        account_type = self._get_constant(self.const.Account, account_type,
                                          "account type")

        account_policy = AccountPolicy(self.db)
        try:
            account = account_policy.create_group_account(
                operator.get_entity_id(),
                account_name,
                self._get_group(group_name),
                contact_address,
                account_type
            )
        except InvalidAccountCreationArgument as e:
            raise CerebrumError(e)

        self._user_password(operator, account)

        # TBD: Better way of checking if email forwards are in use, by
        # checking if bofhd command is available?
        if hasattr(self, '_email_create_forward_target'):
            localaddr = '{}@{}'.format(
                account_name,
                Email.get_primary_default_email_domain())
            self._email_create_forward_target(localaddr, contact_address)

        return {'account_id': int(account.entity_id)}
