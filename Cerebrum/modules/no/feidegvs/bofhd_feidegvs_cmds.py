# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003 University of Oslo, Norway
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

# Dette er strippet versjon av UiO sin kommandosett for Cerebrum-klienten
#
# Skal brukes i FEIDE-GVS prosjektet, men er ikke ferdig definert ennå
# 
#

import re
import sys
import time
import os
#import cyruslib
from mx import DateTime

import cereconf
from Cerebrum import Cache
from Cerebrum import Database
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode, _QuarantineCode, _SpreadCode,\
     _PersonAffiliationCode, _PersonAffStatusCode, _EntityTypeCode
from Cerebrum.Constants import CoreConstants     
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.Email import _EmailSpamLevelCode, _EmailSpamActionCode
from Cerebrum.modules import PasswordChecker
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthOpSet, \
     AuthConstants, BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules.no import fodselsnr
#from Cerebrum import OU
#from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.modules.no.uio import bofhd_uio_help
#from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.templates.letters import TemplateHandler

# TBD: It would probably be cleaner if our time formats were specified
# in a non-Java-SimpleDateTime-specific way.
def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

def format_time(field):
    fmt = "yyyy-MM-dd HH:mm"            # 16 characters wide
    return ':'.join((field, "date", fmt))

class BofhdExtension(object):
    """All CallableFuncs take user as first arg, and are responsible
    for checking necessary permissions"""

    all_commands = {}
    
    OU_class = Utils.Factory.get('OU')

    external_id_mappings = {}

    def __init__(self, server):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.person = Utils.Factory.get('Person')(self.db)
        self.const = self.person.const
        self.name_codes = {}
        for t in self.person.list_person_name_codes():
            self.name_codes[int(t.code)] = t.description
        self.person_affiliation_codes = {}
#	self.ou = OU.OU(self.db)
        self.person_affiliation_statusids = {}
        for c in dir(self.const):
            const = getattr(self.const, c)
            if isinstance(const, _PersonAffStatusCode):
                self.person_affiliation_statusids.setdefault(str(const.affiliation), {})[str(const)] = const
            elif isinstance(const, _PersonAffiliationCode):
                self.person_affiliation_codes[str(const)] = const
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
        # TODO: str2const is not guaranteed to be unique (OK for now, though)
        self.num2const = {}
        self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const[str(tmp)] = tmp
        self.ba = BofhdAuth(self.db)
        aos = BofhdAuthOpSet(self.db)
        self.num2op_set_name = {}
        for r in aos.list():
            self.num2op_set_name[int(r['op_set_id'])] = r['name']
        self.change_type2details = {}
        for r in self.db.get_changetypes():
            self.change_type2details[int(r['change_type_id'])] = [
                r['category'], r['type'], r['msg_string']]

        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots],
                                                   size=500)
	    
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

    def get_help_strings(self):
        return (bofhd_uio_help.group_help, bofhd_uio_help.command_help,
                bofhd_uio_help.arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()


    #
    # email commands start
    #


    # email info <account>+
    all_commands['email_info'] = Command(
        ("email", "info"),
        AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_info',
        fs=FormatSuggestion([
        # target_type == Account
        ("Account:          %s\nMail server:      %s (%s)\n"+
         "Default address:  %s\nValid addresses:  %s",
         ("account", "server", "server_type", "def_addr", "valid_addr")),
        ("Spam level:       %s\nSpam action:      %s",
         ("spam_level", "spam_action")),
        ("Quota:            %d MiB, warn at %d%% (not enforced)",
         ("dis_quota_hard", "dis_quota_soft")),
        ("Quota:            %d MiB, warn at %d%% (%s MiB used)",
         ("quota_hard", "quota_soft", "quota_used")),
        ("Forwarding:       %s",
         ("forward", )),
        # target_type == Mailman
        ("Mailing list:     %s",
         ("mailman_list", )),
        ("Alias:            %s",
         ("mailman_alias", )),
        ("Administrative addresses:\n                  %s",
         ("mailman_admin", )),
        ]))
    def email_info(self, operator, uname):
        if uname.find('@') <> -1:
            try:
                ea = Email.EmailAddress(self.db)
                ea.find_by_address(uname)
                et = Email.EmailTarget(self.db)
                et.find(ea.get_target_id())
                ttype = et.email_target_type
                if (ttype == self.const.email_target_Mailman):
                    return self._email_info_mailman(uname, et)
                elif (ttype == self.const.email_target_account or
                      ttype == self.const.email_target_deleted):
                    acc = self._get_account(et.email_target_entity_id,
                                            idtype = 'id')
                else:
                    raise CerebrumError, ("email info for target type %s isn't "
                                          "implemented") % self.num2const[ttype]
            except Errors.NotFoundError:
                raise CerebrumError, "No such e-mail address (%s)" % uname
        else:
            acc = self._get_account(uname)
        self.ba.can_email_info(operator.get_entity_id(), acc)
        ret = self._email_info_basic(acc)
        try:
            self.ba.can_email_info_detail(operator.get_entity_id(), acc)
            ret += self._email_info_detail(acc)
        except PermissionDenied:
            pass
        return ret
    
    def _email_info_basic(self, acc):
        info = {}
        info["account"] = acc.account_name
        et = Email.EmailTarget(self.db)
        et.find_by_entity(acc.entity_id)
        if et.email_target_type == self.const.email_target_deleted:
            info["server"] = "<none>"
            info["server_type"] = "N/A"
            info["def_addr"] = "<deleted>"
        else:
            est = Email.EmailServerTarget(self.db)
            est.find_by_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(est.email_server_id)
            info["server"] = es.name
            type = int(es.email_server_type)
            info["server_type"] = str(Email._EmailServerTypeCode(type))
            info["def_addr"] = acc.get_primary_mailaddress()
        addrs = []
        for r in et.get_addresses(special=False):
            addrs.append(r['local_part'] + '@' + r['domain'])
        info["valid_addr"] = "\n                  ".join(addrs)
        return [ info ]

    def _email_info_detail(self, acc):
        info = []
        esf = Email.EmailSpamFilter(self.db)
        try:
            esf.find_by_entity(acc.entity_id)
            slev = _EmailSpamLevelCode(int(esf.email_spam_level))
            sact = _EmailSpamActionCode(int(esf.email_spam_action))
            info.append({'spam_level': slev._get_description(),
                         'spam_action': sact._get_description()})
        except Errors.NotFoundError:
            pass
        eq = Email.EmailQuota(self.db)
        try:
            eq.find_by_entity(acc.entity_id)
            est = Email.EmailServerTarget(self.db)
            est.find_by_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(est.email_server_id)
            if es.email_server_type == self.const.email_server_type_cyrus:
                pw = self.db._read_password(cereconf.CYRUS_HOST,
                                            cereconf.CYRUS_ADMIN)
                try:
                    cyrus = cyruslib.CYRUS(es.name)
                    cyrus.login(cereconf.CYRUS_ADMIN, pw)
                    # TODO: use imaplib instead of cyruslib, and do
                    # quotatrees properly.  cyruslib doesn't check to
                    # see if it's a STORAGE quota or something else.
                    # not very important for us, though.
                    used, limit = cyrus.lq("user", acc.account_name)
                    used = str(used/1024)
                except:
                    used = 'N/A'
                info.append({'quota_hard': eq.email_quota_hard,
                             'quota_soft': eq.email_quota_soft,
                             'quota_used': used})
            else:
                info.append({'dis_quota_hard': eq.email_quota_hard,
                             'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass
        forw = []
        local_copy = ""
        ef = Email.EmailForward(self.db)
        ef.find_by_entity(acc.entity_id)
        if ef.email_target_type == self.const.email_target_deleted:
            prim = "<deleted>"
        else:
            prim = acc.get_primary_mailaddress()
        for r in ef.get_forward():
            if r['enable'] == 'T':
                enabled = "on"
            else:
                enabled = "off"
            if r['forward_to'] == prim:
                local_copy = "+ local delivery (%s)" % enabled
            else:
                forw.append("%s (%s) " % (r['forward_to'], enabled))
        # for aesthetic reasons, print "+ local delivery" last
        if local_copy:
            forw.append(local_copy)
        if forw:
            info.append({'forward': "\n                  ".join(forw)})
        return info
    
    _interface2addrs = {
        'post': ["%(local_part)s@%(domain)s"],
        'mailcmd': ["%(local_part)s-request@%(domain)s"],
        'mailowner': ["%(local_part)s-admin@%(domain)s",
                      "%(local_part)s-owner@%(domain)s",
                      "owner-%(local_part)s@%(domain)s"]
        }
    _mailman_pipe = "|/local/Mailman/mail/wrapper %(interface)s %(listname)s"
    _mailman_patt = r'\|/local/Mailman/mail/wrapper (\S+) (\S+)$'
    
    def _email_info_mailman(self, addr, et):
        m = re.match(self._mailman_patt, et.email_target_alias)
        if not m:
            raise CerebrumError, ("Unrecognised pipe command for Mailman list:"+
                                  et.email_target_alias)
        interface, list = m.groups()
        # this is the primary name
        ret = [{'mailman_list': list}]
        lp, dom = list.split('@')
        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(dom)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            raise CerebrumError, ("Address %s exists, but the list it points "
                                  "to, %s, does not") % (addr, list)
        # now find all e-mail addresses
        et.clear()
        et.find(ea.email_addr_target_id)
        aliases = []
        for r in et.get_addresses():
            a = "%(local_part)s@%(domain)s" % r
            if a == list:
                continue
            aliases.append(a)
        if aliases:
            print "DEBUG:", "\n                  ".join(aliases)
            ret.append({'mailman_alias':
                        "\n                  ".join(aliases)})
        # and all administrative addresses ... TODO
        return ret

    # email-commands slutt


    #
    # misc commands start
    #

    # misc affiliations
    all_commands['misc_affiliations'] = Command(
        ("misc", "affiliations"),
        fs=FormatSuggestion("%-14s %-14s %s", ('aff', 'status', 'desc'),
                            hdr="%-14s %-14s %s" % ('Affiliation', 'Status',
                                                    'Description')))
    def misc_affiliations(self, operator):
        tmp = {}
        for c in dir(self.const):
            const = getattr(self.const, c)
            if isinstance(const, _PersonAffStatusCode):
                if not tmp.has_key(str(const.affiliation)):
                    tmp[str(const.affiliation)] = [
                        {'aff': str(const.affiliation), 'status': '',
                         'desc': unicode(const.affiliation._get_description(), 'iso8859-1')}]
                else:
                    tmp[str(const.affiliation)].append(
                        {'aff': '', 'status': "%s" % const,
                         'desc': unicode(const._get_description(), 'iso8859-1')})
        keys = tmp.keys()
        keys.sort()
        ret = []
        for k in keys:
            for r in tmp[k]:
                ret.append(r)
        return ret

        # TODO: Define affiliations for UiO
        raise NotImplementedError, "Feel free to implement this function"

    # misc checkpassw
    all_commands['misc_checkpassw'] = Command(
        ("misc", "checkpassw"), AccountPassword())
    def misc_checkpassw(self, operator, password):
        pc = PasswordChecker.PasswordChecker(self.db)
        try:
            pc.goodenough(None, password, uname="foobar")
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError, "Bad password: %s" % m
        ac = Utils.Factory.get('Account')(self.db)
        crypt = ac.enc_auth_type_crypt3_des(password)
        md5 = ac.enc_auth_type_md5_crypt(password)
        return "OK.  crypt3-DES: %s   MD5-crypt: %s" % (crypt, md5)

    # misc clear_passwords
    all_commands['misc_clear_passwords'] = Command(
        ("misc", "clear_passwords"), AccountName(optional=True))
    def misc_clear_passwords(self, operator, account_name=None):
        operator.clear_state(state_types=('new_account_passwd', 'user_passwd'))
        return "OK"

    # misc list_passwords
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
        if not tpl_lang.endswith("letter"):
            if not all_args:
                return {'prompt': 'Oppgi skrivernavn'}
            skriver = all_args.pop(0)
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
                    'help_ref': 'print_select_range'}

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
        if not tpl_lang.endswith("letter"):
            skriver = args.pop(0)
        else:
            skriver = cereconf.PRINT_PRINTER
        selection = args.pop(0)
        cache = self._get_cached_passwords(operator)
        th = TemplateHandler(tpl_lang, tpl_name, tpl_type)
        tmp_dir = Utils.make_temp_dir(dir=cereconf.JOB_RUNNER_LOG_DIR,
                                      prefix="bofh_spool")
        out_name = "%s/%s.%s" % (tmp_dir, "job", tpl_type)
        out = file(out_name, 'w')
        if th._hdr is not None:
            out.write(th._hdr)
        ret = []
        
        for n in self._parse_range(selection):
            n -= 1
            account = self._get_account(cache[n]['account_id'])
            mapping = {'uname': cache[n]['account_id'],
                       'password': cache[n]['password'],
                       'account_id': account.entity_id}#,

            person = self._get_person('entity_id', account.owner_id)
            fullname = person.get_name(self.const.system_cached, self.const.name_full)
            mapping['fullname'] =  fullname
            mapping['address_line1'] = fullname
	    mapping['address_line2'] = person.birth_date.strftime('%Y-%m-%d')
	    mapping['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
	    mapping['emailadr'] =  account.get_primary_mailaddress() 

            out.write(th.apply_template('body', mapping))
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


    # misc user_passwd
    all_commands['misc_user_passwd'] = Command(
        ("misc", "user_passwd"), AccountName(), AccountPassword())
    def misc_user_passwd(self, operator, accountname, password):
        ac = self._get_account(accountname)
        # Only people who can set the password are allowed to check it
        self.ba.can_set_password(operator.get_entity_id(), ac)
        old_pass = ac.get_account_authentication(self.const.auth_type_md5_crypt)
        if(ac.enc_auth_type_md5_crypt(password, salt=old_pass[:old_pass.rindex('$')])
           == old_pass):
            return "Password is correct"
        return "Incorrect password"

    # misc-commands slutt

    #
    # person commands start
    #

    # person create
    all_commands['person_create'] = Command(
        ("person", "create"), PersonId(),
        Date(help_ref='date_birth'), PersonName(help_ref="person_name_full"), OU(),
        Affiliation(), AffiliationStatus(),
        fs=FormatSuggestion("Created: %i",
        ("person_id",)), perm_filter='can_create_person')
    def person_create(self, operator, person_id, bdate, person_name,
                      ou, affiliation, aff_status):
	ou = self._get_ou(ou)
        aff = self._get_affiliationid(affiliation)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
	self.ba.can_create_person(operator.get_entity_id(), ou, aff)
        #self.ba.can_create_person(operator.get_entity_id())
        person = self.person
        person.clear()
        if bdate is not None:
            bdate = self._parse_date(bdate)
        if person_id:
            id_type, id = self._map_person_id(person_id)
        else:
            id_type = None
        gender = self.const.gender_unknown
        if id_type is not None and id:
            if id_type == self.const.externalid_fodselsnr:
                try:
                    if fodselsnr.er_mann(id):
                        gender = self.const.gender_male
                    else:
                        gender = self.const.gender_female
                except fodselsnr.InvalidFnrError, msg:
                    raise CerebrumError("Invalid birth-no")
                try:
                    person.find_by_external_id(self.const.externalid_fodselsnr, id)
                    raise CerebrumError("A person with that fnr already exists")
                except Errors.TooManyRowsError:
                    raise CerebrumError("A person with that fnr already exists")
                except Errors.NotFoundError:
                    pass
                person.clear()
                person.affect_external_id(self.const.system_manual,
                                          self.const.externalid_fodselsnr)
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_fodselsnr,
                                            id)
        person.populate(bdate, gender,
                        description='Manualy created')
        person.affect_names(self.const.system_manual, self.const.name_full)
        person.populate_name(self.const.name_full,
                             person_name.encode('iso8859-1'))
#        ou = self._get_ou(ou)
#        aff = self._get_affiliationid(affiliation)
#        aff_status = self._get_affiliation_statusid(aff, aff_status)
        try:
            person.write_db()
            person.add_affiliation(ou.entity_id, aff,
                                   self.const.system_manual, aff_status)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    # person accounts
    all_commands['person_accounts'] = Command(
        ("person", "accounts"), PersonId(),
        fs=FormatSuggestion("%6i %s", ("account_id", "name"), hdr="Id     Name"))
    def person_accounts(self, operator, id):
        if id.find(":") == -1 and not id.isdigit():
            ac = self._get_account(id)
            id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(id))
        account = Utils.Factory.get('Account')(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(person.entity_id):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name})
        return ret


    # person find
    all_commands['person_find'] = Command(
        ("person", "find"), PersonSearchType(), SimpleString(),
        fs=FormatSuggestion("%6i   %10s   %10s   %s",
                            ('id', format_day('birth'), 'export_id', 'name'),
                            hdr="%6s   %10s   %10s   %s" % \
                            ('Id', 'Birth', 'Exp-id', 'Name')))

    def person_find(self, operator, search_type, value):
        # TODO: Need API support for this
        matches = []
        if search_type == 'person_id':
            person = self._get_person(*self._map_person_id(value))
            matches = [{'person_id': person.entity_id}]
        else:
            person = self.person
            person.clear()
            if search_type == 'name':
                if value.strip() and '%' not in value and '_' not in value:
                    # Add wildcards to start and end of value.
                    value = '%' + value.strip() + '%'
                matches = person.find_persons_by_name(value)
            elif search_type == 'date':
                matches = person.find_persons_by_bdate(self._parse_date(value))
        ret = []
        for row in matches:
            person = self._get_person('entity_id', row['person_id'])
            ret.append({'id': row['person_id'],
                        'birth': person.birth_date,
                        'export_id': person.export_id,
                        'name': person.get_name(self.const.system_cached,
                                                getattr(self.const, cereconf.DEFAULT_GECOS_NAME))})
        return ret
    
    # person info
    all_commands['person_info'] = Command(
        ("person", "info"), PersonId(),
        fs=FormatSuggestion("Name:          %s\n" +
                            "Export ID:     %s\n" +
                            "Birth:         %s\n" +
                            "Affiliations:  %s",
                            ("name", "export_id", format_day("birth"),
			     "affiliations")))
    def person_info(self, operator, person_id):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        affiliations = []
        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s/%s@%s" % (
                self.num2const[int(row['affiliation'])],
                self.num2const[int(row['status'])],
                self._format_ou_name(ou)))
        return {'name': person.get_name(self.const.system_cached,
                                        getattr(self.const,
                                                cereconf.DEFAULT_GECOS_NAME)),
                'affiliations': (",\n" + (" " * 15)).join(affiliations),
                'export_id': person.export_id,
                'birth': person.birth_date}

    # person-commands slutt


    #
    # quarantine commands start
    #

    # quarantine list
    all_commands['quarantine_list'] = Command(
        ("quarantine", "list"),
        fs=FormatSuggestion("%-14s %s", ('name', 'desc'),
                            hdr="%-14s %s" % ('Name', 'Description')))
    def quarantine_list(self, operator):
        ret = []
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _QuarantineCode):
                ret.append({'name': "%s" % tmp,
                            'desc': unicode(tmp._get_description(), 'iso8859-1')})
        return ret

    # quarantine remove
    all_commands['quarantine_remove'] = Command(
        ("quarantine", "remove"), EntityType(default="account"), Id(), QuarantineType(),
        perm_filter='can_remove_quarantine')
    def quarantine_remove(self, operator, entity_type, id, qtype):
        entity = self._get_entity(entity_type, id)
        qtype = int(self._get_constant(qtype, "No such quarantine"))
        self.ba.can_remove_quarantine(operator.get_entity_id(), entity, qtype)
        entity.delete_entity_quarantine(qtype)
        return "OK"

    # quarantine set
    all_commands['quarantine_set'] = Command(
        ("quarantine", "set"), EntityType(default="account"), Id(repeat=True),
        QuarantineType(), SimpleString(help_ref="string_why"),
        SimpleString(help_ref="string_from_to"), perm_filter='can_set_quarantine')
    def quarantine_set(self, operator, entity_type, id, qtype, why, date):
        date_start, date_end = self._parse_date_from_to(date)
        entity = self._get_entity(entity_type, id)
        qtype = int(self._get_constant(qtype, "No such quarantine"))
        self.ba.can_set_quarantine(operator.get_entity_id(), entity, qtype)
        if entity_type != 'account':
            raise CerebrumError("Quarantines can only be set on accounts")
        entity.add_entity_quarantine(qtype, operator.get_entity_id(), why, date_start, date_end)
        return "OK"

    # quarantine show
    all_commands['quarantine_show'] = Command(
        ("quarantine", "show"), EntityType(default="account"), Id(),
        fs=FormatSuggestion("%-14s %-16s %-16s %-14s %-8s %s",
                            ('type', format_time('start'), format_time('end'),
                             format_day('disable_until'), 'who', 'why'),
                            hdr="%-14s %-16s %-16s %-14s %-8s %s" % \
                            ('Type', 'Start', 'End', 'Disable until', 'Who',
                             'Why')),
        perm_filter='can_show_quarantines')
    def quarantine_show(self, operator, entity_type, id):
        ret = []
        entity = self._get_entity(entity_type, id)
        self.ba.can_show_quarantines(operator.get_entity_id(), entity)
        for r in entity.get_entity_quarantine():
            acc = self._get_account(r['creator_id'], idtype='id')
            ret.append({'type': "%s" % self.num2const[int(r['quarantine_type'])],
                        'start': r['start_date'],
                        'end': r['end_date'],
                        'disable_until': r['disable_until'],
                        'who': acc.account_name,
                        'why': r['description']})
        return ret

    # quarantine commands slutt


    # group commands start


    # group create
    all_commands['group_create'] = Command(
        ("group", "create"), GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="string_description"),
        fs=FormatSuggestion("Group created as a normal group, internal id: %i", ("group_id",)),
        perm_filter='can_create_group')
    def group_create(self, operator, groupname, description):
        self.ba.can_create_group(operator.get_entity_id())
        g = Utils.Factory.get('Group')(self.db)
        g.populate(creator_id=operator.get_entity_id(),
                   visibility=self.const.group_visibility_all,
                   name=groupname, description=description)
        try:
            g.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(g.entity_id)}

    # group add
    all_commands['group_add'] = Command(
        ("group", "add"), AccountName(help_ref="account_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_add(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="account")

    # group remove
    all_commands['group_remove'] = Command(
        ("group", "remove"), AccountName(help_ref="account_name_member", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_remove(self, operator, src_name, dest_group,
                     group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="account")

    #
    # user commands start
    #

    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)


    # user create
    all_commands['user_reserve'] = Command(
        ('user', 'create_reserve'), prompt_func=user_create_basic_prompt_func,
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='can_create_user')
    def user_reserve(self, operator, idtype, person_id, affiliation, uname):
        person = self._get_person("entity_id", person_id)
        account = Utils.Factory.get('Account')(self.db)
        account.clear()
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may reserve users")
        account.populate(uname,
                         self.const.entity_person,  # Owner type
                         person.entity_id,
                         None,                      # np_type
                         operator.get_entity_id(),  # creator_id
                         None)                      # expire_date
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        try:
            account.write_db()
            self._user_create_set_account_type(account, person.entity_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(account.entity_id),
                                                    'password': passwd})
        return {'account_id': int(account.entity_id)}
 
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
                    # TODO: We should show the persons name in the list
                    map.append((
                        ("%8i %s", int(c[i]['person_id']),
                         person.get_name(self.const.system_cached, self.const.name_full)),
                        int(c[i]['person_id'])))
                return {'prompt': "Choose person from list",
                        'map': map,
                        'help_ref': 'user_create_select_person'}
        owner_id = all_args.pop(0)
        if not group_owner:
            if not all_args:
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                person = self._get_person("entity_id", owner_id)
		for aff in person.get_affiliations():
		    print "%s %s" % (aff['affiliation'],type(aff['affiliation']))
		    if aff['affiliation'] == int(self.const.affiliation_admin):
			map.append((("%s", str(self.const.affiliation_admin)),
				    int(self.const.affiliation_admin)))
		    if aff['affiliation'] == int(self.const.affiliation_guardian):
			map.append((("%s", str(self.const.affiliation_guardian)),
				    int(self.const.affiliation_guardian)))
		    if aff['affiliation'] == int(self.const.affiliation_teacher):
			map.append((("%s", str(self.const.affiliation_teacher)),
				    int(self.const.affiliation_teacher)))
		    if aff['affiliation'] == int(self.const.affiliation_pupil):
			map.append((("%s", str(self.const.affiliation_pupil)),
				    int(self.const.affiliation_pupil)))
		    if aff['affiliation'] == int(self.const.affiliation_employee):
			map.append((("%s", str(self.const.affiliation_employee)),
				    int(self.const.affiliation_employee)))
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
            ret = {'prompt': "Username", 'last_arg': True}
            posix_user = PosixUser.PosixUser(self.db)
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    # TODO: this requires that cereconf.DEFAULT_GECOS_NAME is name_full.  fix
                    full = person.get_name(self.const.system_cached, self.const.name_full)
                    fname, lname = full.split(" ", 1)
                    sugg = posix_user.suggest_unames(self.const.account_namespace, fname, lname)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        raise CerebrumError, "Client called prompt func with too many arguments"

    
    def _user_create_set_account_type(self, account, owner_id, affiliation):
        #ou = self._get_ou(ou=cereconf.DEFAULT_OU)
        person = self._get_person('entity_id', owner_id)
	if person.get_affiliations() is not None:
	    for aff in person.get_affiliations():
		if aff['affiliation'] == int(self.const.affiliation_admin):
		    ou = self._get_ou(aff['ou_id'])
		if aff['affiliation'] == int(self.const.affiliation_teacher):
		    ou = self._get_ou(aff['ou_id'])
		if aff['affiliation'] == int(self.const.affiliation_guardian):
		    ou = self._get_ou(aff['ou_id'])
		if aff['affiliation'] == int(self.const.affiliation_pupil):
		    ou = self._get_ou(aff['ou_id'])
		if aff['affiliation'] == int(self.const.affiliation_employee):
		    ou = self._get_ou(aff['ou_id'])
	    account.set_account_type(ou.entity_id, affiliation)
	else:
	    raise CerebrumError, "Person not properly registered, check source system"

#        if not (affiliation == self.const.affiliation_admin or
#                affiliation == self.const.affiliation_teacher or
#		affiliation == self.const.affiliation_guardian or
#		affiliation == self.const.affiliation_pupil):
#            tmp = self.person_affiliation_statusids[str(self.const.affiliation_manuell)]
#            for k in tmp.keys():
#                if affiliation == int(tmp[k]):
#                    break
#            affiliation = tmp[k].affiliation
#            has_affiliation = False
#            for a in person.get_affiliations():
#                if (a['ou_id'] == ou.entity_id and
#                    a['affiliation'] == int(tmp[k].affiliation)):
#                    has_affiliation = True
#            if not has_affiliation:
#                person.add_affiliation(ou.entity_id, tmp[k].affiliation,
#                                       self.const.system_manual, tmp[k])
#        else:
#            for aff in person.get_affiliations():
#                if aff['affiliation'] == int(self.const.affiliation_ansatt):
#                    ou = self._get_ou(aff['ou_id'])
#                if aff['affiliation'] == int(self.const.affiliation_student):
#                    ou = self._get_ou(aff['ou_id'])
#        account.set_account_type(ou.entity_id, affiliation)

    # user history
    all_commands['user_history'] = Command(
        ("user", "history"), AccountName(),
        perm_filter='can_show_history')
    def user_history(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_show_history(operator.get_entity_id(), account)
        ret = []
        for r in self.db.get_log_events(0, subject_entity=account.entity_id):
            dest = r['dest_entity']
            if dest is not None:
                self._get_entity_name(None, dest)
            msg = self.change_type2details[int(r['change_type_id'])][2] % {
                'subject': self._get_entity_name(None, r['subject_entity']),
                'dest': dest}
            by = r['change_program'] or self._get_entity_name(None, r['change_by'])
            ret.append("%s [%s]: %s" % (r['tstamp'], by, msg))
        return "\n".join(ret)

    # user info
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion([("Spreads:       %s\n" +
                              "Affiliations:  %s\n" +
                              "Expire:        %s\n" +
                              "Home:          %s\n" +
                              "Entity id:     %i",
                              ("spread", "affiliations", format_day("expire"),
                               "home", "entity_id")),
                             ("uid:           %i\n" +
                              "default fg:    %i=%s\n" +
                              "gecos:         %s\n" +
                              "shell:         %s",
                              ('uid', 'dfg_posix_gid', 'dfg_name', 'gecos',
                               'shell'))]))
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
        for row in account.get_account_types():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (self.num2const[int(row['affiliation'])],
                                           self._format_ou_name(ou)))
        ret = {'entity_id': account.entity_id,
               'spread': ",".join(["%s" % self.num2const[int(a['spread'])]
                                   for a in account.get_spread()]),
               'affiliations': (",\n" + (" " * 15)).join(affiliations),
               'expire': account.expire_date,
               'home': account.home}
        if account.disk_id is not None:
            disk = Utils.Factory.get('Disk')(self.db)
            disk.find(account.disk_id)
            ret['home'] = "%s/%s" % (disk.path, account.account_name)

        if is_posix:
            group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            ret['uid'] = account.posix_uid
            ret['dfg_posix_gid'] = group.posix_gid
            ret['dfg_name'] = group.group_name
            ret['gecos'] = account.gecos
            ret['shell'] = str(self.num2const[int(account.shell)])
        # TODO: Return more info about account
        return ret

    # user commands slutt

    def _map_template(self, num=None):
        """If num==None: return list of avail templates, else return
        selected template """
        tpls = []
        n = 1
        keys = cereconf.BOFHD_TEMPLATES.keys()
        keys.sort()
        for k in keys:
            for tpl in cereconf.BOFHD_TEMPLATES[k]:
                tpls.append("%s:%s.%s (%s)" % (k, tpl[0], tpl[1], tpl[2]))
                if num is not None and n == int(num):
                    return (k, tpl[0], tpl[1])
                n += 1
        if num is not None:
            raise CerebrumError, "Unknown template selected"
        return tpls

    def _get_cached_passwords(self, operator):
        ret = []
        for r in operator.get_state():
            # state_type, entity_id, state_data, set_time
            if r['state_type'] in ('new_account_passwd', 'user_passwd'):
                ret.append({'account_id': self._get_entity_name(
                    self.const.entity_account, r['state_data']['account_id']),
                            'password': r['state_data']['password'],
                            'operation': r['state_type']})
        return ret



    # user password
    all_commands['user_password'] = Command(
        ('user', 'password'), AccountName(), AccountPassword(optional=True))
    def user_password(self, operator, accountname, password=None):
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)
        if password is None:
            password = account.make_passwd(accountname)
        else:
            if operator.get_entity_id() <> account.entity_id:
                raise CerebrumError, \
                      "Cannot specify password for another user."
        try:
            pc = PasswordChecker.PasswordChecker(self.db)
            pc.goodenough(account, password)
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError, "Bad password: %s" % m
        account.set_password(password)
        try:
            account.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("user_passwd", {'account_id': int(account.entity_id),
                                             'password': password})
	
	return "Bruk 'misc list_passwords' for å skrive ut passordet"
    
    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)


    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable
    #

    def _get_account(self, id, idtype=None, actype="Account"):
        if actype == 'Account':
            account = Utils.Factory.get('Account')(self.db)
        elif actype == 'PosixUser':
            account = PosixUser.PosixUser(self.db)
        account.clear()
        try:
            if idtype is None:
                if id.find(":") != -1:
                    idtype, id = id.split(":", 1)
                else:
                    idtype = 'name'
            if idtype == 'name':
                account.find_by_name(id, self.const.account_namespace)
            elif idtype == 'id':
                account.find(id)
            else:
                raise NotImplementedError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find %s with %s=%s" % (actype, idtype, id)
        return account

    def _get_host(self, name):
        host = Utils.Factory.get('Host')(self.db)
        try:
            host.find_by_name(name)
            return host
        except Errors.NotFoundError:
            raise CerebrumError, "Unkown host: %s" % name

    def _get_group(self, id, idtype=None, grtype="Group"):
        if grtype == "Group":
            group = Utils.Factory.get('Group')(self.db)
        elif grtype == "PosixGroup":
            group = PosixGroup.PosixGroup(self.db)
        try:
            group.clear()
            if idtype is None:
                if id.count(':'):
                    idtype, id = id.split(':', 1)
                else:
                    idtype='name'
            if idtype == 'name':
                group.find_by_name(id)
            elif idtype == 'id':
                group.find(id)
            else:
                raise NotImplementedError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find %s with %s=%s" % (grtype, idtype, id)
        return group

    def _get_shell(self, shell):
        if shell == 'bash':
            return self.const.posix_shell_bash
        return int(self._get_constant(shell, "Unknown shell"))
    
    def _format_ou_name(self, ou):
        return "%s (%02i)" % (ou.name, ou.ou_id)

    def _get_ou(self, ou_id=None):
        ou = self.OU_class(self.db)
        ou.clear()
        if ou_id is not None:
            ou.find(ou_id)
        else:
            if not ou_id.isdigit():
                raise CerebrumError("Expected a digit")
            #ou.find_stedkode(stedkode[0:2], stedkode[2:4], stedkode[4:6],
            #                 institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
        return ou

    def _get_group_opcode(self, operator):
        if operator is None:
            return self.const.group_memberop_union
        if operator == 'union':
            return self.const.group_memberop_union
        if operator == 'intersection':
            return self.const.group_memberop_intersection
        if operator == 'difference':
            return self.const.group_memberop_difference
        raise CerebrumError("unknown group opcode: '%s'" % operator)

    def _get_entity(self, idtype=None, id=None):
        if id is None:
            raise CerebrumError, "Invalid id"
        if idtype == 'account':
            return self._get_account(id)
        if idtype == 'person':
            return self._get_person(*self._map_person_id(id))
        if idtype == 'group':
            return self._get_group(id)
        if idtype is None:
            return Entity.object_by_entityid(id, self.db)
        raise CerebrumError, "Invalid idtype"

    def _find_persons(self, arg):
        if arg.isdigit() and len(arg) > 10:  # finn personer fra fnr
            arg = 'fnr:%s' % arg
        ret = []
        person = self.person
        person.clear()
        if arg.find("-") != -1:
            # finn personer på fødselsdato
            ret = person.find_persons_by_bdate(self._parse_date(arg))
        elif arg.find(":") != -1:
            idtype, id = arg.split(":")
            if idtype == 'exp':
                raise NotImplementedError, "Lack API support for this"
            elif idtype == 'fnr':
                for ss in [self.const.system_sas, self.const.system_manual]:
                    try:
                        person.clear()
                        person.find_by_external_id(self.const.externalid_fodselsnr, id,
                                                   source_system=ss)
                        ret.append({'person_id': person.entity_id})
                    except Errors.NotFoundError:
                        pass
        else:
            raise CerebrumError, "Unable to parse person id"
        return ret
    
    def _get_person(self, idtype, id):
        person = self.person
        person.clear()
        try:
            if str(idtype) == 'account_name':
                ac = self._get_account(id)
                id = ac.owner_id
                idtype = "entity_id"
            if isinstance(idtype, _CerebrumCode):
                person.find_by_external_id(idtype, id)
            elif idtype == 'entity_id':
                person.find(id)
            else:
                raise CerebrumError, "Unknown idtype"
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find person with %s=%s" % (idtype, id)
        return person

    def _map_person_id(self, id):
        """Map <idtype:id> to const.<idtype>, id.  Recognizes
        fødselsnummer without <idtype>.  Also recognizes entity_id"""
        if id.isdigit() and len(id) >= 10:
            return self.const.externalid_fodselsnr, id
        if id.find(":") == -1:
            self._get_account(id)  # We assume this is an account
            return "account_name", id

        id_type, id = id.split(":", 1)
        if id_type != 'entity_id':
            id_type = self.external_id_mappings.get(id_type, None)
        if id_type is not None:
            return id_type, id
        raise CerebrumError, "Unkown person_id type"

    def _get_printerquota(self, account_id):
        pq = PrinterQuotas.PrinterQuotas(self.db)
        try:
            pq.find(account_id)
            return pq
        except Errors.NotFoundError:
            return None

    def _get_nametypeid(self, nametype):
        if nametype == 'first':
            return self.const.name_first
        elif nametype == 'last':
            return self.const.name_last
        elif nametype == 'full':
            return self.const.name_full
        else:
            raise NotImplementedError, "unkown nametype: %s" % nametye

    def _get_entity_name(self, type, id):
        if type is None:
            ety = Entity.Entity(self.db)
            ety.find(id)
            type = self.num2const[int(ety.entity_type)]
        if type == self.const.entity_account:
            acc = self._get_account(id, idtype='id')
            return acc.account_name
        elif type == self.const.entity_group:
            group = self._get_group(id, idtype='id')
            return group.get_name(self.const.group_namespace)
        elif type == self.const.entity_disk:
            disk = Utils.Factory.get('Disk')(self.db)
            disk.find(id)
            return disk.path
        elif type == self.const.entity_host:
            host = Utils.Factory.get('Host')(self.db)
            host.find(id)
            return host.name
        else:
            return "%s:%s" % (type, id)

    def _get_disk(self, home):
        disk_id = None
        try:
            host = None
            if home.find(":") != -1:
                host, path = home.split(":")
            else:
                path = home
            disk = Utils.Factory.get('Disk')(self.db)
            disk.find_by_path(path, host)
            home = None
            disk_id = disk.entity_id
        except Errors.NotFoundError:
            raise CerebrumError("Unknown disk: %s" % home)
        return disk_id, home

    def _map_np_type(self, np_type):
        # TODO: Assert _AccountCode
        return int(self._get_constant(np_type, "Unknown account type"))
        
    def _map_visibility_id(self, visibility):
        # TODO: Assert _VisibilityCode
        return int(self._get_constant(visibility, "No such visibility type"))


    def _is_yes(self, val):
        if isinstance(val, str) and val.lower() in ('y', 'yes', 'ja', 'j'):
            return True
        return False
        
    def _get_affiliationid(self, code_str):
        for k in self.person_affiliation_codes.keys():
            if k.lower() == code_str.lower():
                return self.person_affiliation_codes[k]
        raise CerebrumError("Unknown affiliation")

    def _get_affiliation_statusid(self, affiliation, code_str):
        for k in self.person_affiliation_statusids[str(affiliation)].keys():
            if k.lower() == code_str.lower():
                return self.person_affiliation_statusids[str(affiliation)][k]
        raise CerebrumError("Unknown affiliation status")

    def _get_constant(self, const_str, err_msg="Could not find constant"):
        if self.str2const.has_key(const_str):
            return self.str2const[const_str]
        raise CerebrumError("%s: %s" % (err_msg, const_str))

    def _parse_date_from_to(self, date):
        date_start = self._today()
        date_end = None
        if date:
            tmp = date.split("--")
            if len(tmp) == 2:
                date_start = self._parse_date(tmp[0])
                date_end = self._parse_date(tmp[1])
            elif len(tmp) == 1:
                date_end = self._parse_date(date)
            else:
                raise CerebrumError, "Incorrect date specification: %s." % date
        return (date_start, date_end)

    def _parse_date(self, date):
        if not date:
            return None
        try:
            return self.db.Date(*([ int(x) for x in date.split('-')]))
        except:
            raise CerebrumError, "Illegal date: %s" % date

    def _today(self):
        return self._parse_date("%d-%d-%d" % time.localtime()[:3])

    def _parse_range(self, selection):
        lst = []
        for part in selection.split():
            idx = part.find('-')
            if idx != -1:
                for n in range(int(part[:idx]), int(part[idx+1:])+1):
                    if n not in lst:
                        lst.append(n)
            else:
                part = int(part)
                if part not in lst:
                    lst.append(part)
        lst.sort()
        return lst
