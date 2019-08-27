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
"""Pan-institutional 'user create_unperson' bofh daemon functionality.

This module contains class, functions, etc. related to the command
'user create_unperson'
"""
from __future__ import unicode_literals

import logging
import six

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.bofhd_core import (BofhdCommonMethods,
                                               BofhdCommandBase)
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.cmd_param import (AccountName,
                                              EmailAddress,
                                              GroupName,
                                              Command,
                                              FormatSuggestion,
                                              SimpleString)


CMD_HELP = {
    'user': {
        'user_create_unperson': 'Create a new unperson account',
    }
}

CMD_ARGS = {
    'unperson_account_type': ['account_type', 'Enter account type',
                                'The type of unperson account.'],
}


class BofhdExtension(BofhdCommonMethods):
    """Class with 'user create_unperson' method."""

    all_commands = {}

    @classmethod
    def get_help_strings(cls):
        co = Factory.get('Constants')()
        account_types = co.fetch_constants(co.Account)

        cmd_args = {}
        list_sep = '\n - '
        for k, v in CMD_ARGS.items():
            cmd_args[k] = v[:]
            if k == 'unperson_account_type':
                cmd_args[k][2] += '\nAccount types:'
                cmd_args[k][2] += list_sep + list_sep.join(six.text_type(c) for
                                                           c in account_types)
        del co
        return merge_help_strings(
            ({}, {}, cmd_args),  # We want _our_ cmd_args to win!
            get_help_strings(),
            ({}, CMD_HELP, {}))


    #
    # user create_unperson
    #
    all_commands['user_create_unperson'] = Command(
        ('user', 'create_unperson'),
        AccountName(),
        GroupName(),
        EmailAddress(),
        SimpleString(help_ref="string_np_type"),
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)))

    def user_create_unperson(self, operator,
                             account_name, group_name,
                             contact_address, account_type):
        owner_group = self._get_group(group_name)
        self.ba.can_create_user_unperson(operator.get_entity_id(),
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
            localaddr = '{}@{}'.format(ccount_name,
                Email.get_primary_default_email_domain())
            self._email_create_forward_target(localaddr, contact_address)

        quar = cereconf.BOFHD_CREATE_UNPERSON_QUARANTINE
        if quar:
            qconst = self._get_constant(self.const.Quarantine, quar,
                                        "quarantine")
            account.add_entity_quarantine(qconst, operator.get_entity_id(),
                                          "Not granted for global password "
                                          "auth (ask IT-sikkerhet)",
                                          self._today())
        return {'account_id': int(account.entity_id)}
