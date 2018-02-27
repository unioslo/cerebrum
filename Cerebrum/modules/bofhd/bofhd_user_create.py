#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2009-2016 University of Oslo, Norway
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
"""Common 'user create' bofh daemon functionality used across all institutions.

This module contains class, functions, etc. related to the command
'user create' This file should only include such generic functionality.

Push institution-specific extensions to
modules/no/<institution>/bofhd_<institution>_cmds.py.
"""
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import cmd_param as cmd
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied


CMD_HELP = {
    'user': {
        'user_create': 'Create a new user account',
    }
}


class BofhdUserCreateMethod(BofhdCommonMethods):
    """Class with 'user create' method that is used by most, 'normal' instances.

    Instances that requires some special care for some methods could subclass
    those in their own institution-specific class
    (modules.no.<inst>.bofhd_<inst>_cmds.py:BofhdExtension).

    The methods are using the BofhdAuth that is defined in the institution's
    subclass - L{BofhdExtension.authz}.

    """

    all_commands = {}
    authz = BofhdAuth

    @classmethod
    def get_help_strings(cls):
        # All the args are specified in bofhd_core_help, but user_create is not
        group, cmd, args = get_help_strings()
        for group_name in CMD_HELP:
            cmd.setdefault(group_name, {}).update(CMD_HELP[group_name])
        return group, cmd, args

    def _user_create_prompt_func_helper(self, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])

        if not all_args:
            return {'prompt': "Person identification",
                    'help_ref': "user_create_person_id"}
        arg = all_args.pop(0)
        if arg.startswith("group:"):
            group_owner = True
        else:
            group_owner = False
        if not all_args or group_owner:
            if group_owner:
                group = self._get_group(arg.split(":")[1])
                if all_args:
                    all_args.insert(0, group.entity_id)
                else:
                    all_args = [group.entity_id]
            else:
                c = self._find_persons(arg)
                map = [(("%-8s %s", "Id", "Name"), None)]
                for i in range(len(c)):
                    person = self._get_person("entity_id", c[i]['person_id'])
                    map.append((
                        ("%8i %s", int(c[i]['person_id']),
                         person.get_name(self.const.system_cached,
                                         self.const.name_full)),
                        int(c[i]['person_id'])))
                if not len(map) > 1:
                    raise CerebrumError("No persons matched")
                return {'prompt': "Choose person from list",
                        'map': map,
                        'help_ref': 'user_create_select_person'}
        owner_id = all_args.pop(0)
        if not group_owner:
            person = self._get_person("entity_id", owner_id)
            existing_accounts = []
            account = self.Account_class(self.db)
            for r in account.list_accounts_by_owner_id(person.entity_id):
                account = self._get_account(r['account_id'], idtype='id')
                if account.expire_date:
                    exp = account.expire_date.strftime('%Y-%m-%d')
                else:
                    exp = '<not set>'
                existing_accounts.append("%-10s %s" % (account.account_name,
                                                       exp))
            if existing_accounts:
                existing_accounts = "Existing accounts:\n%-10s %s\n%s\n" % (
                    "uname", "expire", "\n".join(existing_accounts))
            else:
                existing_accounts = ''
            if existing_accounts:
                if not all_args:
                    return {'prompt': "%sContinue? (y/n)" % existing_accounts}
                yes_no = all_args.pop(0)
                if not yes_no == 'y':
                    raise CerebrumError("Command aborted at user request")
            if not all_args:
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s@%s" % (
                        self.const.PersonAffStatus(aff['status']),
                        self._format_ou_name(ou))
                    map.append((("%s", name),
                                {'ou_id': int(aff['ou_id']),
                                 'aff': int(aff['affiliation'])}))
                if not len(map) > 1:
                    raise CerebrumError("Person has no affiliations. "
                                        "Try person affiliation_add")
                return {'prompt': "Choose affiliation from list", 'map': map}
            all_args.pop(0)  # Affiliation
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type'}
            all_args.pop(0)  # np_type
        if not all_args:
            ret = {'prompt': "Username", 'last_arg': True}
            posix_user = Factory.get('PosixUser')(self.db)
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    fname, lname = [
                        person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first,
                                  self.const.name_last)]
                    sugg = posix_user.suggest_unames(
                        self.const.account_namespace, fname, lname)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError("Too many arguments")

    def _user_create_set_account_type(self, account,
                                      owner_id, ou_id, affiliation,
                                      priority=None):
        person = self._get_person('entity_id', owner_id)
        try:
            affiliation = self.const.PersonAffiliation(affiliation)
            # make sure exist
            int(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError("Invalid affiliation {}".format(affiliation))
        for aff in person.get_affiliations():
            if aff['ou_id'] == ou_id and aff['affiliation'] == affiliation:
                break
        else:
            raise CerebrumError(
                "Owner did not have any affiliation {}".format(affiliation))
        account.set_account_type(ou_id, affiliation, priority=priority)

    def _user_create_basic(self, operator, owner, uname, np_type=None):
        account = self.Account_class(self.db)
        try:
            account.find_by_name(uname)
        except Errors.NotFoundError:
            account.clear()
        else:
            raise CerebrumError("Username already taken: {}".format(uname))
        account.populate(uname,
                         owner.entity_type,
                         owner.entity_id,
                         np_type,
                         operator.get_entity_id(),
                         None)
        account.write_db()
        return account

    def _user_password(self, operator, account, passwd=None):
        """Set new (random) password for account and store in bofhd session"""
        if not passwd:
            passwd = account.make_passwd(account.account_name)
        account.set_password(passwd)
        try:
            account.write_db()
        except self.db.DatabaseError as m:
            raise CerebrumError('Database error: {}'.format(m))
        operator.store_state('new_account_passwd',
                             {'account_id': int(account.entity_id),
                              'password': passwd})

    #
    # user create ---
    #
    all_commands['user_create'] = cmd.Command(
        ('user', 'create'),
        prompt_func=_user_create_prompt_func_helper,
        fs=cmd.FormatSuggestion(
            "Created account_id=%i", ("account_id",)),
        perm_filter='is_superuser')

    def user_create(self, operator, *args):
        np_type = None
        affiliation = None

        if args[0].startswith('group:'):
            group_id, np_type, uname = args
            owner = self._get_group(group_id.split(":")[1])
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")
        else:
            if len(args) == 4:
                idtype, person_id, affiliation, uname = args
            else:
                idtype, person_id, yes_no, affiliation, uname = args
            owner = self._get_person("entity_id", person_id)

        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may reserve users")
        account = self._user_create_basic(operator, owner, uname, np_type)
        self._user_password(operator, account)
        for spread in cereconf.BOFHD_NEW_USER_SPREADS:
            account.add_spread(self.const.Spread(spread))
        try:
            account.write_db()
            if affiliation is not None:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(
                    account, owner.entity_id, ou_id, affiliation)
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        return {'account_id': int(account.entity_id)}
