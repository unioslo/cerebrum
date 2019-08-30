# -*- coding: utf-8 -*-
#
# Copyright 2009-2019 University of Oslo, Norway
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
"""Pan-institutional 'user create_unpersonal' bofh daemon functionality.

This module contains class, functions, etc. related to the command
'user create_unpersonal'
"""
from __future__ import unicode_literals

import warnings
import six

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd import bofhd_email
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.modules.bofhd.bofhd_user_create import BofhdUserCreateMethod
from Cerebrum.modules.bofhd.cmd_param import (AccountName,
                                              EmailAddress,
                                              GroupName,
                                              Command,
                                              FormatSuggestion,
                                              SimpleString)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings


def exc_to_text(e):
    """ Get an error text from an exception. """
    try:
        text = six.text_type(e)
    except UnicodeError:
        text = bytes(e).decode('utf-8', 'replace')
        warnings.warn("Non-unicode data in exception {!r}".format(e),
                      UnicodeWarning)
    return text


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
    'unpersonal_account_type': ['account_type', 'Enter account type',
                                'The type of unpersonal account.'],
}


@copy_func(
    BofhdUserCreateMethod,
    methods=['_user_create_set_account_type', '_user_create_basic',
             '_user_password']
)
class BofhdExtension(BofhdCommonMethods):
    """Class with 'user create_unpersonal' method."""

    all_commands = {}
    authz = BofhdUnpersonalAuth

    @classmethod
    def get_help_strings(cls):
        co = Factory.get('Constants')()
        account_types = co.fetch_constants(co.Account)
        cmd_args = {}
        list_sep = '\n - '
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'unpersonal_account_type':
                cmd_args[k][2] += '\nValid account types:'
                cmd_args[k][2] += list_sep + list_sep.join(six.text_type(c) for
                                                           c in account_types)
        del co
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
        perm_filter='can_create_user_unpersonal')

    def user_create_unpersonal(self, operator,
                               account_name, group_name,
                               contact_address, account_type):
        owner_group = self._get_group(group_name)
        self.ba.can_create_user_unpersonal(operator.get_entity_id(),
                                           group=owner_group)

        account_type = self._get_constant(self.const.Account, account_type,
                                          "account type")
        account = self._user_create_basic(operator, owner_group, account_name,
                                          account_type)
        self._user_password(operator, account)

        # Validate the contact address
        # TBD: Check if address is instance-internal?
        local_part, domain = bofhd_email.split_address(contact_address)
        ea = Email.EmailAddress(self.db)
        ed = Email.EmailDomain(self.db)
        try:
            if not ea.validate_localpart(local_part):
                raise AttributeError('Invalid local part')
            ed._validate_domain_name(domain)
        except AttributeError as e:
            raise CerebrumError("Invalid contact address: %s" % exc_to_text(e))

        # Unpersonal accounts shouldn't normally have a mail inbox, but they
        # get a forward target for the account, to be sent to those responsible
        # for the account, preferrably a sysadm mail list.
        if hasattr(account, 'add_contact_info'):
            account.add_contact_info(self.const.system_manual,
                                     self.const.contact_email,
                                     contact_address)

        # TBD: Better way of checking if email forwards are in use, by
        # checking if bofhd command is available?
        if hasattr(self, '_email_create_forward_target'):
            localaddr = '{}@{}'.format(
                account_name,
                Email.get_primary_default_email_domain())
            self._email_create_forward_target(localaddr, contact_address)

        quar = cereconf.BOFHD_CREATE_UNPERSONAL_quarantine
        if quar:
            qconst = self._get_constant(self.const.Quarantine, quar,
                                        "quarantine")
            account.add_entity_quarantine(qconst, operator.get_entity_id(),
                                          "Not granted for global password "
                                          "auth (ask IT-sikkerhet)",
                                          self._today())
        return {'account_id': int(account.entity_id)}
