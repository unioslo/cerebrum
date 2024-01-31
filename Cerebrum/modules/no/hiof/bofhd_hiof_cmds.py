# -*- coding: utf-8 -*-
#
# Copyright 2007-2023 University of Oslo, Norway
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
""" HiOF bohfd module. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    # TODO: unicode_literals,
)

import six

import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.apikeys import bofhd_apikey_cmds
from Cerebrum.modules.audit import bofhd_history_cmds
from Cerebrum.modules.bofhd import bofhd_access
from Cerebrum.modules.bofhd import bofhd_contact_info
from Cerebrum.modules.bofhd import bofhd_group_roles
from Cerebrum.modules.bofhd import bofhd_ou_cmds
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd_requests.request import BofhdRequests
from Cerebrum.modules.bofhd_requests import bofhd_requests_auth
from Cerebrum.modules.bofhd_requests import bofhd_requests_cmds
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.modules.no.uio import bofhd_uio_cmds
from Cerebrum.modules.trait import bofhd_trait_cmds


# BofhdRequests are unfortunately very UiO specific. Let's try to keep
# Hiof stuff here to avoid making things worse.
class HiofBofhdRequests(BofhdRequests):
    def __init__(self, db, const):
        # Do normal extension of baseclass constructor
        super(HiofBofhdRequests, self).__init__(db, const)
        # Hiofs BohfdRequest constant must be added to self.conflicts
        self.conflicts[int(const.bofh_ad_attrs_remove)] = None


class HiofAuth(BofhdAuth):
    """ hiof specific auth. """

    def can_alter_group(self, operator, group=None, query_run_any=False):
        """Checks if the operator has permission to add/remove group members
        for the given group.

        @type operator: int
        @param operator: The entity_id of the user performing the operation.

        @type group: An entity of EntityType Group
        @param group: The group to add/remove members to/from.

        @type query_run_any: True or False
        @param query_run_any: Check if the operator has permission *somewhere*

        @return: True or False
        """
        if self.is_superuser(operator):
            return True
        if query_run_any and self._is_admin(operator):
            return True
        if self._is_admin(operator, group.entity_id):
            return True
        return super(HiofAuth, self).can_alter_group(operator, group,
                                                     query_run_any)


@copy_func(
    bofhd_uio_cmds.BofhdExtension,
    methods=[
        '_user_create_set_account_type',
        '_viewable_external_ids',
    ]
)
class BofhdExtension(BofhdCommonMethods):

    OU_class = Utils.Factory.get('OU')
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')

    all_commands = {}
    parent_commands = True
    authz = HiofAuth

    @property
    def ou(self):
        try:
            return self.__ou
        except AttributeError:
            self.__ou = Factory.get('OU')(self.db)
            return self.__ou

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            get_help_strings(),
            ({}, HELP_CMDS, {}))

    #
    # user remove_ad_attrs
    #
    all_commands['user_remove_ad_attrs'] = cmd_param.Command(
        ('user', 'remove_ad_attrs'),
        cmd_param.AccountName(),
        cmd_param.Spread(),
        perm_filter='is_superuser')

    def user_remove_ad_attrs(self, operator, uname, spread):
        """ Bofh command user remove_ad_attrs

        Delete AD attributes home, profile_path and ou for user by
        adding a BofhdRequests. The actual deletion is governed by
        job_runner when calling process_bofhd_requests. This is done
        to avvoid race condition with AD sync.

        @param operator: operator in bofh session
        @type  uname: string
        @param uname: user name of account which AD values should be
                      deleted
        @type  spread: string
        @param spread: code_str of spread
        @rtype: string
        @return: OK message if success
        """
        account = self._get_account(uname, idtype='name')
        spread = self._get_constant(self.const.Spread, spread)
        br = HiofBofhdRequests(self.db, self.const)
        delete_attrs = account.get_ad_attrs_by_spread(spread)
        if delete_attrs:
            br.add_request(operator.get_entity_id(),
                           br.now,
                           self.const.bofh_ad_attrs_remove,
                           account.entity_id,
                           None,
                           state_data=six.text_type(spread))
            return "OK, added remove AD attributes request for %s" % uname
        else:
            return "No AD attributes to remove for user %s" % uname

    #
    # user list_ad_attrs
    #
    all_commands['user_list_ad_attrs'] = cmd_param.Command(
        ('user', 'list_ad_attrs'),
        cmd_param.AccountName(),
        perm_filter='is_superuser',
        fs=cmd_param.FormatSuggestion(
            "%-16s %-16s %s", ("spread", "ad_attr", "ad_val"),
            hdr="%-16s %-16s %s" % ("Spread", "AD attribute", "Value")))

    def user_list_ad_attrs(self, operator, uname):
        """
        Bofh command user list_ad_attrs

        List all ad_traits for user

        @param operator: operator in bofh session
        @type  uname: string
        @param uname: user name of account which AD values should be
                      deleted
        @rtype: string
        @return: OK message if success
        """
        account = self._get_account(uname, idtype='name')
        ret = []
        for spread, attr_map in account.get_ad_attrs().iteritems():
            spread = self._get_constant(self.const.Spread, spread, 'spread')
            for attr_type, attr_val in attr_map.items():
                ret.append({
                    'spread': six.text_type(spread),
                    'ad_attr': attr_type,
                    'ad_val': attr_val,
                })
        return ret

    #
    # user create prompt
    #
    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)

    #
    # user create prompt helper
    #
    def _user_create_prompt_func_helper(self, ac_type, session, *args):
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
                        six.text_type(
                            self.const.PersonAffStatus(aff['status'])),
                        self._format_ou_name(ou))
                    map.append(
                        (("%s", name),
                         {'ou_id': int(aff['ou_id']),
                          'aff': int(aff['affiliation']), }))
                if not len(map) > 1:
                    raise CerebrumError("Person has no affiliations."
                                        " Try person affiliation_add")
                return {'prompt': "Choose affiliation from list", 'map': map}
            all_args.pop(0)
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type'}
            all_args.pop(0)
        if not all_args:
            return {'prompt': "Enter spread",
                    'help_ref': 'string_spread'}
        all_args.pop(0)
        if not all_args:
            return {'prompt': "Enter e-mail server name",
                    'help_ref': 'string_email_host'}
        all_args.pop(0)
        if not all_args:
            ret = {'prompt': "Username", 'last_arg': True}
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    sugg = account.suggest_unames(person)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError("Too many arguments")

    #
    # user create
    #
    all_commands['user_create'] = cmd_param.Command(
        ('user', 'create'),
        prompt_func=user_create_prompt_func,
        fs=cmd_param.FormatSuggestion(
            "Created account_id=%i", ("account_id",)),
        perm_filter='is_superuser')

    def user_create(self, operator, *args):
        if args[0].startswith('group:'):
            group_id, np_type, spread, email_server, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")
            affiliation = None
            owner_type = self.const.entity_group
        else:
            if len(args) == 6:
                (idtype,
                 person_id,
                 affiliation,
                 spread,
                 email_server,
                 uname) = args
            else:
                (idtype,
                 person_id,
                 yes_no,
                 affiliation,
                 spread,
                 email_server,
                 uname) = args
            person = self._get_person("entity_id", person_id)
            owner_type, owner_id = self.const.entity_person, person.entity_id
            np_type = None
        account = self.Account_class(self.db)
        account.clear()
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may reserve users")
        account.populate(uname,
                         owner_type,  # Owner type
                         owner_id,
                         np_type,                      # np_type
                         operator.get_entity_id(),  # creator_id
                         None)                      # expire_date
        account.write_db()
        for s in cereconf.BOFHD_NEW_USER_SPREADS:
            account.add_spread(self.const.Spread(s))
        if spread:
            try:
                account.add_spread(self.const.Spread(spread))
            except Errors.NotFoundError:
                raise CerebrumError("No such spread: %r" % spread)
        account.write_db()
        try:
            account._update_email_server(email_server)
        except Errors.NotFoundError:
            raise CerebrumError("No such email server: %r" % email_server)
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        try:
            account.write_db()
            if affiliation is not None:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(
                    account, person.entity_id, ou_id, affiliation)
        except self.db.DatabaseError as m:
            raise CerebrumError("Database error: %s" % m)
        operator.store_state(
            "new_account_passwd",
            {'account_id': int(account.entity_id), 'password': passwd})
        return {'account_id': int(account.entity_id)}


class _ContactAuth(HiofAuth, bofhd_contact_info.BofhdContactAuth):
    pass


class ContactCommands(bofhd_contact_info.BofhdContactCommands):
    authz = _ContactAuth


class _BofhdRequestsAuth(HiofAuth, bofhd_requests_auth.RequestsAuth):
    pass


class BofhdRequestCommands(bofhd_requests_cmds.BofhdExtension):
    authz = _BofhdRequestsAuth


class _AccessAuth(HiofAuth, bofhd_access.BofhdAccessAuth):
    pass


class AccessCommands(bofhd_access.BofhdAccessCommands):
    authz = _AccessAuth


class _ApiKeyAuth(HiofAuth, bofhd_apikey_cmds.BofhdApiKeyAuth):
    pass


class ApiKeyCommands(bofhd_apikey_cmds.BofhdApiKeyCommands):
    authz = _ApiKeyAuth


class _GroupRoleAuth(HiofAuth, bofhd_group_roles.BofhdGroupRoleAuth):
    pass


class GroupRoleCommands(bofhd_group_roles.BofhdGroupRoleCommands):
    authz = _GroupRoleAuth


class _HistoryAuth(HiofAuth, bofhd_history_cmds.BofhdHistoryAuth):
    pass


class HistoryCommands(bofhd_history_cmds.BofhdHistoryCmds):
    authz = _HistoryAuth


class _OuAuth(HiofAuth, bofhd_ou_cmds.OuAuth):
    pass


class OuCommands(bofhd_ou_cmds.OuCommands):
    authz = _OuAuth


class _TraitAuth(HiofAuth, bofhd_trait_cmds.TraitAuth):
    pass


class TraitCommands(bofhd_trait_cmds.TraitCommands):
    authz = _TraitAuth


HELP_CMDS = {
    'user': {
        'user_create': 'Create a user account',
        'user_list_ad_attrs': 'View ad attributes for a user',
        'user_remove_ad_attrs': 'Delete ad attributes for a user',
    }
}
