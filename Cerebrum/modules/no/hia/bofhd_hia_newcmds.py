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
import time
import os
import sys
import string

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum import Database

from Cerebrum.modules import Email
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.no.uio import bofhd_uio_help
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.no import fodselsnr
from mx import DateTime
from Cerebrum.modules.no.hia.access_FS import FS
from Cerebrum.modules.templates.letters import TemplateHandler

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
        'group_add', 'group_gadd', 'group_padd', '_group_add', '_group_add_entity',
        '_group_count_memberships', 'group_add_entity', 'group_create',
        'group_def', 'group_delete', 'group_remove', 'group_gremove',
        '_group_remove', '_group_remove_entity', 'group_remove_entity',
        'group_demote_posix', 'group_promote_posix', 'group_info',
        'group_list', 'group_list_expanded', 'group_search', 'group_set_description',
        'group_memberships', '_get_group', '_get_group_opcode',
        'group_personal', 'group_set_expire', 'group_set_visibility',
        #
        # copy relevant misc-cmds and util methods
        #
        'misc_affiliations', 'misc_check_password', 'misc_clear_passwords',
        'misc_stedkode', 'misc_verify_password', 'misc_cancel_request',
        'misc_list_requests', '_map_template', '_parse_range',
        # 'misc_list_passwords_prompt_func',
        # 'misc_list_passwords',
        #
        # copy relevant person-cmds and util methods
        #
        'person_accounts', 'person_affiliation_add',
        '_person_affiliation_add_helper',
        'person_affiliation_remove', 'person_create',
        'person_find', 'person_info', 'person_list_user_priorities',
        'person_set_user_priority', 'person_set_name',
        'person_clear_name', 'person_clear_id', 'person_set_bdate',
        'person_set_id',
        #
        # copy relevant quarantine-cmds and util methods
        #
        'quarantine_disable', 'quarantine_list', 'quarantine_remove',
        'quarantine_set', 'quarantine_show',
        #
        # copy relevant user-cmds and util methods
        #
        'user_affiliation_add', '_user_affiliation_add_helper',
        'user_affiliation_remove', 'user_history',
        'user_find', 'user_password', 'user_set_expire',
        'user_reserve', 'user_gecos', 'user_promote_posix', 'user_demote_posix',
        'user_set_np_type', 'user_shell', 'user_set_disk_status',
        '_user_create_set_account_type', '_get_shell',
        'user_set_owner', 'user_set_owner_prompt_func',
        #
        # copy relevant spread-cmds and util methods
        #
        'spread_list', 'spread_add', 'spread_remove',
        #
        # copy relevant email-functions and util methods
        #
        'email_add_address', 'email_remove_address', '_remove_email_address',
        'email_add_filter', 'email_remove_filter', 'email_create_list_alias',
        'email_remove_list_alias', 'email_spam_action', 'email_spam_level',
        'email_reassign_address', 'email_forward', 'email_add_forward',
        'email_remove_forward','_check_email_address', '_forward_exists',
        'email_info', '_email_info_account', '_email_info_basic', '_email_info_spam',
        '_email_info_filters', '_email_info_forwarding', '_split_email_address',
        '_email_info_mailman', '_email_info_multi', '_email_info_file',
        '_email_info_pipe', '_email_info_forward', 'email_create_domain',
        'email_domain_configuration', 'email_domain_info', 'email_add_domain_affiliation',
        'email_remove_domain_affiliation', 'email_create_forward', 'email_create_list',
        'email_delete_list', 'email_quota', 'email_tripnote',
        'email_list_tripnotes', 'email_add_tripnote', 'email_remove_tripnote',
        'email_update', '_get_email_domain', '_onoff', '_register_list_spam_settings',
        '_register_list_filter_settings', '_find_tripnote', '_sync_category',
        '_has_category', '_update_email_for_ou', '_is_ok_mailman_name',
        '_register_list_addresses', '_email_delete_list', '_check_mailman_official_name',
        '_get_mailman_list',
        #
        # copy relevant helper-functions
        #
         '_find_persons', '_get_account', '_get_ou', '_format_ou_name',
        '_get_person', '_get_disk', '_get_group', '_map_person_id', '_get_entity',
         '_get_boolean', '_entity_info', 'num2str', '_get_affiliationid',
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

        non_all_cmds = ('num2str', 'user_set_owner_prompt_func',)
        for func in BofhdExtension.copy_commands:
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in non_all_cmds:
                BofhdExtension.all_commands[func] = UiOBofhdExtension.all_commands[func]
        x = object.__new__(cls)
        return x

    def __init__(self, server, default_zone='uia'):
        self.server = server
        self.logger = server.logger
        self.util = server.util
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
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
        return (bofhd_uio_help.group_help,
                bofhd_uio_help.command_help,
                bofhd_uio_help.arg_help)
    
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
                et.find_by_entity(acc.entity_id)
                epa = Email.EmailPrimaryAddressTarget(self.db)
                epa.find(et.email_target_id)
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
        - integer (use as email_target_id and look up that target's
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
            epat.find(etarget.email_target_id)
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
        eq = Email.EmailQuota(self.db)
        try:
            eq.find_by_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
            used = 'N/A'
            limit = None
            info.append({'quota_hard': eq.email_quota_hard,
                         'quota_soft': eq.email_quota_soft,
                         'quota_used': used})
            info.append({'dis_quota_hard': eq.email_quota_hard,
                         'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass
        return info

    # email move
    #
    all_commands['email_move'] = Command(
        ("email", "move"),
        AccountName(help_ref="account_name", repeat=True),
        SimpleString(help_ref='string_email_host'),
        perm_filter='can_email_move')
    def email_move(self, operator, uname, server):
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        et = Email.EmailTarget(self.db)
        et.find_by_entity(acc.entity_id)
        old_server = et.email_server_id
        es = Email.EmailServer(self.db)
        es.find_by_name(server)
        et.email_server_id = es.entity_id
        et.write_db()
        return "OK, updated e-mail server for %s (to %s)" % (uname, server)
    
    # mailman-stuff:
    _interface2addrs = {
        'post': ["%(local_part)s@%(domain)s"],
        'mailcmd': ["%(local_part)s-request@%(domain)s",
                    "%(local_part)s-confirm@%(domain)s",
                    "%(local_part)s-join@%(domain)s",
                    "%(local_part)s-leave@%(domain)s",
                    "%(local_part)s-subscribe@%(domain)s",
                    "%(local_part)s-unsubscribe@%(domain)s"],
        'mailowner': ["%(local_part)s-admin@%(domain)s",
                      "%(local_part)s-owner@%(domain)s",
                      "%(local_part)s-bounces@%(domain)s"]
        }
    # These are just for show, UiA is not really using this
    _mailman_pipe = "|/fake %(interface)s %(listname)s"
    _mailman_patt = r'\|/fake (\S+) (\S+)$'
    
    # person student_info
    all_commands['person_student_info'] = Command(
        ("person", "student_info"), PersonId(),
        fs=FormatSuggestion([
        ("Studieprogrammer: %s, %s, %s, tildelt=%s->%s privatist: %s",
         ("studprogkode", "studierettstatkode", "status", format_day("dato_studierett_tildelt"),
          format_day("dato_studierett_gyldig_til"), "privatist")),
        ("Eksamensmeldinger: %s (%s), %s",
         ("ekskode", "programmer", format_day("dato"))),
        ("Utd. plan: %s, %s, %d, %s",
         ("studieprogramkode", "terminkode_bekreft", "arstall_bekreft",
          format_day("dato_bekreftet"))),
        ("Semesterreg: %s, %s, betalt: %s, endret: %s",
         ("regformkode", "betformkode", format_day("dato_betaling"),
          format_day("dato_regform_endret"))),
        ("Kull: %s, (%s)", ("kullkode", "status_aktiv"))
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
        db = Database.connect(user="cerebrum", service="FSUIA.uio.no",
                              DB_driver='Oracle')
        fs = FS(db)
        for row in fs.student.get_studierett(fodselsdato, pnum):
            har_opptak["%s" % row['studieprogramkode']] = \
			    row['status_privatist']
            ret.append({'studprogkode': row['studieprogramkode'],
                        'studierettstatkode': row['studierettstatkode'],
                        'status': row['studentstatkode'],
                        'dato_studierett_tildelt': DateTime.DateTimeFromTicks(row['dato_studierett_tildelt']),
                        'dato_studierett_gyldig_til': DateTime.DateTimeFromTicks(row['dato_studierett_gyldig_til']),
                        'privatist': row['status_privatist']})

        for row in fs.student.get_eksamensmeldinger(fodselsdato, pnum):
            programmer = []
            for row2 in fs.info.get_emne_i_studieprogram(row['emnekode']):
                if har_opptak.has_key("%s" % row2['studieprogramkode']):
                    programmer.append(row2['studieprogramkode'])
            ret.append({'ekskode': row['emnekode'],
                        'programmer': ",".join(programmer),
                        'dato': DateTime.DateTimeFromTicks(row['dato_opprettet'])})
                      
        for row in fs.student.get_utdanningsplan(fodselsdato, pnum):
            ret.append({'studieprogramkode': row['studieprogramkode'],
                        'terminkode_bekreft': row['terminkode_bekreft'],
                        'arstall_bekreft': row['arstall_bekreft'],
                        'dato_bekreftet': DateTime.DateTimeFromTicks(row['dato_bekreftet'])})

        for row in fs.student.get_semreg(fodselsdato, pnum):
            ret.append({'regformkode': row['regformkode'],
                        'betformkode': row['betformkode'],
                        'dato_betaling': DateTime.DateTimeFromTicks(row['dato_betaling']),
                        'dato_regform_endret': DateTime.DateTimeFromTicks(row['dato_regform_endret'])})

	for row in fs.student.get_student_kull(fodselsdato, pnum):
	    ret.append({'kullkode': "%s-%s-%s" % (row['studieprogramkode'], row['terminkode_kull'], row['arstall_kull']),
			'status_aktiv': row['status_aktiv']})

        db.close()
        return ret

    # user home_create (set extra home per spread for a given account)
    #
    all_commands['user_home_create'] = Command(
	("user", "home_create"), AccountName(), Spread(), DiskId(), perm_filter='can_create_user')
    def user_home_create(self, operator, accountname, spread, disk):
	account = self._get_account(accountname)
        disk_id, home = self._get_disk(disk)[1:3]
        homedir_id = None
        home_spread = False
        for s in cereconf.HOME_SPREADS:
            if spread == str(getattr(self.const, s)):
                home_spread = True
                break
        if home is not None:
            if home[0] == ':':
                home = home[1:]
            else:
                raise CerebrumError, "Invalid disk"
	self.ba.can_create_user(operator.get_entity_id(), account)
        is_posix = False
        try:
            self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            pass
        if not is_posix:
            raise CerebrumError("This user is not a posix user. Please use 'user promote_posix' first.")
        if not home_spread:
            raise CerebrumError, "Cannot assign home in a non-home spread!"
        if account.has_spread(int(self._get_constant(self.const.Spread, spread))):
	    try:
                if account.get_home(int(self._get_constant(self.const.Spread, spread))):
                    return "User already has a home in spread %s, use user move" % spread
	    except:
                homedir_id = account.set_homedir(disk_id=disk_id, home=home,
                                                 status=self.const.home_status_not_created)

	else:
	    account.add_spread(self._get_constant(self.const.Spread, spread))
	    homedir_id = account.set_homedir(disk_id=disk_id, home=home,
                                             status=self.const.home_status_not_created)
        account.set_home(int(self._get_constant(self.const.Spread, spread)), homedir_id)
        account.write_db()
        return "Home made for %s in spread %s" % (accountname, spread)
    
    # user info
    #
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion([("Username:      %s\n"+
                              "Spreads:       %s\n" +
                              "Affiliations:  %s\n" +
                              "Expire:        %s\n" +
                              "Home:          %s\n" +
                              "Entity id:     %i\n" +
                              "Owner id:      %i (%s: %s)",
                              ("username", "spread", "affiliations",
                               format_day("expire"),
                               "home", "entity_id", "owner_id",
                               "owner_type", "owner_desc")),
                             ("UID:           %i\n" +
                              "Default fg:    %i=%s\n" +
                              "Gecos:         %s\n" +
                              "Shell:         %s",
                              ('uid', 'dfg_posix_gid', 'dfg_name', 'gecos',
                               'shell')),
                             ("Quarantined:   %s",
                              ("quarantined",))]))
    def user_info(self, operator, accountname):
        is_posix = False
        try: 
            account = self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            account = self._get_account(accountname)
        if account.is_deleted() and not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError("User is deleted")
        affiliations = []
        for row in account.get_account_types(filter_expired=False):
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" %
                                (self.const.PersonAffiliation(row['affiliation']),
                                 self._format_ou_name(ou)))
        tmp = {'disk_id': None, 'home': None, 'status': None,
               'homedir_id': None}
        hm = []
        # fixme: UiA does not user home_status as per today. this should
        # probably be fixed
        # home_status = None
        home = None
        for spread in cereconf.HOME_SPREADS:
            try:
                tmp = account.get_home(getattr(self.const, spread))
                if tmp['disk_id'] or tmp['home']:
                    tmp_home = account.resolve_homedir(disk_id=tmp['disk_id'],
                                                       home=tmp['home'])
                #home_status = str(self.const.AccountHomeStatus(tmp['status']))
                hm.append("%s (%s)" % (tmp_home, str(getattr(self.const, spread))))
            except Errors.NotFoundError:
                pass
        home = ("\n" + (" " * 15)).join([x for x in hm])
        ret = {'entity_id': account.entity_id,
               'username': account.account_name,
               'spread': ",".join([str(self.const.Spread(a['spread']))
                                   for a in account.get_spread()]),
               'affiliations': (",\n" + (" " * 15)).join(affiliations),
               'expire': account.expire_date,
	       'home': home,
               'owner_id': account.owner_id,
               'owner_type': str(self.const.EntityType(account.owner_type))
               }
        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            try:
                p_name = person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME))
            except Errors.NotFoundError:
                p_name = '<none>'
            ret['owner_desc'] = p_name
        else:
            grp = self._get_group(account.owner_id, idtype='id')
            ret['owner_desc'] = grp.group_name

        if is_posix:
            group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            ret['uid'] = account.posix_uid
            ret['dfg_posix_gid'] = group.posix_gid
            ret['dfg_name'] = group.group_name
            ret['gecos'] = account.gecos
            ret['shell'] = str(self.const.PosixShell(account.shell))
        # TODO: Return more info about account
        quarantined = None
        now = DateTime.now()
        for q in account.get_entity_quarantine():
            if q['start_date'] <= now:
                if (q['end_date'] is not None and
                    q['end_date'] < now):
                    quarantined = 'expired'
                elif (q['disable_until'] is not None and
                    q['disable_until'] > now):
                    quarantined = 'disabled'
                else:
                    quarantined = 'active'
                    break
            else:
                quarantined = 'pending'
        if quarantined:
            ret['quarantined'] = quarantined
        return ret

    # misc list_passwords_prompt_func
    #
    def misc_list_passwords_prompt_func(self, session, *args):
        """  - Går inn i "vis-info-om-oppdaterte-brukere-modus":
  1 Skriv ut passordark
  1.1 Lister ut templates, ber bofh'er om å velge en
  1.1.[0] Spesifiser skriver (for template der dette tillates valgt av
          bofh'er)
  1.1.1 Lister ut alle aktuelle brukernavn, ber bofh'er velge hvilke
        som skal skrives ut ('*' for alle).
  1.1.2 (skriv ut ark/brev)
  2 List brukernavn/passord til skjerm
  """
        all_args = list(args[:])
        if not all_args:
            return {'prompt': "Velg#",
                    'map': [(("Alternativer",), None),
                            (("Skriv ut passordark",), "skriv"),
                            (("List brukernavn/passord til skjerm",), "skjerm")]}
        arg = all_args.pop(0)
        if(arg == "skjerm"):
            return {'last_arg': True}
        if not all_args:
            map = [(("Alternativer",), None)]
            n = 1
            for t in self._map_template():
                map.append(((t,), n))
                n += 1
            return {'prompt': "Velg template #", 'map': map,
                    'help_ref': 'print_select_template'}
        arg = all_args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(arg)
        if not all_args:
            n = 1
            map = [(("%8s %s", "uname", "operation"), None)]
            for row in self._get_cached_passwords(session):
                map.append((("%-12s %s", row['account_id'], row['operation']), n))
                n += 1
            if n == 1:
                raise CerebrumError, "no users"
            return {'prompt': 'Velg bruker(e)', 'last_arg': True,
                    'map': map, 'raw': True,
                    'help_ref': 'print_select_range',
                    'default': str(n-1)}

    # misc list_passwords
    #
    all_commands['misc_list_passwords'] = Command(
        ("misc", "list_passwords"), prompt_func=misc_list_passwords_prompt_func,
        fs=FormatSuggestion("%-8s %-20s %s", ("account_id", "operation", "password"),
                            hdr="%-8s %-20s %s" % ("Id", "Operation", "Password")))
    def misc_list_passwords(self, operator, *args):
        if args[0] == "skjerm":
            return self._get_cached_passwords(operator)
        args = list(args[:])
        args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(args.pop(0))
        skriver = None
	try:
            acc = self._get_account(operator.get_entity_id(), idtype='id')
	    opr=acc.account_name
        except Errors.NotFoundError:
	    raise CerebrumError, ("Could not find the operator id!")
	time_temp = time.strftime("%Y-%m-%d-%H%M%S", time.localtime())
	selection = args.pop(0)
        cache = self._get_cached_passwords(operator)
        th = TemplateHandler(tpl_lang, tpl_name, tpl_type)
        tmp_dir = Utils.make_temp_dir(dir=cereconf.JOB_RUNNER_LOG_DIR,
                                      prefix="bofh_spool")
	out_name = "%s/%s-%s-%s.%s" % (tmp_dir, opr, time_temp, os.getpid(), tpl_type)
        out = file(out_name, "w")
        if th._hdr is not None:
            out.write(th._hdr)
        ret = []
        
        num_ok = 0
        for n in self._parse_range(selection):
            n -= 1
            account = self._get_account(cache[n]['account_id'])
            mapping = {'uname': cache[n]['account_id'],
                       'password': cache[n]['password'],
                       'account_id': account.entity_id,
                       'lopenr': ''}
            if tpl_lang.endswith("letter"):
                mapping['barcode'] = '%s/barcode_%s.eps' % (
                    tmp_dir, account.entity_id)
                try:
                    th.make_barcode(account.entity_id, mapping['barcode'])
                except IOError, msg:
                    raise CerebrumError(msg)
            person = self._get_person('entity_id', account.owner_id)
            fullname = person.get_name(self.const.system_cached, self.const.name_full)
            mapping['fullname'] =  fullname
            if tpl_lang.endswith("letter"):
                address = None
                for source, kind in ((self.const.system_sap,
                                      self.const.address_post),
                                     (self.const.system_fs,
                                      self.const.address_post),
                                     (self.const.system_fs,
                                      self.const.address_post_private)):
                    address = person.get_entity_address(source = source, type = kind)
                    if address:
                        break

                if not address:
                    ret.append("Error: Couldn't get authoritative address for %s" % account.account_name)
                    continue
                
                address = address[0]
                mapping['address_line2'] = ""
                mapping['address_line3'] = ""
                if address['address_text']:
                    alines = address['address_text'].split("\n")+[""]
                    mapping['address_line2'] = alines[0]
                    mapping['address_line3'] = alines[1]
                mapping['address_line1'] = fullname
                mapping['zip'] = address['postal_number']
                mapping['city'] = address['city']
                mapping['country'] = address['country']

                mapping['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
                mapping['emailadr'] = account.get_primary_mailaddress()  
	    num_ok += 1	
            out.write(th.apply_template('body', mapping, no_quote=('barcode',)))
        if not (num_ok > 0):
            raise CerebrumError("Errors extracting required information: %s" % "+n".join(ret))
        if th._footer is not None:
            out.write(th._footer)
        out.close()
        try:
            account = self._get_account(operator.get_entity_id(), idtype='id')
            th.spool_job(out_name, tpl_type, skriver, skip_lpr=0,
                         lpr_user=account.account_name,
                         logfile="%s/spool.log" % tmp_dir)
        except IOError, msg:
            raise CerebrumError(msg)
        ret.append("OK: %s/%s.%s spooled @ %s for %s" % (
            tpl_lang, tpl_name, tpl_type, skriver, selection))
        return "\n".join(ret)

    # user delete
    #
    all_commands['user_delete'] = Command(
        ("user", "delete"), AccountName(), perm_filter='can_delete_user')
    def user_delete(self, operator, accountname):
        # TODO: How do we delete accounts?
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError, "User is already deleted"
        br = BofhdRequests(self.db, self.const)
        br.add_request(operator.get_entity_id(), br.now,
                       self.const.bofh_delete_user,
                       account.entity_id, None,
                       state_data=None)
        return "User %s queued for deletion at 20:00" % account.account_name

    # user_create_prompt_fun_helper
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
        if ac_type == 'PosixUser':
            if not all_args:
                return {'prompt': "Default filegroup"}
            filgruppe = all_args.pop(0)
            if not all_args:
                return {'prompt': "Shell", 'default': 'bash'}
            shell = all_args.pop(0)
            if not all_args:
                return {'prompt': "Disk", 'help_ref': 'disk'}
            disk = all_args.pop(0)
            if not all_args:
                return {'prompt': "Novell disk", 'help_ref': 'disk'}
            ndisk = all_args.pop(0)
        if not all_args:
            ret = {'prompt': "Username", 'last_arg': True}
            posix_user = PosixUser.PosixUser(self.db)
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    fname, lname = [
                        person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last) ]
                    sugg = posix_user.suggest_unames(self.const.account_namespace, fname, lname)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        if len(all_args) == 1:
            return {'last_arg': True}
        raise CerebrumError, "Too many arguments"

    # user_create_prompt_func
    #
    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('PosixUser', session, *args)
    
    # user_create_basic_prompt_func
    #
    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)
    
    #
    # user create
    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')
    def user_create(self, operator, *args):
        if args[0].startswith('group:'):
            group_id, np_type, filegroup, shell, home, novell_home, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")
        else:
            if len(args) == 7:
                idtype, person_id, affiliation, filegroup, shell, home, novell_home, uname = args
            else:
                idtype, person_id, yes_no, affiliation, filegroup, shell, home, novell_home, uname = args
            owner_type = self.const.entity_person
            owner_id = self._get_person("entity_id", person_id).entity_id
            np_type = None

        # Only superusers should be allowed to create users with
        # capital letters in their ids, and even then, just for system
        # users
        if uname != uname.lower():
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise CerebrumError("Account names cannot contain capital letters")
            else:
                if owner_type != self.const.entity_group:
                    raise CerebrumError("Personal account names cannot contain capital letters")
            
        group = self._get_group(filegroup, grtype="PosixGroup")
        posix_user = PosixUser.PosixUser(self.db)
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        if home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hardcoded path")
            disk_id, home = None, home[1:]
        if novell_home[0] != ':':  # Hardcoded path
            ndisk_id, novell_home = self._get_disk(novell_home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hardcoded path")
            ndisk_id, novell_home = None, home[1:]            
        posix_user.clear()
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)

        posix_user.populate(uid, group.entity_id, gecos, shell, name=uname,
                            owner_type=owner_type,
                            owner_id=owner_id, np_type=np_type,
                            creator_id=operator.get_entity_id(),
                            expire_date=expire_date)
        try:
            posix_user.write_db()
            for spread in cereconf.BOFHD_NEW_USER_SPREADS:
                posix_user.add_spread(self.const.Spread(spread))
            homedir_id = posix_user.set_homedir(
                disk_id=disk_id, home=home,
                status=self.const.home_status_not_created)
            posix_user.set_home(self.const.spread_nis_user, homedir_id)
            nhomedir_id = posix_user.set_homedir(
                disk_id=ndisk_id, home=novell_home,
                status=self.const.home_status_not_created)
            posix_user.set_home(self.const.spread_hia_novell_user, nhomedir_id)
            # For correct ordering of ChangeLog events, new users
            # should be signalled as "exported to" a certain system
            # before the new user's password is set.  Such systems are
            # flawed, and should be fixed.
            passwd = posix_user.make_passwd(uname)
            posix_user.set_password(passwd)
            # And, to write the new password to the database, we have
            # to .write_db() one more time...
            posix_user.write_db()
            if len(args) != 6:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(posix_user, owner_id,
                                                   ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        self._meld_inn_i_server_gruppe(int(posix_user.entity_id), operator)        
        return "Ok, create %s" % {'uid': uid}

    # helper func, let new account join appropriate server_group
    #
    def _meld_inn_i_server_gruppe(self, acc_id, operator):
        # fikser innmelding i edir-servergrupper _midlertidig_. skal fikses i nye edir-sync
        acc = Utils.Factory.get('Account')(self.db)
        acc.clear()
        acc.find(acc_id)
        acc_stuff= acc.get_home(self.const.spread_hia_novell_user)
        disk_id = acc_stuff['disk_id']
        disk = Utils.Factory.get('Disk')(self.db)
        disk.clear()
        disk.find(disk_id)
        tmp = string.split(disk.path, '/')
        grp_name = 'server-' + str(tmp[1])
        grp = Utils.Factory.get("Group")(self.db)
        grp.clear()
        grp.find_by_name(grp_name)
        grp.add_member(acc.entity_id, self.const.entity_account, self.const.group_memberop_union)

    # user move
    #
    all_commands['user_move'] = Command(
        ("user", "move"), AccountName(help_ref="account_name", repeat=False),
        Spread(), DiskId(),
        perm_filter='is_superuser')
    def user_move(self, operator, accountname, spread, path):
        account = self._get_account(accountname)
        move_ok = False
        if account.is_expired():
            raise CerebrumError, "Account %s has expired" % account.account_name
        spread = int(self._get_constant(self.const.Spread, spread))
        tmp_s = []
        for r in account.get_spread():
            tmp_s.append(int(r['spread']))
        if spread in tmp_s:
            move_ok = True
        if not move_ok:
            raise CerebrumError, "You can not move a user that does not have homedir in the given spread. Use home_create."
        disk_id = self._get_disk(path)[1]
        if disk_id is None:
            raise CerebrumError, "Bad destination disk"
        ah = account.get_home(spread)
        account.set_homedir(current_id=ah['homedir_id'],
                            disk_id=disk_id)
        account.set_home(spread, ah['homedir_id'])
        account.write_db()
        return "Ok, user %s moved." % accountname        

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
	    if ea.email_addr_target_id <> et.email_target_id:
		raise CerebrumError, "Address (%s) is in use by another user" % address
        except Errors.NotFoundError:
            pass
	ea.populate(lp, ed.email_domain_id, et.email_target_id)
	ea.write_db()
	epat = Email.EmailPrimaryAddressTarget(self.db)
	epat.clear()
	try:
	    epat.find(ea.email_addr_target_id)
	    epat.populate(ea.email_addr_id)
	except Errors.NotFoundError:
	    epat.clear()
	    epat.populate(ea.email_addr_id, parent = et)
	epat.write_db()
	return "Registered %s as primary address for %s" % (address, uname)
