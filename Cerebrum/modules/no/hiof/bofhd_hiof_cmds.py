# -*- coding: utf-8 -*-
#
# Copyright 2007-2018 University of Oslo, Norway
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
from six import text_type

import cereconf

from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import bofhd_contact_info
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd_requests.utils import BofhdRequests

from Cerebrum.modules.bofhd.bofhd_utils import copy_func, copy_command
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as cmd_base
from Cerebrum.modules.bofhd import bofhd_access


# BofhdRequests are unfortunately very UiO specific. Let's try to keep
# Hiof stuff here to avoid making things worse.
class HiofBofhdRequests(BofhdRequests):
    def __init__(self, db, const, id=None):
        # Do normal extension of baseclass constructor
        super(HiofBofhdRequests, self).__init__(db, const, id)
        # Hiofs BohfdRequest constant must be added to self.conflicts
        self.conflicts[int(const.bofh_ad_attrs_remove)] = None


class HiofAuth(BofhdAuth):
    """ Indigo specific auth. """
    pass


class HiofContactAuth(HiofAuth, bofhd_contact_info.BofhdContactAuth):
    """ Indigo specific contact info auth. """
    pass


class HiofAccessAuth(HiofAuth, bofhd_access.BofhdAccessAuth):
    """Hiof specific access auth"""
    pass


uio_commands = [
    'misc_cancel_request',
    'misc_list_requests',
    'ou_info',
    'ou_search',
    'ou_tree',
]


@copy_command(
    cmd_base,
    'all_commands', 'all_commands',
    commands=uio_commands)
@copy_func(
    cmd_base,
    methods=uio_commands)
@copy_func(
    cmd_base,
    methods=['_user_create_set_account_type']
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
                           state_data=text_type(spread))
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
                    'spread': text_type(spread),
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
                        text_type(self.const.PersonAffStatus(aff['status'])),
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
                    fname, lname = [person.get_name(self.const.system_cached,
                                                    v)
                                    for v in (self.const.name_first,
                                              self.const.name_last)]
                    sugg = account.suggest_unames(self.const.account_namespace,
                                                  fname,
                                                  lname)
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


class ContactCommands(bofhd_contact_info.BofhdContactCommands):
    authz = HiofContactAuth


class HiofAccessCommands(bofhd_access.BofhdAccessCommands):
    """Hiof specific bofhd access * commands"""
    authz = HiofAccessAuth


HELP_CMDS = {
    'user': {
        'user_create': 'Create a user account',
        'user_list_ad_attrs': 'View ad attributes for a user',
        'user_remove_ad_attrs': 'Delete ad attributes for a user',
    }
}
