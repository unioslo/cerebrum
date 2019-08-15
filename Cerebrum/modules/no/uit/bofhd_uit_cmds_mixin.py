# -*- coding: utf-8 -*-
#
# Copyright 2006-2019 University of Tromso, Norway
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
from __future__ import absolute_import, unicode_literals

from Cerebrum import Errors
from Cerebrum.modules.bofhd import bofhd_core
from Cerebrum.modules.bofhd import bofhd_core_help
from Cerebrum.modules.bofhd.cmd_param import (
    AccountName,
    Command,
    FormatSuggestion,
    PersonId,
    YesNo,
)
from Cerebrum.modules.bofhd.errors import PermissionDenied, CerebrumError
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.legacy_users import LegacyUsers
from Cerebrum.modules.no.uit import bofhd_auth
from Cerebrum.modules.no.uit import entity_terminate


def list_legacy_users(db, search_term):
    lu = LegacyUsers(db)
    results = dict()
    for row in lu.search(username=search_term):
        results[row['user_name']] = dict(row)
    for row in lu.search(ssn=search_term):
        results[row['user_name']] = dict(row)
    return list(results.values())


class BofhdUiTExtension(bofhd_core.BofhdCommonMethods):
    """
    Custom UiT commands for bofhd.
    """

    all_commands = {}
    parent_commands = False
    authz = bofhd_auth.UitAuth

    @classmethod
    def get_help_strings(cls):
        cmds = {
            'misc': {
                'misc_list_legacy_user': 'List reserved usernames',
            },
        }
        args = {
            'yes_no_sure': [
                'certain',
                'Are you absolutely certain you want to do this? This deletes'
                ' the account completely from the database and can not be'
                ' reversed. (y/n)']
        }
        return merge_help_strings(
            bofhd_core_help.get_help_strings(),
            ({}, cmds, args))

    #
    # UiT special table for reserved usernames. Usernames that is reserved due
    # to being used in legacy systems
    #
    all_commands['misc_list_legacy_user'] = Command(
        ("misc", "legacy_user"),
        PersonId(),
        fs=FormatSuggestion(
            "%-6s %11s %6s %4s ", ('user_name', 'ssn', 'source', 'type'),
            hdr="%-6s %-11s %6s %4s" % ('UserID', 'Personnr', 'Source', 'Type')
        )
    )

    def misc_list_legacy_user(self, operator, personid):
        # TODO: This method leaks personal information
        return list_legacy_users(self.db, personid)

    #
    # Special user delete just for UiT that actually deletes an entity from the
    # database
    #
    all_commands['user_delete_permanent'] = Command(
        ("user", "delete_permanent"),
        AccountName(help_ref='account_name_id_uid'),
        YesNo(help_ref='yes_no_sure'),
        perm_filter='is_superuser',
        fs=FormatSuggestion(
            "Account deleted successfully\n" +
            "Account name:        %s\n" +
            "Owner:               %s\n" +
            "New primary account: %s",
            ('account_name', 'owner_name', 'primary_account_name',
             ),
        )
    )

    def user_delete_permanent(self, operator, account_name, yesno):
        """ Delete a user from the database

        This command deletes every database entry connected to the entity id of
        an account. It is reserved for use by superusers only and you should
        not be using it unless you are absolutely sure about what you are
        doing.

        :param operator: Cerebrum.Account object of operator
        :param basestring account_name: account name of target account
        :param basestring yesno: 'y' to confirm deletion
        :return: Information about the deleted account and its owner
        :rtype: dict
        :raises CerebrumError: If account name is unknown, or the account owner
            is not a person
        """
        if yesno.lower() != 'y':
            return "Did not receive 'y'. User deletion stopped."

        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")

        ac = self._get_account(account_id=account_name, idtype='name')
        try:
            terminate = entity_terminate.delete(self.db, ac)
        except Errors.NotFoundError:
            raise CerebrumError(
                'Account: {}, not owned by a person. Aborting'.format(
                    account_name))
        return terminate
