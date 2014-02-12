# -*- coding: utf-8 -*-

# Copyright 2006-2009 University of Oslo, Norway
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
from Cerebrum.modules import Email
from Cerebrum.modules.no.nih import bofhd_nih_help
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.no import fodselsnr

def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

class BofhdExtension(BofhdCommonMethods):
    OU_class = Utils.Factory.get('OU')
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')
    all_commands = {}
    external_id_mappings = {}

    copy_commands = (
        #
        # copy relevant access-cmds and util methods
        #
        'access_disk', 'access_group', 'access_ou', 'access_user',
        'access_global_group', 'access_global_ou', '_list_access',
        'access_grant', 'access_revoke', '_manipulate_access',
        '_get_access_id', '_validate_access', '_get_access_id_disk',
        '_validate_access_disk', '_get_access_id_group', '_validate_access_group',
        '_get_access_id_global_group', '_validate_access_global_group',
        '_get_access_id_ou', '_validate_access_ou', '_get_access_id_global_ou',
        '_validate_access_global_ou', 'access_list_opsets', 'access_show_opset',
        'access_list', '_get_auth_op_target', '_grant_auth', '_revoke_auth',
        '_get_opset',
        #
        # copy relevant e-mail-cmds and util methods
        #
        'email_info', 'email_update', 'email_mod_name', 
        '_email_info_spam', '_email_info_filters', '_email_info_contact_info',
        '_email_info_forwarding', '_split_email_address',
        '_email_info_mailman', '_email_info_multi', '_email_info_file',
        '_email_info_pipe', '_email_info_forward', 'email_reassign_address',
        'email_add_address', '_get_email_domain', 'email_remove_address',
        '_split_email_address', '_remove_email_address',
        #
        # copy relevant group-cmds and util methods
        #
        'group_add', 'group_gadd', '_group_add', '_group_add_entity',
        '_group_count_memberships', 'group_add_entity',
        'group_delete', 'group_remove', 'group_gremove', '_group_remove',
        '_group_remove_entity', 'group_remove_entity', 'group_info',
        'group_list', 'group_list_expanded', 'group_search', 'group_set_description',
        'group_memberships', '_get_group', '_get_group_opcode', '_fetch_member_names',
        #
        # copy relevant misc-cmds and util methods
        #
        'misc_affiliations', 'misc_check_password', 'misc_clear_passwords',
        'misc_verify_password',
        #
        # copy relevant ou-cmds and util methods
        #
        'ou_search', 'ou_info', 'ou_tree',
        #
        # copy trait-functions
        #
        'trait_info', 'trait_list', 'trait_remove', 'trait_set',
        #
        # copy relevant person-cmds and util methods
        #
        'person_accounts', 'person_affiliation_add',
        '_person_affiliation_add_helper', 
        '_person_create_externalid_helper',
        'person_affiliation_remove', 'person_create',
        'person_clear_name', 'person_clear_id',
        'person_find', 'person_info', 'person_list_user_priorities',
        'person_set_user_priority', 'person_set_name', 'person_set_id',
        #
        # copy relevant quarantine-cmds and util methods
        #
        'quarantine_disable', 'quarantine_list', 'quarantine_remove',
        'quarantine_set', 'quarantine_show',
        #
        # copy relevant user-cmds and util methods
        #
        'user_affiliation_add', '_user_affiliation_add_helper',
        'user_affiliation_remove', 'user_history', 'user_info',
        'user_find', 'user_password', 'user_set_expire',
        '_user_create_prompt_func_helper', 'user_create_basic_prompt_func',
        '_user_create_set_account_type',
        'user_set_owner', 'user_set_owner_prompt_func', 'user_reserve',
        #
        # copy relevant spread-cmds and util methods
        #
        'spread_list', 'spread_add', 'spread_remove',
        #
        # copy relevant helper-functions
        #
        '_find_persons', '_format_ou_name', '_get_person', '_get_disk',
        '_map_person_id', '_entity_info', 'num2str', '_get_affiliationid',
        '_get_affiliation_statusid', '_parse_date', '_today', 'entity_history',
        '_format_changelog_entry', '_format_from_cl', '_get_group_opcode',
        '_get_constant', '_is_yes', '_remove_auth_target',
        '_remove_auth_role', '_get_cached_passwords', '_parse_date_from_to',
        '_convert_ticks_to_timestamp', '_get_account', '_get_entity',
        )

    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uio_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
             UiOBofhdExtension

        non_all_cmds = ('num2str', 'user_set_owner_prompt_func',
                        'user_create_basic_prompt_func',)
        for func in BofhdExtension.copy_commands:
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in non_all_cmds:
                BofhdExtension.all_commands[func] = UiOBofhdExtension.all_commands[func]
        x = object.__new__(cls)
        return x

    def __init__(self, server, default_zone='nih'):
        super(BofhdExtension, self).__init__(server)
        self.server = server
        self.logger = server.logger
        self.util = server.util
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.ba = BofhdAuth(self.db)

        # From uio
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
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
        # Copy in all defined commands from the superclass that is not defined
        # in this class.
        for key, cmd in super(BofhdExtension, self).all_commands.iteritems():
            if not self.all_commands.has_key(key):
                self.all_commands[key] = cmd

    def get_help_strings(self):
        return (bofhd_nih_help.group_help,
                bofhd_nih_help.command_help,
                bofhd_nih_help.arg_help)
    
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


    # person student_info
    #
    all_commands['person_student_info'] = Command(
        ("person", "student_info"), PersonId(),
        fs=FormatSuggestion([
        ("Studieprogrammer: %s, %s, %s, %s, tildelt=%s->%s privatist: %s",
         ("studprogkode", "studieretningkode", "studierettstatkode", "studentstatkode", 
	  format_day("dato_tildelt"), format_day("dato_gyldig_til"), "privatist")),
        ("Eksamensmeldinger: %s (%s), %s",
         ("ekskode", "programmer", format_day("dato"))),
        ("Utd. plan: %s, %s, %d, %s",
         ("studieprogramkode", "terminkode_bekreft", "arstall_bekreft",
          format_day("dato_bekreftet"))),
        ("Semesterreg: %s, %s, FS bet. reg: %s, endret: %s",
         ("regformkode", "betformkode", format_day("dato_endring"),
          format_day("dato_regform_endret")))
        ]),
        perm_filter='can_get_student_info')
    def person_student_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_get_student_info(operator.get_entity_id(), person)
        fnr = person.get_external_id(id_type=self.const.externalid_fodselsnr,
                                     source_system=self.const.system_fs)
        if not fnr:
            raise CerebrumError("No matching fnr from FS")
        fodselsdato, pnum = fodselsnr.del_fnr(fnr[0]['external_id'])
        har_opptak = {}
        ret = []
        try:
            fs_db = Factory.get("FS")()
        except Database.DatabaseError, e:
            self.logger.warn("Can't connect to FS (%s)" % e)
            raise CerebrumError("Can't connect to FS, try later")
        for row in fs_db.student.get_studierett(fodselsdato, pnum):
            har_opptak["%s" % row['studieprogramkode']] = \
                            row['status_privatist']
            ret.append({'studprogkode': row['studieprogramkode'],
                        'studierettstatkode': row['studierettstatkode'],
                        'studentstatkode': row['studentstatkode'],
			'studieretningkode': row['studieretningkode'],
                        'dato_tildelt': self._convert_ticks_to_timestamp(row['dato_studierett_tildelt']),
                        'dato_gyldig_til': self._convert_ticks_to_timestamp(row['dato_studierett_gyldig_til']),
                        'privatist': row['status_privatist']})

        for row in fs_db.student.get_eksamensmeldinger(fodselsdato, pnum):
            programmer = []
            for row2 in fs_db.info.get_emne_i_studieprogram(row['emnekode']):
                if har_opptak.has_key("%s" % row2['studieprogramkode']):
                    programmer.append(row2['studieprogramkode'])
            ret.append({'ekskode': row['emnekode'],
                        'programmer': ",".join(programmer),
                        'dato': self._convert_ticks_to_timestamp(row['dato_opprettet'])})
                      
        for row in fs_db.student.get_utdanningsplan(fodselsdato, pnum):
            ret.append({'studieprogramkode': row['studieprogramkode'],
                        'terminkode_bekreft': row['terminkode_bekreft'],
                        'arstall_bekreft': row['arstall_bekreft'],
                        'dato_bekreftet': self._convert_ticks_to_timestamp(row['dato_bekreftet'])})

        for row in fs_db.student.get_semreg(fodselsdato, pnum):
            ret.append({'regformkode': row['regformkode'],
                        'betformkode': row['betformkode'],
                        'dato_endring': self._convert_ticks_to_timestamp(row['dato_endring']),
                        'dato_regform_endret': self._convert_ticks_to_timestamp(row['dato_regform_endret'])})
        return ret

    # misc list_passwords
    #
    all_commands['misc_list_passwords'] = Command(
        ("misc", "list_passwords"),
        fs=FormatSuggestion("%-8s %-20s %s", ("account_id", "operation", "password"),
                            hdr="%-8s %-20s %s" % ("Id", "Operation", "Password")))
    def misc_list_passwords(self, operator):
        ret = self._get_cached_passwords(operator)
        if not ret:
            return "Password cache for this session is empty."
        return ret

    # user create prompt
    #
    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)    
    
    # user create
    #
    # FIXME: we should be able to use uio's user create her
    #
    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='is_superuser')
    def user_create(self, operator, *args):
        if args[0].startswith('group:'):
            group_id, np_type, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")
            affiliation = None
            owner_type = self.const.entity_group
        else:
            if len(args) == 4:
                idtype, person_id, affiliation, uname = args
            else:
                idtype, person_id, yes_no, affiliation, uname = args
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
        for spread in cereconf.BOFHD_NEW_USER_SPREADS:
            account.add_spread(self.const.Spread(spread))
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
    
    # user delete
    #
    all_commands['user_delete'] = Command(
        ("user", "delete"), AccountName(), perm_filter='can_delete_user')
    def user_delete(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError, "User is already deleted"
        account.expire_date = mx.DateTime.now()
        for s in account.get_spread():
            account.delete_spread(int(s['spread']))
        account.write_db()
        return "User %s queued for deletion immediately" % account.account_name

    # helpers needed for email_info, cannot be copied in the usual way
    #
    def __get_valid_email_addrs(self, et, special=False, sort=False):
        """Return a list of all valid e-mail addresses for the given
        EmailTarget.  Keep special domain names intact if special is
        True, otherwise re-write them into real domain names."""
        addrs = [(r['local_part'], r['domain'])       
                 for r in et.get_addresses(special=special)]
        if sort:
            addrs.sort(lambda x,y: cmp(x[1], y[1]) or cmp(x[0],y[0]))
        return ["%s@%s" % a for a in addrs]

    def __get_email_target_and_address(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the address object.  If there is no at-sign
        in address, assume it is an account name and return primary
        address.  Raises CerebrumError if address is unknown.
        """
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        if address.count('@') == 0:
            acc = self.Account_class(self.db)
            try:
                acc.find_by_name(address)
                # FIXME: We can't use Account.get_primary_mailaddress
                # since it rewrites special domains.
                et = Email.EmailTarget(self.db)
                et.find_by_target_entity(acc.entity_id)
                epa = Email.EmailPrimaryAddressTarget(self.db)
                epa.find(et.entity_id)
                ea.find(epa.email_primaddr_id)
            except Errors.NotFoundError:
                raise CerebrumError, ("No such address: '%s'" % address)
        elif address.count('@') == 1:
            try:
                ea.find_by_address(address)
                et.find(ea.email_addr_target_id)
            except Errors.NotFoundError:
                raise CerebrumError, "No such address: '%s'" % address
        else:
            raise CerebrumError, "Malformed e-mail address (%s)" % address
        return et, ea

    def __get_email_target_and_account(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et, ea = self.__get_email_target_and_address(address)
        acc = None
        if et.email_target_type in (self.const.email_target_account,
                                    self.const.email_target_deleted):
            acc = self._get_account(et.email_target_entity_id, idtype='id')
        return et, acc
    
    def __get_address(self, etarget):
        """The argument can be
        - EmailPrimaryAddressTarget
        - EmailAddress
        - EmailTarget (look up primary address and return that, throw
        exception if there is no primary address)
        - integer (use as entity_id and look up that target's
        primary address)
        The return value is a text string containing the e-mail
        address.  Special domain names are not rewritten."""
        ea = Email.EmailAddress(self.db)
        if isinstance(etarget, (int, long, float)):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            # may throw exception, let caller handle it
            epat.find(etarget)
            ea.find(epat.email_primaddr_id)
        elif isinstance(etarget, Email.EmailTarget):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            epat.find(etarget.entity_id)
            ea.find(epat.email_primaddr_id)
        elif isinstance(etarget, Email.EmailPrimaryAddressTarget):
            ea.find(etarget.email_primaddr_id)
        elif isinstance(etarget, Email.EmailAddress):
            ea = etarget
        else:
            raise ValueError, "Unknown argument (%s)" % repr(etarget)
        ed = Email.EmailDomain(self.db)
        ed.find(ea.email_addr_domain_id)
        return ("%s@%s" % (ea.email_addr_local_part,
                           ed.email_domain_name))

    def _email_info_detail(self, acc):
        info = []
        try:
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            homemdb = None
            tmp = acc.get_trait(self.const.trait_exchange_mdb)
            if tmp != None:
                homemdb = tmp['strval']
            else:
                homemdb = 'N/A'
            # should not be shown for accounts without exchange-spread, needs fixin', Jazz 2011-02-21
            info.append({'homemdb': homemdb})
        except Errors.NotFoundError:
            pass
        return info
    
    def _email_info_basic(self, acc, et):
        info = {}
        data = [ info ]
        if (et.email_target_type not in (self.const.email_target_Mailman,
                                         self.const.email_target_Sympa) and
            et.email_target_alias is not None):
            info['alias_value'] = et.email_target_alias
        info["account"] = acc.account_name
        info["server"] = 'Mail server'
        info["server_type"] = 'Microsoft Exchange'
        return data
    
    def _email_info_account(self, operator, acc, et, addrs):
        self.ba.can_email_info(operator.get_entity_id(), acc)
        ret = self._email_info_basic(acc, et)
        try:
            self.ba.can_email_info_detail(operator.get_entity_id(), acc)
        except PermissionDenied:
            pass
        else:
            # spam settings, forwarding and filters are not used at
            # NIH for now
            #ret += self._email_info_spam(et)
            #ret += self._email_info_forwarding(et, addrs)
            #ret += self._email_info_filters(et)
            ret += self._email_info_detail(acc)            
        return ret

    # email set_primary_address account lp@dom
    #
    all_commands['email_set_primary_address'] = Command(
        ("email", "set_primary_address"),
        AccountName(help_ref="account_name", repeat=False),
        EmailAddress(help_ref='email_address', repeat=False),
        perm_filter='is_superuser')
    def email_set_primary_address(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        ea = Email.EmailAddress(self.db)
        if address == '':
            return "Primary address cannot be an empty string!"
        lp, dom = address.split('@')
        ed = self._get_email_domain(dom)
        ea.clear()
        try:
            ea.find_by_address(address)
            if ea.email_addr_target_id != et.entity_id:
                raise CerebrumError, "Address (%s) is in use by another user" % address
        except Errors.NotFoundError:
            pass
        ea.populate(lp, ed.entity_id, et.entity_id)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        epat.clear()
        try:
            epat.find(ea.email_addr_target_id)
            epat.populate(ea.entity_id)
        except Errors.NotFoundError:
            epat.clear()
            epat.populate(ea.entity_id, parent = et)
        epat.write_db()
        return "Registered %s as primary address for %s" % (address, uname)
