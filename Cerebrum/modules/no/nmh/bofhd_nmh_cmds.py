# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
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
        # copy relevant person-cmds and util methods
        #
        'person_accounts', 'person_affiliation_add',
        '_person_affiliation_add_helper',
        'person_affiliation_remove', 'person_create',
        'person_find', 'person_info', 'person_list_user_priorities',
        'person_set_user_priority', 'person_set_name', 'person_clear_id',
        'person_clear_name',
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
        'user_set_owner', 'user_set_owner_prompt_func',
        #
        # copy relevant spread-cmds and util methods
        #
        'spread_list', 'spread_add', 'spread_remove',
        #
        # copy relevant mail-cmds and util methods
        #
        '_split_email_address',
        #
        # copy relevant helper-functions
        #
         '_find_persons', '_get_account', '_format_ou_name',
        '_get_person', '_get_disk', '_get_group', '_map_person_id', '_get_entity',
        '_entity_info', 'num2str', '_get_affiliationid',
        '_get_affiliation_statusid', '_parse_date', '_today', 'entity_history',
        '_format_changelog_entry', '_format_from_cl',
        '_get_entity_name', '_get_group_opcode', '_get_name_from_object',
        '_get_constant', '_is_yes', '_remove_auth_target',
        '_remove_auth_role', '_get_cached_passwords', '_parse_date_from_to',
        '_convert_ticks_to_timestamp'
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

    def __init__(self, server, default_zone='nmh'):
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
