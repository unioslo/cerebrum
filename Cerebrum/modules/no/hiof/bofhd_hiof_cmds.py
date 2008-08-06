# -*- coding: iso-8859-1 -*-

# Copyright 2007-2008 University of Oslo, Norway
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



import mx
import pickle

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum import Database

from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.no.nmh import bofhd_nmh_help
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules import Email
from Cerebrum.modules.no.hiof import ADMappingRules

def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

class BofhdExtension(object):
    OU_class = Utils.Factory.get('OU')
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')
    all_commands = {}

    copy_commands = (
        #
        # copy relevant user_create related methods
        #
        '_find_persons', '_get_person', '_get_account', '_get_ou',
        '_format_ou_name', '_user_create_set_account_type','_get_group',
        '_get_constant', '_parse_date',
        )
        
    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uio_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
             UiOBofhdExtension

        non_all_cmds = ('num2str', 'user_create_basic_prompt_func',)
        for func in BofhdExtension.copy_commands:
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in non_all_cmds:
                BofhdExtension.all_commands[func] = UiOBofhdExtension.all_commands[func]
        x = object.__new__(cls)
        return x

    def __init__(self, server, default_zone='hiof'):
        self.server = server
        self.logger = server.logger
        self.util = server.util
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.ou = Factory.get('OU')(self.db)
        self.ba = BofhdAuth(self.db)

        # From uio
        self.num2const = {}
        self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const[str(tmp)] = tmp
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)

    def get_help_strings(self):
        return (bofhd_nmh_help.group_help,
                bofhd_nmh_help.command_help,
                bofhd_nmh_help.arg_help)
    
    def get_commands(self, account_id):
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for k in self.all_commands.keys():
            tmp = self.all_commands[k]
            if tmp is not None:
                if tmp.perm_filter:
                    if not getattr(self.ba, tmp.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

    def _user_get_ad_traits(self, account):
        """
        Utility function for methods user_*

        Get all ad_traits for a user. 
        """
        ret = []
        traits = account.get_traits()
        relevant_traits = [self.const.trait_ad_homedir,
                           self.const.trait_ad_profile_path,
                           self.const.trait_ad_account_ou]
        for trait_const_class, entity_trait in traits.iteritems():
            if trait_const_class in relevant_traits:
                ret.append((trait_const_class, entity_trait))
        return ret

    # user delete_ad_attrs
    all_commands['user_delete_ad_attrs'] = Command(
        ('user', 'delete_ad_attrs'), AccountName(), Spread(),
        perm_filter='is_superuser')
    def user_delete_ad_attrs(self, operator, uname, spread):
        """
        Bofh command user delete_ad_attrs

        Delete AD values home, profile_path and ou for user in the AD
        domain given by spread.
        AD values are stored as a spread -> value mapping in an entity
        trait in Cerebrum.

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
        for trait_const_class, entity_trait in self._user_get_ad_traits(account):
            unpickle_val = pickle.loads(str(entity_trait['strval']))
            for u in unpickle_val.keys():
                if self._get_constant(self.const.Spread, u, 'spread') == spread:
                    account.delete_trait(entity_trait['code'])
        return "OK, removed AD-traits for %s" % uname

    # user list_ad_attrs
    all_commands['user_list_ad_attrs'] = Command(
        ('user', 'list_ad_attrs'), AccountName(),
        perm_filter='is_superuser', fs=FormatSuggestion(
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
        for trait_const_class, entity_trait in self._user_get_ad_traits(account):
            unpickle_val = pickle.loads(str(entity_trait['strval']))
            for spread, ad_val in unpickle_val.items():
                ret.append({'spread': str(self._get_constant(self.const.Spread, spread, 'spread')),
                            'ad_attr': str(trait_const_class),
                            'ad_val': ad_val})
        return ret

    # def _get_ad_rules(self, spread):
    #     if spread == self.const.spread_ad_account_fag:
    #         rules = ADMappingRules.Fag()
    #     elif spread == self.const.spread_ad_account_adm:
    #         rules = ADMappingRules.Adm()
    #     elif spread == self.const.spread_ad_account_stud:
    #         rules = ADMappingRules.Student()    
    #     return rules

    # def _get_ou_sko(self, ou_id):
    #     self.ou.clear()
    #     self.ou.find(ou_id)
    #     return "%d%02d%02d" % (self.ou.fakultet, self.ou.institutt, self.ou.avdeling)

    # # user verify_ad_attrs
    # all_commands['user_verify_ad_attrs'] = Command(
    #     ('user', 'verify_ad_attrs'), AccountName(), Spread(),
    #     perm_filter='is_superuser')
    # def user_verify_ad_attrs(self, operator, uname, spread):
    #     """
    #     Check what AD attributes a user should have in a domain
    #     according to affiliation and spread.
    #     """
    #     account = self._get_account(uname, idtype='name')
    #     spread = self._get_constant(self.const.Spread, spread)
    #     # We can't calculate AD attributes for students without first
    #     # parsing /cerebrum/dumps/FS/studieprog.xml
    #     if spread == self.const.spread_ad_account_stud:
    #         return "Not yet implemented for spread stud"
    #     # Get affiliations
    #     affs = account.get_account_types()
    #     if not affs:
    #         raise CerebrumError(
    #             "Cannot calculate ad attrs for user without affiliation")
    #     # TBD: what to do if more than one aff? For now, use aff with
    #     # highest priority
    #     sko = self._get_ou_sko(affs[0]['ou_id'])
    #     rules = self._get_ad_rules(spread)
    #     dn = rules.getDN(sko, uname)
    #     return '\n'.join(
    #         ["%12s: %s" % ("OU", dn[dn.find(',')+1:]), # OU part of DN
    #          "%12s: %s" % ("Profile Path", rules.getProfilePath(sko, uname)),
    #          "%12s: %s" % ("Homedir", rules.getHome(sko, uname))])

    # def _user_set_ad_trait(self, uname, spread, trait_const, ad_val):
    #     """
    #     Utility function for methods user_set_ad_*
    # 
    #     Set new spread -> AD value mapping as an entity trait for
    #     user. Do some sanity checks, log relevant info and raise
    #     CerebrumError if something goes wrong.
    # 
    #     @type  uname: string
    #     @param uname: user name of account which AD value should be
    #                   set
    #     @type  spread: string
    #     @param spread: code_str of spread
    #     @type  trait_const: trait constant (_EntityTraitCode)
    #     @param trait_const: trait constant which type indicates which
    #                         type of AD value that should be set
    #     @return: None
    #     """
    #     account = self._get_account(uname, idtype='name')
    #     spread = self._get_constant(self.const.Spread, spread)
    #     if not account.has_spread(spread):
    #         raise CerebrumError, "User hasn't spread %s. Can't set ad_trait" % spread
    #     try:
    #         trait = account.get_trait(trait_const)
    #         if trait:
    #             # user already has a ad_trait of that type. The trait
    #             # is stored as a pickled dict (spread -> ad value
    #             # mapping). Just change for the specified spread.
    #             ad_trait = pickle.loads(str(trait['strval']))
    #         else:
    #             # No trait of type trait_const for this user. Set new dict
    #             ad_trait = {}
    #         ad_trait[int(spread)] = ad_val
    #         account.populate_trait(trait_const, strval=pickle.dumps(ad_trait))
    #         account.write_db()
    #     except:
    #         self.logger.exception("Error setting trait of type %s for %s" % (
    #             trait_const, uname))
    #         raise CerebrumError, "Couldn't set ad_trait for user %s" % uname
    #
    # # user set_ad_home
    # all_commands['user_set_ad_home'] = Command(
    #     ('user', 'set_ad_home'), AccountName(), Spread(), SimpleString(),
    #     perm_filter='is_superuser')
    # def user_set_ad_home(self, operator, uname, spread, ad_home):
    #     """
    #     Bofh command user set_ad_home
    # 
    #     Set new value for ad_home in Cerebrum. The value represent the
    #     AD variable homedir in AD domain indicated by spread.
    #     
    #     @param operator: operator in bofh session
    #     @type  uname: string
    #     @param uname: user name of account which AD values should be
    #                   deleted. Given by operator
    #     @type  spread: string
    #     @param spread: code_str of spread. Given by operator
    #     @type  ad_home: string
    #     @param ad_home: New value for ad_home. Given by operator
    #     @rtype: string
    #     @return: OK message if success
    #     """
    #     self._user_set_ad_trait(uname, spread,
    #                             self.const.trait_ad_homedir, ad_home)
    #     return "OK, new ad_home set for user %s" % uname
    # 
    # # user set_ad_ou
    # all_commands['user_set_ad_ou'] = Command(
    #     ('user', 'set_ad_ou'), AccountName(), Spread(), SimpleString(),
    #     perm_filter='is_superuser')
    # def user_set_ad_ou(self, operator, uname, spread, ad_ou):
    #     """
    #     Bofh command user set_ad_ou
    # 
    #     Set new value for ad_ou in Cerebrum. The value represent the
    #     AD variable OU in AD domain indicated by spread.
    #     
    #     @param operator: operator in bofh session
    #     @type  uname: string
    #     @param uname: user name of account which AD values should be
    #                   deleted. Given by operator
    #     @type  spread: string
    #     @param spread: code_str of spread. Given by operator
    #     @type  ad_ou: string
    #     @param ad_ou: New value for ad_ou. Given by operator
    #     @rtype: string
    #     @return: OK message if success
    #     """
    #     self._user_set_ad_trait(uname, spread,
    #                             self.const.trait_ad_account_ou, ad_ou)
    #     return "OK, new ad_ou set for user %s" % uname
    # 
    # # user set_ad_profile
    # all_commands['user_set_ad_profile'] = Command(
    #     ('user', 'set_ad_profile'), AccountName(), Spread(), SimpleString(),
    #     perm_filter='is_superuser')
    # def user_set_ad_profile(self, operator, uname, spread, ad_profile):
    #     """
    #     Bofh command user set_ad_profile
    # 
    #     Set new value for ad_profile in Cerebrum. The value represent
    #     the AD variable Profile Path in AD domain indicated by spread.
    #     
    #     @param operator: operator in bofh session
    #     @type  uname: string
    #     @param uname: user name of account which AD values should be
    #                   deleted. Given by operator
    #     @type  spread: string
    #     @param spread: code_str of spread. Given by operator
    #     @type  ad_profile: string
    #     @param ad_profile: New value for ad_profile. Given by operator
    #     @rtype: string
    #     @return: OK message if success
    #     """
    #     self._user_set_ad_trait(uname, spread,
    #                             self.const.trait_ad_profile_path, ad_profile)
    #     return "OK, new ad_profile set for user %s" % uname
    
    # user create prompt
    #
    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)
    
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
                         person.get_name(self.const.system_cached, self.const.name_full)),
                        int(c[i]['person_id'])))
                if not len(map) > 1:
                    raise CerebrumError, "No persons matched"
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
                    raise CerebrumError, "Command aborted at user request"
            if not all_args:
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s@%s" % (
                        self.const.PersonAffStatus(aff['status']),
                        self._format_ou_name(ou))
                    map.append((("%s", name),
                                {'ou_id': int(aff['ou_id']), 'aff': int(aff['affiliation'])}))
                if not len(map) > 1:
                    raise CerebrumError(
                        "Person has no affiliations. Try person affiliation_add")
                return {'prompt': "Choose affiliation from list", 'map': map}
            affiliation = all_args.pop(0)
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type'}
            np_type = all_args.pop(0)
        if not all_args:
            return {'prompt': "Enter spread",
                    'help_ref': 'string_spread'}
        spread = all_args.pop(0)
        if not all_args:
            return {'prompt': "Enter e-mail server name",
                    'help_ref': 'string_email_host'}
        email_server = all_args.pop(0)
        if not all_args:
            ret = {'prompt': "Username", 'last_arg': True}
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    fname, lname = [
                        person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last) ]
                    sugg = account.suggest_unames(self.const.account_namespace, fname, lname)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret    
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError, "Too many arguments"

    # user create
    #
    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
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
                idtype, person_id, affiliation, spread, email_server, uname = args
            else:
                idtype, person_id, yes_no, affiliation, spread, email_server, uname = args
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
            account.add_spread(self.const.Spread(spread))
        account.write_db()
        account._update_email_server(email_server)
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        try:
            account.write_db()
            if affiliation is not None:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(
                    account, person.entity_id, ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(account.entity_id),
                                                    'password': passwd})
        return {'account_id': int(account.entity_id)}
