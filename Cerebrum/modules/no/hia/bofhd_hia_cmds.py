# -*- coding: iso-8859-1 -*-

# Copyright 2002-2004 University of Oslo, Norway
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

# Denne fila implementerer er en bofhd extension som definerer kommandosettet
# tilgjengelig i Cerebrum-klienten til HiA

import re
import sys
import time
import os
import email.Generator, email.Message
import cyruslib
import pickle
from mx import DateTime
try:
    from sets import Set
except ImportError:
    # It's the same module taken from python 2.3, it should
    # work fine in 2.2  
    from Cerebrum.extlib.sets import Set    

import cereconf
from Cerebrum import Cache
from Cerebrum import Database
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode, _QuarantineCode, _SpreadCode,\
     _PersonAffiliationCode, _PersonAffStatusCode, _EntityTypeCode
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.Email import _EmailSpamLevelCode, _EmailSpamActionCode,\
     _EmailDomainCategoryCode
from Cerebrum.modules import PasswordChecker
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.no.hia.auth import BofhdAuth, BofhdAuthOpSet, \
     AuthConstants, BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.modules.no.hia import bofhd_hia_help
from Cerebrum.modules.no.hia.access_FS import HiAFS
from Cerebrum.modules.templates.letters import TemplateHandler
from time import localtime, strftime, time

# TBD: It would probably be cleaner if our time formats were specified
# in a non-Java-SimpleDateTime-specific way.
def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

def format_time(field):
    fmt = "yyyy-MM-dd HH:mm"            # 16 characters wide
    return ':'.join((field, "date", fmt))

class TimeoutException(Exception):
    pass

class BofhdExtension(object):
    """All CallableFuncs take user as first arg, and are responsible
    for checking necessary permissions"""

    all_commands = {}
    OU_class = Utils.Factory.get('OU')
    Account_class = Utils.Factory.get('Account')
    Group_class = Utils.Factory.get('Group')
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
        self.fixup_imaplib()

    def fixup_imaplib(self):
        import imaplib
        def nonblocking_open(self, host, port):
            import socket
            import time
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setblocking(False)
            tries = 0
            while tries < 10:
                tries += 1
                err = self.sock.connect_ex((self.host, self.port))
                if err == 0:
                    self.sock.setblocking(True)
                    self.file = self.sock.makefile('rb')
                    return
                time.sleep(0.05)
            raise TimeoutException
        setattr(imaplib.IMAP4, 'open', nonblocking_open)

    def num2str(self, num):
        """Returns the string value of a numerical constant"""
        return str(self.num2const[int(num)])
        
    def str2num(self, string):
        """Returns the numerical value of a string constant"""
        return int(self.str2const[str(string)])

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
        return (bofhd_hia_help.group_help, bofhd_hia_help.command_help,
                bofhd_hia_help.arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()


    #
    # access commands
    #

    # access disk <path>
    # access email_domain <address>
    # access group <group>
    all_commands['access_group'] = Command(
        ('access', 'group'),
        GroupName(),
        fs=FormatSuggestion("%13s  %-9s %s", ("opset", "type", "name"),
                            hdr="%13s  %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_group(self, operator, group):
        return self._list_access("group", group)

    # access host <hostname>
    all_commands['access_host'] = Command(
        ('access', 'host'),
        SimpleString(help_ref="string_host"),
        fs=FormatSuggestion("%13s  %-10s %-9s %-20s",
                            ("opset", "attr", "type", "name"),
                            hdr="%13s  %-10s %-9s %-20s" %
                            ("Operation set", "Pattern", "Type", "Name")))
    def access_host(self, operator, host):
        return self._list_access("host", host)

    # access ou <ou>
    # access person <account>
    # access spread <spread>
    # access user <account>

    def _list_access(self, target_type, target_name, decode_attr=str):
        target_id, target_type = self._get_access_id(target_type, target_name)
        ret = []
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for r in self._get_auth_op_target(target_id, target_type,
                                          any_attr=True):
            attr = r['attr']
            if attr is None:
                attr = ""
            else:
                attr = decode_attr(attr)
            for r2 in ar.list(op_target_id=r['op_target_id']):
                aos.clear()
                aos.find(r2['op_set_id'])
                ety = self._get_entity(id=r2['entity_id'])
                ret.append({'opset': aos.name,
                            'attr': attr,
                            'type': str(self.const.EntityType(ety.entity_type)),
                            'name': self._get_name_from_object(ety)})
        ret.sort(lambda a,b: (cmp(a['attr'], b['attr']) or
                              cmp(a['name'], b['name'])))
        return ret or "None"


    # access grant <opset name> <who> <type> <on what> [<attr>]
    all_commands['access_grant'] = Command(
        ('access', 'grant'),
        OpSet(),
        GroupName(repeat=True, help_ref="auth_group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='is_superuser')
    def access_grant(self, operator, opset, group, entity_type, target_name,
                     attr=None):
        return self._manipulate_access(self._grant_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    # access revoke <opset name> <who> <type> <on what> [<attr>]
    all_commands['access_revoke'] = Command(
        ('access', 'revoke'),
        OpSet(),
        GroupName(repeat=True, help_ref="auth_group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='is_superuser')
    def access_revoke(self, operator, opset, group, entity_type, target_name,
                     attr=None):
        return self._manipulate_access(self._revoke_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    def _manipulate_access(self, change_func, operator, opset, group,
                           entity_type, target_name, attr):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        opset = self._get_opset(opset)
        gr = self._get_group(group)
        target_id, target_type = self._get_access_id(entity_type, target_name)
        self._validate_access(entity_type, opset, attr)
        return change_func(gr.entity_id, opset, target_id, target_type, attr,
                           group, target_name)

    def _get_access_id(self, target_type, target_name):
        func_name = "_get_access_id_%s" % target_type
        if not func_name in dir(self):
            raise CerebrumError, "Unknown type %s" % target_type
        return self.__getattribute__(func_name)(target_name)

    def _validate_access(self, target_type, opset, attr):
        func_name = "_validate_access_%s" % target_type
        if not func_name in dir(self):
            raise CerebrumError, "Unknown type %s" % target_type
        return self.__getattribute__(func_name)(opset, attr)

    def _get_access_id_disk(self, target_name):
        return self._get_disk(target_name), self.const.auth_target_type_disk
    def _validate_access_disk(self, opset, attr):
        # TODO: check if the opset is relevant for a disk
        if attr is not None:
            raise CerebrumError, "Can't specify attribute for disk access"

    def _get_access_id_group(self, target_name):
        target = self._get_group(target_name)
        return target.entity_id, self.const.auth_target_type_group
    def _validate_access_group(self, opset, attr):
        # TODO: check if the opset is relevant for a group
        if attr is not None:
            raise CerebrumError, "Can't specify attribute for group access"

    def _get_access_id_host(self, target_name):
        target = self._get_host(target_name)
        return target.entity_id, self.const.auth_target_type_host
    def _validate_access_host(self, opset, attr):
        if attr is not None:
            if attr.count('/'):
                raise CerebrumError, ("The disk pattern should only contain "+
                                      "the last component of the path.")
            try:
                re.compile(attr)
            except re.error, e:
                raise CerebrumError, ("Syntax error in regexp: %s" % e)

    # def _get_access_id_maildom(self, target_name):
        
    # def _get_access_id_ou(self, target_name):

    # def _get_access_id_spread(self, target_name):


    # access list_opsets

    # for phase 2, something like:
    # access create_opset <opset name> <op>+
    # access add_op_to_opset <op>+ <opset>
    # access remove_op_from_opset <op>+ <opset>
    # access create_op <opname>
    # access delete_op <opname>
    # what to do about auth_op_attrs?

    def _get_auth_op_target(self, entity_id, target_type, attr=None,
                            any_attr=False, create=False):
        
        """Return auth_op_target(s) associated with (entity_id,
        target_type, attr).  If any_attr is false, return one
        op_target_id or None.  If any_attr is true, return list of
        matching db_row objects.  If create is true, create a new
        op_target if no matching row is found."""
        
        if any_attr:
            op_targets = []
            assert attr is None and create is False
        else:
            op_targets = None

        aot = BofhdAuthOpTarget(self.db)
        for r in aot.list(entity_id=entity_id, target_type=target_type,
                          attr=attr):
            if attr is None and not any_attr and r['attr']:
                continue
            if any_attr:
                op_targets.append(r)
            else:
                # There may be more than one matching op_target, but
                # we don't care which one we use -- we will make sure
                # not to make duplicates ourselves.
                op_targets = int(r['op_target_id'])
        if op_targets or not create:
            return op_targets
        # No op_target found, make a new one.
        aot.populate(entity_id, target_type, attr)
        aot.write_db()
        return aot.op_target_id

    def _grant_auth(self, entity_id, opset, target_id, target_type, attr,
                    entity_name, target_name):
        op_target_id = self._get_auth_op_target(target_id, target_type, attr,
                                                create=True)
        ar = BofhdAuthRole(self.db)
        rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        if len(rows) == 0:
            ar.grant_auth(entity_id, opset.op_set_id, op_target_id)
            return "OK"
        print "DEBUG", "hei"
        return "%s already has %s access to %s" % (entity_name, opset.name,
                                                   target_name)

    def _revoke_auth(self, entity_id, opset, target_id, target_type, attr,
                     entity_name, target_name):
        op_target_id = self._get_auth_op_target(target_id, target_type, attr)
        if not op_target_id:
            raise CerebrumError, ("No one has matching access to %s" %
                                  target_name)
        ar = BofhdAuthRole(self.db)
        rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        if len(rows) == 0:
            return "%s don't have %s access to %s" % (entity_name, opset.name,
                                                      target_name)
        print ["%r" % x for x in (entity_id, opset, target_id, target_type,
                                  attr, entity_name, target_name)]
        ar.revoke_auth(entity_id, opset.op_set_id, op_target_id)
        # See if the op_target has any references left, delete it if not.
        rows = ar.list(op_target_id=op_target_id)
        if len(rows) == 0:
            aot = BofhdAuthOpTarget(self.db)
            aot.find(op_target_id)
            aot.delete()
        return "OK"

    #
    # email commands
    #

    # email add_address <address or account> <address>+
    all_commands['email_add_address'] = Command(
        ('email', 'add_address'),
        AccountName(help_ref='account_name'),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_address_add')
    def email_add_address(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        ttype = et.email_target_type
        if ttype not in (self.const.email_target_Mailman,
                         self.const.email_target_forward,
                         self.const.email_target_multi,
                         self.const.email_target_pipe,
                         self.const.email_target_account):
            raise CerebrumError, ("Can't add e-mail address to target "+
                                  "type %s") % self.num2const[ttype]
        ea = Email.EmailAddress(self.db)
        lp, dom = address.split('@')
        ed = self._get_email_domain(dom)
        self.ba.can_email_address_add(operator.get_entity_id(),
                                      account=acc, domain=ed)
        ea.clear()
        try:
            ea.find_by_address(address)
            raise CerebrumError, "Address already exists (%s)" % address
        except Errors.NotFoundError:
            pass
        ea.clear()
        ea.populate(lp, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        return "OK"
    
    # email remove_address <account> <address>+
    all_commands['email_remove_address'] = Command(
        ('email', 'remove_address'),
        AccountName(help_ref='account_name'),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_address_delete')
    def email_remove_address(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        ttype = et.email_target_type
        if ttype not in (self.const.email_target_Mailman,
                         self.const.email_target_account,
                         self.const.email_target_forward,
                         self.const.email_target_pipe,
                         self.const.email_target_multi,
                         self.const.email_target_deleted):
            raise CerebrumError, ("Can't remove e-mail address from target "+
                                  "type %s") % self.num2const[ttype]
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_address(address)
        except Errors.NotFoundError:
            raise CerebrumError, "No such e-mail address (%s)" % address
        if ((ttype == int(self.const.email_target_Mailman) and
             self._get_mailman_list(uname) <> self._get_mailman_list(address))
            and ea.get_target_id() <> et.email_target_id):
            raise CerebrumError, ("Address <%s> is not associated with %s" %
                                  (address, uname))
        ed = Email.EmailDomain(self.db)
        ed.find(ea.email_addr_domain_id)
        self.ba.can_email_address_add(operator.get_entity_id(),
                                      account=acc, domain=ed)
        ea.delete()
        for r in et.get_addresses():
            # there is at least one address left
            return "OK"
        # clean up and remove the target.  we remove any forward
        # addresses first.
        ef = Email.EmailForward(self.db)
        ef.find(et.email_target_id)
        for r in ef.get_forward():
            ef.delete_forward(r['forward_to'])
        et.delete()
        return "OK, also deleted e-mail target"

    # email forward "on"|"off"|"local" <account>+ [<address>+]
    all_commands['email_forward'] = Command(
        ('email', 'forward'),
        SimpleString(help_ref='email_forward_action'),
        AccountName(help_ref='account_name', repeat=True),
        EmailAddress(help_ref='email_address',
                     repeat=True, optional=True),
        perm_filter='can_email_forward_toggle')
    def email_forward(self, operator, action, uname, addr=None):
        acc = self._get_account(uname)
        self.ba.can_email_forward_toggle(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find_by_entity(acc.entity_id)
        matches = []
        prim = acc.get_primary_mailaddress()

        if addr == 'local':
            found = False
            for a in self.__get_valid_email_addrs(fw):
                if self._forward_exists(fw, a):
                    found = True
                    matches.append(a)
        else:
            for r in fw.get_forward():
                if addr is None or r['forward_to'].find(addr) <> -1:
                    matches.append(r['forward_to'])
        if addr:
            if not matches:
                raise CerebrumError, "No such forward address: %s" % addr
            elif len(matches) > 1 and addr <> 'local':
                raise CerebrumError, "More than one address matches %s" % addr
        elif not matches:
            raise CerebrumError, "No forward addresses for %s" % uname
        if action == 'local':
            action = 'on'
            if not found:
                fw.add_forward(prim)
        for a in matches:
            if action == 'on':
                fw.enable_forward(a)
            elif action == 'off':
                fw.disable_forward(a)
            else:
                raise CerebrumError, ("Unknown action (%s), " +
                                      "choose one of on, off or local") % action
        fw.write_db()
        return 'OK'

    # email add_forward <account>+ <address>+
    # account can also be an e-mail address for pure forwardtargets
    all_commands['email_add_forward'] = Command(
        ('email', 'add_forward'),
        AccountName(help_ref='account_name', repeat=True),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_forward_edit')
    def email_add_forward(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        if uname.count('@') and not acc:
            lp, dom = uname.split('@')
            ed = Email.EmailDomain(self.db)
            ed.find_by_domain(dom)
            self.ba.can_email_forward_edit(operator.get_entity_id(),
                                           domain=ed)
        else:
            self.ba.can_email_forward_edit(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find(et.email_target_id)
        addr = self._check_email_address(address)
        if addr == 'local':
            if acc:
                addr = acc.get_primary_mailaddress()
            else:
                raise CerebrumError, ("Forward address '%s' does not make sense"
                                      % addr)
        if self._forward_exists(fw, addr):
            raise CerebrumError, "Forward address added already (%s)" % addr
        fw.add_forward(addr)
        return "OK"

    # email remove_forward <account>+ <address>+
    # account can also be an e-mail address for pure forwardtargets
    all_commands['email_remove_forward'] = Command(
        ("email", "remove_forward"),
        AccountName(help_ref="account_name", repeat=True),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_forward_edit')
    def email_remove_forward(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        if uname.count('@') and not acc:
            lp, dom = uname.split('@')
            ed = Email.EmailDomain(self.db)
            ed.find_by_domain(dom)
            self.ba.can_email_forward_edit(operator.get_entity_id(),
                                           domain=ed)
        else:
            self.ba.can_email_forward_edit(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find(et.email_target_id)
        addr = self._check_email_address(address)
        if addr == 'local' and acc:
            locals = self.__get_valid_email_addrs(fw)
        else:
            locals = [addr]
        removed = 0
        for a in locals:
            if self._forward_exists(fw, a):
                fw.delete_forward(a)
                removed += 1
        if not removed:
            raise CerebrumError, "No such forward address (%s)" % addr
        return "OK"

    def _check_email_address(self, address):
        # To stop some typoes, we require that the address consists of
        # a local part and a domain, and the domain must contain at
        # least one period.  We also remove leading and trailing
        # whitespace.  We do an unanchored search as well so that an
        # address in angle brackets is accepted, e.g. either of
        # "jdoe@example.com" or "Jane Doe <jdoe@example.com>" is OK.
        address = address.strip()
        if address == 'local':
            return address
        if address.find("@") == -1:
            raise CerebrumError, "E-mail addresses must include the domain name"
        if not (re.match(r'[^@\s]+@[^@\s.]+\.[^@\s]+$', address) or
                re.search(r'<[^@>\s]+@[^@>\s.]+\.[^@>\s]+>$', address)):
            raise CerebrumError, "Invalid e-mail address (%s)" % address
        return address

    def _forward_exists(self, fw, addr):
        for r in fw.get_forward():
            if r['forward_to'] == addr:
                return True
        return False

    # email info <account>+
    all_commands['email_info'] = Command(
        ("email", "info"),
        AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_info',
        fs=FormatSuggestion([
        #
        # target_type == Account
        #
        # We use valid_addr_1 and (multiple) valid_addr to enable
        # programs to get the information reasonably easily, while
        # still keeping the suggested output format pretty.
        ("Account:          %s\nMail server:      %s (%s)\n"+
         "Default address:  %s\nValid addresses:  %s",
         ("account", "server", "server_type", "def_addr", "valid_addr_1")),
        ("                  %s",
         ("valid_addr",)),
        ("Quota:            %d MiB, warn at %d%% (not enforced)",
         ("dis_quota_hard", "dis_quota_soft")),
        ("Quota:            %d MiB, warn at %d%% (%s MiB used)",
         ("quota_hard", "quota_soft", "quota_used")),
        # TODO: change format so that ON/OFF is passed as separate value.
        # this must be coordinated with webmail code.
        ("Forwarding:       %s",
         ("forward_1", )),
        ("                  %s",
         ("forward", )),
        #
        # target_type == Mailman
        #
        ("Mailing list:     %s",
         ("mailman_list", )),
        ("Alias:            %s",
         ("mailman_alias_1", )),
        ("                  %s",
         ("mailman_alias", )),
        ("Request address:  %s",
         ("mailman_mailcmd_1", )),
        ("                  %s",
         ("mailman_mailcmd", )),
        ("Owner address:    %s",
         ("mailman_mailowner_1", )),
        ("                  %s",
         ("mailman_mailowner", )),
        # target_type == multi
        ("Primary address:  %s",
         ("multi_def_addr",)),
        ("Valid address:    %s",
         ("multi_valid_addr_1",)),
        ("                  %s",
         ("multi_valid_addr",)),
        ("Forward to group: %s",
         ("multi_forward_gr",)),
        ("Expands to:       %s",
         ("multi_forward_1",)),
        ("                  %s",
         ("multi_forward",)),
        # target_type == pipe
        ("Command:          %s\n"+
         "Run as:           %s\n"+
         "Address:          %s",
         ("pipe_cmd", "pipe_runas", "pipe_addr_1")),
        ("                  %s",
         ("pipe_addr",)),
        # target_type == forward
        ("Address:          %s",
         ("fw_target",)),
        # TODO: all these valid-addresses should share code and
        # FormatSuggestion
        ("Valid addresses:  %s",
         ("fw_valid_1",)),
        ("                  %s",
         ("fw_valid",)),
        ("Forwarding:       %s (%s)",
         ("fw_addr_1", "fw_enable_1")),
        ("                  %s (%s)",
         ("fw_addr", "fw_enable")),
        #
        # both account and Mailman
        #
        ("Spam level:       %s (%s)\nSpam action:      %s (%s)",
         ("spam_level", "spam_level_desc", "spam_action", "spam_action_desc")),
        ]))
    def email_info(self, operator, uname):
        et, acc = self.__get_email_target_and_account(uname)
        ttype = et.email_target_type
        if ttype == self.const.email_target_Mailman:
            return self._email_info_mailman(uname, et)
        elif ttype == self.const.email_target_multi:
            return self._email_info_multi(uname, et)
        elif ttype == self.const.email_target_pipe:
            return self._email_info_pipe(uname, et)
        elif ttype == self.const.email_target_forward:
            return self._email_info_forward(uname, et)
        elif ttype not in (self.const.email_target_account,
                           self.const.email_target_deleted):
            raise CerebrumError, ("email info for target type %s isn't "
                                  "implemented") % self.num2const[ttype]
        self.ba.can_email_info(operator.get_entity_id(), acc)
        addrs = self.__get_valid_email_addrs(et)
        ret = self._email_info_basic(acc, et, addrs)
        try:
            self.ba.can_email_info_detail(operator.get_entity_id(), acc)
        except PermissionDenied:
            pass
        else:
            ret += self._email_info_spam(et)
            ret += self._email_info_detail(acc, addrs)
        return ret

    def __get_valid_email_addrs(self, et, special=False):
        """Return a list of all valid e-mail addresses for the given
        EmailTarget.  Keep special domain names intact if special is
        True, otherwise re-write them into real domain names."""
        addrs = []
        for r in et.get_addresses(special=special):
            addrs.append(r['local_part'] + '@' + r['domain'])
        return addrs

    def _email_info_basic(self, acc, et, addrs):
        info = {}
        data = [ info ]
        info["account"] = acc.account_name
        est = Email.EmailServerTarget(self.db)
        try:
            est.find_by_entity(acc.entity_id)
        except Errors.NotFoundError:
            info["server"] = "<none>"
            info["server_type"] = "N/A"
        else:
            es = Email.EmailServer(self.db)
            es.find(est.email_server_id)
            info["server"] = es.name
            type = int(es.email_server_type)
            info["server_type"] = str(Email._EmailServerTypeCode(type))
        try:
            info["def_addr"] = acc.get_primary_mailaddress()
        except Errors.NotFoundError:
            info["def_addr"] = "<none>"
        if addrs:
            info["valid_addr_1"] = addrs[0]
            for idx in range(1, len(addrs)):
                data.append({"valid_addr": addrs[idx]})
        else:
            info["valid_addr_1"] = "<none>"
        return data

    def _email_info_spam(self, target):
        info = []
        esf = Email.EmailSpamFilter(self.db)
        try:
            esf.find(target.email_target_id)
            spam_lev = _EmailSpamLevelCode(int(esf.email_spam_level))
            spam_act = _EmailSpamActionCode(int(esf.email_spam_action))
            info.append({'spam_level':       str(spam_lev),
                         'spam_level_desc':  spam_lev._get_description(),
                         'spam_action':      str(spam_act),
                         'spam_action_desc': spam_act._get_description()})
        except Errors.NotFoundError:
            pass
        return info

    def _email_info_detail(self, acc, addrs):
        info = []
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
                except TimeoutException:
                    used = 'DOWN'
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
        for r in ef.get_forward():
            if r['enable'] == 'T':
                enabled = "on"
            else:
                enabled = "off"
            if r['forward_to'] in addrs:
                local_copy = "+ local delivery (%s)" % enabled
            else:
                forw.append("%s (%s) " % (r['forward_to'], enabled))
        # for aesthetic reasons, print "+ local delivery" last
        if local_copy:
            forw.append(local_copy)
        if forw:
            info.append({'forward_1': forw[0]})
            for idx in range(1, len(forw)):
                info.append({'forward': forw[idx]})
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
        # We extract the official list name from the pipe command.
        interface, listname = m.groups()
        ret = [{'mailman_list': listname}]
        if listname.count('@') == 0:
            lp = listname
            dom = addr.split('@')[1]
        else:
            lp, dom = listname.split('@')
        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(dom)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            raise CerebrumError, ("Address %s exists, but the list it points "
                                  "to, %s, does not") % (addr, listname)
        # now find all e-mail addresses
        et.clear()
        et.find(ea.email_addr_target_id)
        ret += self._email_info_spam(et)
        aliases = []
        for r in et.get_addresses():
            a = "%(local_part)s@%(domain)s" % r
            if a == listname:
                continue
            aliases.append(a)
        if aliases:
            ret.append({'mailman_alias_1': aliases[0]})
            for idx in range(1, len(aliases)):
                ret.append({'mailman_alias': aliases[idx]})
        # all administrative addresses
        for iface in ('mailcmd', 'mailowner'):
            try:
                et.clear()
                et.find_by_alias(self._mailman_pipe % { 'interface': iface,
                                                        'listname': listname} )
                addrs = et.get_addresses()
                if addrs:
                    ret.append({'mailman_' + iface + '_1':
                                '%(local_part)s@%(domain)s' % addrs[0]})
                    for idx in range(1, len(addrs)):
                        ret.append({'mailman_' + iface:
                                    '%(local_part)s@%(domain)s' % addrs[idx]})
            except Errors.NotFoundError:
                pass
        return ret

    def _email_info_multi(self, addr, et):
        ret = []
        # a multi target does not need a primary address target, but
        # let's handle it just in case.
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.email_target_id)
        except Errors.NotFoundError:
            pass
        else:
            ret.append({'multi_def_addr': self.__get_address(epat)})
        addr_list = []
        for r in et.get_addresses():
            addr_list.append("%(local_part)s@%(domain)s" % r)
        addr_list.sort()
        if addr_list:
            ret.append({'multi_valid_addr_1': addr_list[0]})
            for idx in range(1, len(addr_list)):
                ret.append({'multi_valid_addr': addr_list[idx]})
        if int(et.email_target_entity_type) <> int(self.const.entity_group):
            ret.append({'multi_forward_gr': 'ENTITY TYPE OF %d UNKNOWN' %
                        et.email_target_entity_id})
        else:
            group = self.Group_class(self.db)
            acc = self.Account_class(self.db)
            try:
                group.find(et.email_target_entity_id)
            except Errors.NotFoundError:
                ret.append({'multi_forward_gr': 'Unknown group %d' %
                            et.email_target_entity_id})
                return ret
            ret.append({'multi_forward_gr': group.group_name})
            u, i, d = group.list_members()
            fwds = []
            for member_type, member_id in u:
                if member_type <> self.const.entity_account:
                    continue
                acc.clear()
                acc.find(member_id)
                try:
                    addr = acc.get_primary_mailaddress()
                except Errors.NotFoundError:
                    addr = "(account %s has no e-mail)" % acc.account_name
                fwds.append(addr)
            if fwds:
                ret.append({'multi_forward_1': fwds[0]})
                for idx in range(1, len(fwds)):
                    ret.append({'multi_forward': fwds[idx]})
        return ret

    def _email_info_pipe(self, addr, et):
        acc = self._get_account(et.email_target_using_uid, idtype='id')
        addrs = self.__get_valid_email_addrs(et)
        data = [{'pipe_addr_1': addrs[0],
                 'pipe_cmd': et.get_alias(),
                 'pipe_runas': acc.account_name}]
        for idx in range(1, len(addrs)):
            data.append({'pipe_addr': addrs[idx]})
        return data

    def _email_info_forward(self, addr, et):
        data = []
        addrs = self.__get_valid_email_addrs(et)
        if addrs:
            data.append({'fw_valid_1': addrs[0]})
        for idx in range(1, len(addrs)):
            data.append({'fw_valid': addrs[idx]})
        # et.email_target_alias isn't used for anything, it's often
        # a copy of one of the forward addresses, but that's just a
        # waste of bytes, really.
        ef = Email.EmailForward(self.db)
        try:
            ef.find(et.email_target_id)
        except Errors.NotFoundError:
            data.append({'fw_addr_1': '<none>', 'fw_enable': 'off'})
        else:
            forw = ef.get_forward()
            if forw:
                data.append({'fw_addr_1': forw[0].forward_to,
                             'fw_enable_1': self._onoff(forw[0].enable)})
            for idx in range(1, len(forw)):
                data.append({'fw_addr': forw[idx].forward_to,
                             'fw_enable': self._onoff(forw[idx].enable)})
        return data

    # email create_archive <list-address>
    all_commands['email_create_archive'] = Command(
        ("email", "create_archive"),
        EmailAddress(help_ref="mailman_list"),
        perm_filter="can_email_archive_create")
    def email_create_archive(self, operator, listname):
        """Create e-mail address for archiving messages.  Also adds a
        request to create the needed directories on the web server."""
        lp, dom = listname.split('@')
        ed = self._get_email_domain(dom)
        self.ba.can_email_archive_create(operator.get_entity_id(), ed)
        self._check_mailman_official_name(listname)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp + "-archive",
                                             ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, ("%s-archive@%s already exists" % (lp, dom))
        archive_user = 'www'
        archive_prog = '/local/share/mta/bin/new-archive-monthly'
        arch = lp.lower() + "-archive"
        dc = dom.lower().split('.'); dc.reverse()
        archive_dir = "/uio/caesar/mailarkiv/" + ".".join(dc) + "/" + arch
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_pipe,
                    alias="|%s %s" % (archive_prog, archive_dir),
                    using_uid=self._get_account(archive_user).entity_id)
        et.write_db()
        ea = Email.EmailAddress(self.db)
        ea.populate(arch, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        # TODO: add bofh request to run mkdir on www
        return ("OK, now run ssh www 'mkdir -p %s; chown www %s; chmod o= %s'" %
                (archive_dir, archive_dir, archive_dir))


    # email delete_archive <address>
    all_commands['email_delete_archive'] = Command(
        ("email", "delete_archive"),
        EmailAddress(help_ref="email_address"),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_archive_delete")
    def email_delete_archive(self, operator, addr):
        lp, dom = addr.split('@')
        ed = self._get_email_domain(dom)
        et, acc = self.__get_email_target_and_account(addr)
        if et.email_target_type <> self.const.email_target_pipe:
            raise CerebrumError, "%s: Not an archive target" % addr
        # we can imagine passing along the name of the mailing list
        # to the auth function in the future.
        self.ba.can_email_archive_delete(operator.get_entity_id(), ed)
        # All OK, let's nuke it all.
        result = []
        ea = Email.EmailAddress(self.db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            result.append({'address': self.__get_address(ea)})
            ea.delete()
        et.delete()
        return result

    # TODO: commands for creating arbitrary pipe deliveries
    # email create_pipe <address> <uname> <command>
    # email delete_pipe <address>

    # email create_domain <domainname> <description>
    all_commands['email_create_domain'] = Command(
        ("email", "create_domain"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="string_description"),
        perm_filter="can_email_domain_create")
    def email_create_domain(self, operator, domainname, desc):
        """Create e-mail domain."""
        self.ba.can_email_archive_delete(operator.get_entity_id())
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(domainname)
            raise CerebrumError, "%s: e-mail domain already exists" % name
        except Errors.NotFoundError:
            pass
        if not re.match(r'[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+', domainname):
            raise CerebrumError, "%s: illegal e-mail domain name" % domainname
        if len(desc) < 3:
            raise CerebrumError, "Please supply a better description"
        ed.populate(domainname, desc)
        ed.write_db()
        return "OK"

    # email domain_configuration on|off <domain> <category>+
    all_commands['email_domain_configuration'] = Command(
        ("email", "domain_configuration"),
        SimpleString(help_ref="on_or_off"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="email_category", repeat=True),
        perm_filter="can_email_domain_create")
    def email_domain_configuration(self, operator, onoff, domainname, cat):
        """Change configuration for an e-mail domain."""
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        on = self._get_boolean(onoff)
        catcode = None
        for c in self.const.fetch_constants(_EmailDomainCategoryCode):
            if str(c).lower().startswith(cat.lower()):
                if catcode:
                    raise CerebrumError, ("'%s' does not uniquely identify "+
                                          "a configuration category") % cat
                catcode = c
        if catcode is None:
            raise CerebrumError, ("'%s' does not match any configuration "+
                                  "category") % cat
        if self._sync_category(ed, catcode, on):
            return "%s is now %s" % (str(catcode), onoff.lower())
        else:
            return "%s unchanged" % str(catcode)

    def _get_boolean(self, onoff):
        if onoff.lower() == 'on':
            return True
        elif onoff.lower() == 'off':
            return False
        raise CerebrumError, "Enter one of ON or OFF"

    def _onoff(self, enable):
        if enable:
            return 'on'
        else:
            return 'off'

    def _has_category(self, domain, category):
        ccode = int(category)
        for r in domain.get_categories():
            if r['category'] == ccode:
                return True
        return False

    def _sync_category(self, domain, category, enable):
        """Enable or disable category with EmailDomain.  Returns False
        for no change or True for change."""
        if self._has_category(domain, category) == enable:
            return False
        if enable:
            domain.add_category(category)
        else:
            domain.remove_category(category)
        return True

    # email domain_info <domain>
    # this command is accessible for all
    all_commands['email_domain_info'] = Command(
        ("email", "domain_info"),
        SimpleString(help_ref="email_domain"),
        fs=FormatSuggestion([
        ("E-mail domain:    %s\n"+
         "Description:      %s",
         ("domainname", "description")),
        ("Configuration:    %s",
         ("category",)),
        ("Affiliation:      %s@%s",
         ("affil", "ou"))]))
    def email_domain_info(self, operator, domainname):
        ed = self._get_email_domain(domainname)
        ret = []
        ret.append({'domainname': domainname,
                    'description': ed.email_domain_description})
        for r in ed.get_categories():
            ret.append({'category': str(self.num2const[r['category']])})
        eed = Email.EntityEmailDomain(self.db)
        affiliations = {}
        for r in eed.list_affiliations(ed.email_domain_id):
            ou = self._get_ou(r['entity_id'])
            affname = "<any>"
            if r['affiliation']:
                affname = str(self.num2const[int(r['affiliation'])])
            affiliations[self._format_ou_name(ou)] = affname
        aff_list = affiliations.keys()
        aff_list.sort()
        for ou in aff_list:
            ret.append({'affil': affiliations[ou], 'ou': ou})
        return ret

    # email add_domain_affiliation <domain> <stedkode> [<affiliation>]
    all_commands['email_add_domain_affiliation'] = Command(
        ("email", "add_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(), Affiliation(optional=True),
        perm_filter="can_email_domain_create")
    def email_add_domain_affiliation(self, operator, domainname, sko, aff=None):
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        try:
            ou = self._get_ou(stedkode=sko)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % sko
        aff_id = None
        if aff:
            aff_id = int(self._get_affiliationid(aff))
        eed = Email.EntityEmailDomain(self.db)
        try:
            eed.find(ou.entity_id, aff_id)
        except Errors.NotFoundError:
            # We have a partially initialised object, since
            # the super() call finding the OU always succeeds.
            # Therefore we must not call clear()
            eed.populate_email_domain(ed.email_domain_id, aff_id)
            eed.write_db()
            return "OK"
        else:
            old_dom = eed.entity_email_domain_id
            if old_dom <> ed.email_domain_id:
                eed.entity_email_domain_id = ed.email_domain_id
                eed.write_db()
                ed.clear()
                ed.find(old_dom)
                return "OK (was %s)" % ed.email_domain_name
            return "OK (no change)"

    # email remove_domain_affiliation <domain> <stedkode> [<affiliation>]
    all_commands['email_remove_domain_affiliation'] = Command(
        ("email", "remove_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(), Affiliation(optional=True),
        perm_filter="can_email_domain_create")
    def email_remove_domain_affiliation(self, operator, domainname, sko,
                                        aff=None):
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        try:
            ou = self._get_ou(stedkode=sko)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % sko
        aff_id = None
        if aff:
            aff_id = int(self._get_affiliationid(aff))
        eed = Email.EntityEmailDomain(self.db)
        try:
            eed.find(ou.entity_id, aff_id)
        except Errors.NotFoundError:
            raise CerebrumError, "No such affiliation for domain"
        if eed.entity_email_domain_id <> ed.email_domain_id:
            raise CerebrumError, "No such affiliation for domain"
        eed.delete()
        return "OK"

    # email create_forward <local-address> <remote-address>
    all_commands['email_create_forward'] = Command(
        ("email", "create_forward"),
        EmailAddress(),
        EmailAddress(),
        perm_filter="can_email_forward_create")
    def email_create_forward(self, operator, localaddr, remoteaddr):
        """Create a forward target, add localaddr as an address
        associated with that target, and add remoteaddr as a forward
        addresses."""
        lp, dom = localaddr.split('@')
        ed = self._get_email_domain(dom)
        self.ba.can_email_forward_create(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "Address %s already exists" % localaddr
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_forward)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        ef = Email.EmailForward(self.db)
        ef.find(et.email_target_id)
        addr = self._check_email_address(remoteaddr)
        try:
            ef.add_forward(addr)
        except Errors.TooManyRowsError:
            raise CerebrumError, "Forward address added already (%s)" % addr
        return "OK"

    # email create_list <list-address> [admin,admin,admin]
    all_commands['email_create_list'] = Command(
        ("email", "create_list"),
        EmailAddress(help_ref="mailman_list"),
        SimpleString(help_ref="mailman_admins", optional=True),
        perm_filter="can_email_list_create")
    def email_create_list(self, operator, listname, admins = None):
        """Create e-mail addresses listname needs to be a Mailman
        list.  Also adds a request to create the list on the Mailman
        server."""
        lp, dom = listname.split('@')
        ed = self._get_email_domain(dom)
        op = operator.get_entity_id()
        self.ba.can_email_list_create(op, ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "Address %s already exists" % listname
        try:
            self._get_account(lp)
        except CerebrumError:
            pass
        else:
            raise CerebrumError, ("Won't create list %s, as %s is an "
                                  "existing username") % (listname, lp)
        self._register_list_addresses(listname, lp, dom)
        if admins:
            br = BofhdRequests(self.db, self.const)
            ea.clear()
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
            list_id = ea.email_addr_id
            admin_list = []
            for addr in admins.split(","):
                if addr.count('@') == 0:
                    admin_list.append(addr + "@UIO_HOST")
                else:
                    admin_list.append(addr)
            ea.clear()
            try:
                ea.find_by_address(admin_list[0])
            except Errors.NotFoundError:
                raise CerebrumError, "%s: unknown address" % admin_list[0]
            req = br.add_request(op, br.now, self.const.bofh_mailman_create,
                                 list_id, ea.email_addr_id, None)
            for addr in admin_list[1:]:
                ea.clear()
                try:
                    ea.find_by_address(addr)
                except Errors.NotFoundError:
                    raise CerebrumError, "%s: unknown address" % addr
                br.add_request(op, br.now, self.const.bofh_mailman_add_admin,
                               list_id, ea.email_addr_id, str(req))
        return "OK"

    # email create_list_alias <list-address> <new-alias>
    all_commands['email_create_list_alias'] = Command(
        ("email", "create_list_alias"),
        EmailAddress(help_ref="mailman_list_exist"),
        EmailAddress(help_ref="mailman_list"),
        perm_filter="can_email_list_create")
    def email_create_list_alias(self, operator, listname, address):
        """Create a secondary name for an existing Mailman list."""
        lp, dom = address.split('@')
        ed = self._get_email_domain(dom)
        self.ba.can_email_list_create(operator.get_entity_id(), ed)
        self._check_mailman_official_name(listname)
        try:
            self._get_account(lp)
        except CerebrumError:
            pass
        else:
            raise CerebrumError, ("Won't create list %s, as %s is an "
                                  "existing username") % (address, lp)
        # we _don't_ check for "more than 8 characters in local
        # part OR it contains hyphen" since we assume the people
        # who have access to this command know what they are doing
        self._register_list_addresses(listname, lp, dom)
        return "OK"

    # email delete_list <list-address>
    all_commands['email_delete_list'] = Command(
        ("email", "delete_list"),
        EmailAddress(help_ref="mailman_list"),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_list_delete")
    def email_delete_list(self, operator, listname):
        lp, dom = listname.split('@')
        ed = self._get_email_domain(dom)
        op = operator.get_entity_id()
        self.ba.can_email_list_delete(op, ed)
        self._check_mailman_official_name(listname)
        # All OK, let's nuke it all.
        result = []
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        list_id = ea.email_addr_id
        for interface in self._interface2addrs.keys():
            alias = self._mailman_pipe % { 'interface': interface,
                                           'listname': listname }
            try:
                et.clear()
                et.find_by_alias(alias)
                for r in et.get_addresses():
                    addr = '%(local_part)s@%(domain)s' % r
                    ea.clear()
                    ea.find_by_address(addr)
                    ea.delete()
                    result.append({'address': addr})
            except Errors.NotFoundError:
                pass
        br = BofhdRequests(self.db, self.const)
        br.add_request(op, br.now, self.const.bofh_mailman_remove,
                       list_id, None, listname)
        return result

    def _get_mailman_list(self, listname):
        """Returns the official name for the list, or raise an error
        if listname isn't a Mailman list."""
        try:
            ea = Email.EmailAddress(self.db)
            ea.find_by_address(listname)
        except Errors.NotFoundError:
            raise CerebrumError, "No such mailman list %s" % listname
        et = Email.EmailTarget(self.db)
        et.find(ea.get_target_id())
        if not et.email_target_alias:
            raise CerebrumError, "%s isn't a Mailman list" % listname
        m = re.match(self._mailman_patt, et.email_target_alias)
        if not m:
            raise CerebrumError, ("Unrecognised pipe command for Mailman list:"+
                                  et.email_target_alias)
        return m.group(2)
    
    def _check_mailman_official_name(self, listname):
        mlist = self._get_mailman_list(listname)
        if mlist is None:
            raise CerebrumError, "%s is not a Mailman list" % listname
        if listname <> mlist:
            raise CerebrumError, ("%s is not the official name of the list %s" %
                                  (listname, mlist))


    def _register_list_addresses(self, listname, lp, dom):
        """Add list, owner and request addresses.  listname is the
        name in Mailman, which may be different from lp@dom, which is
        the basis for the local parts and domain of the addresses
        which should be added."""
        
        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(dom)

        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, ("The address %s@%s is already in use" %
                                  (lp, dom))

        mailman = self._get_account("mailman", actype="PosixUser")

        for interface in self._interface2addrs.keys():
            targ = self._mailman_pipe % { 'interface': interface,
                                          'listname': listname }
            found_target = False
            for addr_format in self._interface2addrs[interface]:
                addr = addr_format % {'local_part': lp,
                                      'domain': dom}
                addr_lp, addr_dom = addr.split('@')
                # all addresses are in same domain, do an EmailDomain
                # lookup here if  _interface2addrs changes:
                try:
                    ea.clear()
                    ea.find_by_local_part_and_domain(addr_lp,
                                                     ed.email_domain_id)
                    raise CerebrumError, ("Can't add list %s, as the "
                                          "address %s is already in use"
                                          ) % (newaddr, addr)
                except Errors.NotFoundError:
                    pass
                if not found_target:
                    et.clear()
                    try:
                        et.find_by_alias_and_account(targ, mailman.entity_id)
                    except Errors.NotFoundError:
                        et.populate(self.const.email_target_Mailman,
                                    alias=targ, using_uid=mailman.entity_id)
                        et.write_db()
                    found_target = True
                ea.clear()
                ea.populate(addr_lp, ed.email_domain_id, et.email_target_id)
                ea.write_db()

    # email create_multi <multi-address> <group>
    all_commands['email_create_multi'] = Command(
        ("email", "create_multi"),
        EmailAddress(help_ref="email_address"),
        GroupName(help_ref="group_name_dest"),
        perm_filter="can_email_multi_create")
    def email_create_multi(self, operator, addr, group):
        """Create en e-mail target of type 'multi' expanding to
        members of group, and associate the e-mail address with this
        target."""
        lp, dom = addr.split('@')
        ed = self._get_email_domain(dom)
        gr = self._get_group(group)
        self.ba.can_email_multi_create(operator.get_entity_id(), ed, gr)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "Address <%s> is already in use" % addr
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_multi,
                    entity_type = self.const.entity_group,
                    entity_id = gr.entity_id)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        epat.populate(ea.email_addr_id, parent=et)
        epat.write_db()
        return "OK"

    # email delete_multi <address>
    all_commands['email_delete_multi'] = Command(
        ("email", "delete_multi"),
        EmailAddress(help_ref="email_address"),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_multi_delete")
    def email_delete_multi(self, operator, addr):
        lp, dom = addr.split('@')
        ed = self._get_email_domain(dom)
        et, acc = self.__get_email_target_and_account(addr)
        if et.email_target_type <> self.const.email_target_multi:
            raise CerebrumError, "%s: Not a multi target" % addr
        if et.email_target_entity_type <> self.const.entity_group:
            raise CerebrumError, "%s: Does not point to a group!" % addr
        gr = self._get_group(et.email_target_entity_id, idtype="id")
        self.ba.can_email_multi_delete(operator.get_entity_id(), ed, gr)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.email_target_id)
        except Errors.NotFoundError:
            # a multi target does not need a primary address
            pass
        else:
            # but if one exists, we require the user to supply that
            # address, not an arbitrary alias.
            if addr <> self.__get_address(epat):
                raise CerebrumError, ("%s is not the primary address of "+
                                      "the target") % addr
            epat.delete()
        # All OK, let's nuke it all.
        result = []
        ea = Email.EmailAddress(self.db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            result.append({'address': self.__get_address(ea)})
            ea.delete()
        return result

    # email migrate
    all_commands['email_migrate'] = Command(
        ("email", "migrate"),
        AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_migrate')
    def email_migrate(self, operator, uname):
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_migrate(op, acc)
        for r in acc.get_spread():
            if r['spread'] == int(self.const.spread_uio_imap):
                raise CerebrumError, "%s is already an IMAP user" % uname
        acc.add_spread(self.const.spread_uio_imap)
        if op <> acc.entity_id:
            # the local sysadmin should get a report as well, if
            # possible, so change the request add_spread() put in so
            # that he is named as the requestee.  the list of requests
            # may turn out to be empty, ie. processed already, but this
            # unlikely race condition is too hard to fix.
            br = BofhdRequests(self.db, self.const)
            for r in br.get_requests(operation=self.const.bofh_email_move,
                                     entity_id=acc.entity_id):
                br.delete_request(request_id=r['request_id'])
                br.add_request(op, r['run_at'], r['operation'], r['entity_id'],
                               r['destination_id'], r['state_data'])
        return 'OK'

    # email move
    all_commands['email_move'] = Command(
        ("email", "move"),
        AccountName(help_ref="account_name", repeat=True),
        SimpleString(help_ref='string_email_host'),
        perm_filter='can_email_move')
    def email_move(self, operator, uname, server):
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        est = Email.EmailServerTarget(self.db)
        est.find_by_entity(acc.entity_id)
        old_server = est.email_server_id
        es = Email.EmailServer(self.db)
        es.find_by_name(server)
        if old_server == es.entity_id:
            raise CerebrumError, "User is already at %s" % server
        est.populate(es.entity_id)
        est.write_db()
        if es.email_server_type == self.const.email_server_type_cyrus:
            spreads = [int(r['spread']) for r in acc.get_spread()]
            br = BofhdRequests(self.db, self.const)
            if not self.const.spread_uio_imap in spreads:
                acc.add_spread(self.const.spread_uio_imap)
                # Since server was chosen already, add_spread() has
                # only queued a create request, not a move request.
                # Look up the create request so we get the dependency
                # right.
                for r in br.get_requests(operation=self.const.bofh_email_create,
                                         entity_id=acc.entity_id):
                    req = r['request_id']
            else:
                # We need to create the new e-mail account ourselves.
                req = br.add_request(operator.get_entity_id(), br.now,
                                     self.const.bofh_email_create,
                                     acc.entity_id, est.email_server_id)

            # Now add a move request.
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_email_move,
                           acc.entity_id, old_server, state_data=req)
        else:
            # TBD: should we remove spread_uio_imap ?
            # It does not do much good to add to a bofh request, mvmail
            # can't handle this anyway.
            raise NotImplementedError, "can't move to non-IMAP server" 
        return "OK"

    # email quota <uname>+ hardquota-in-mebibytes [softquota-in-percent]
    all_commands['email_quota'] = Command(
        ('email', 'quota'),
        AccountName(help_ref='account_name', repeat=True),
        Integer(help_ref='number_size_mib'),
        Integer(help_ref='number_percent', optional=True),
        perm_filter='can_email_set_quota')
    def email_quota(self, operator, uname, hquota, squota=90):
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_set_quota(op, acc)
        hquota = int(hquota)
        if hquota < 100:
            raise CerebrumError, "The hard quota can't be less than 100 MiB"
        if hquota > 1024*1024:
            raise CerebrumError, "The hard quota can't be more than 1 TiB"
        squota = int(squota)
        if squota < 10 or squota > 99:
            raise CerebrumError, ("The soft quota must be in the interval "+
                                  "10% to 99%")
        et = Email.EmailTarget(self.db)
        try:
            et.find_by_entity(acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError, ("The account %s has no e-mail data "+
                                  "associated with it") % uname
        eq = Email.EmailQuota(self.db)
        change = False
        try:
            eq.find_by_entity(acc.entity_id)
            if eq.email_quota_hard <> hquota:
                change = True
            eq.email_quota_hard = hquota
            eq.email_quota_soft = squota
        except Errors.NotFoundError:
            eq.clear()
            eq.populate(squota, hquota, parent=et)
            change = True
        eq.write_db()
        if change:
            br = BofhdRequests(self.db, self.const)
            # if this operator has already asked for a quota change, but
            # process_bofh_requests hasn't run yet, delete the existing
            # request to avoid the annoying error message.
            for r in br.get_requests(operation=self.const.bofh_email_hquota,
                                     operator_id=op, entity_id=acc.entity_id):
                br.delete_request(request_id=r['request_id'])
            br.add_request(op, br.now, self.const.bofh_email_hquota,
                           acc.entity_id, None)
        return "OK"

    # email spam_level <level> <uname>+
    all_commands['email_spam_level'] = Command(
        ('email', 'spam_level'),
        SimpleString(help_ref='spam_level'),
        AccountName(help_ref='account_name', repeat=True),
        perm_filter='can_email_spam_settings')
    def email_spam_level(self, operator, level, uname):
        """Set the spam level for the EmailTarget associated with username.
        It is also possible for super users to pass the name of a mailing
        list."""
        levelcode = None
        for c in self.const.fetch_constants(_EmailSpamLevelCode):
            if str(c).startswith(level):
                if levelcode:
                    raise CerebrumError, ("'%s' does not uniquely identify "+
                                          "a spam level") % level
                levelcode = c
        if not levelcode:
            raise CerebrumError, "Spam level code not found: %s" % level
        et, acc = self.__get_email_target_and_account(uname)
        self.ba.can_email_spam_settings(operator.get_entity_id(), acc, et)
        esf = Email.EmailSpamFilter(self.db)
        try:
            esf.find(et.email_target_id)
            esf.email_spam_level = levelcode
        except Errors.NotFoundError:
            esf.clear()
            esf.populate(levelcode, self.const.email_spam_action_none,
                         parent=et)
        esf.write_db()
        return "OK"

    # email spam_action <action> <uname>+
    # 
    # (This code is cut'n'paste of email_spam_level(), only the call
    # to populate() had to be fixed manually.  It's hard to fix this
    # kind of code duplication cleanly.)
    all_commands['email_spam_action'] = Command(
        ('email', 'spam_action'),
        SimpleString(help_ref='spam_action'),
        AccountName(help_ref='account_name', repeat=True),
        perm_filter='can_email_spam_settings')
    def email_spam_action(self, operator, action, uname):
        """Set the spam action for the EmailTarget associated with username.
        It is also possible for super users to pass the name of a mailing
        list."""
        actioncode = None
        for c in self.const.fetch_constants(_EmailSpamActionCode):
            if str(c).startswith(action):
                if actioncode:
                    raise CerebrumError, ("'%s' does not uniquely identify "+
                                          "a spam action") % action
                actioncode = c
        if not actioncode:
            raise CerebrumError, "Spam action code not found: %s" % action
        et, acc = self.__get_email_target_and_account(uname)
        self.ba.can_email_spam_settings(operator.get_entity_id(), acc, et)
        esf = Email.EmailSpamFilter(self.db)
        try:
            esf.find(et.email_target_id)
            esf.email_spam_action = actioncode
        except Errors.NotFoundError:
            esf.clear()
            esf.populate(self.const.email_spam_level_none, actioncode,
                         parent=et)
        esf.write_db()
        return "OK"

    # email tripnote on|off <uname> [<begin-date>]
    all_commands['email_tripnote'] = Command(
        ('email', 'tripnote'),
        SimpleString(help_ref='email_tripnote_action'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_toggle')
    def email_tripnote(self, operator, action, uname, when=None):
        if action == 'on':
            enable = True
        elif action == 'off':
            enable = False
        else:
            raise CerebrumError, ("Unknown tripnote action '%s', choose one "+
                                  "of on or off") % action
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_toggle(operator.get_entity_id(), acc)
        ev = Email.EmailVacation(self.db)
        ev.find_by_entity(acc.entity_id)
        if enable is not None:
            opposite_status = not enable
        date = self._find_tripnote(uname, ev, when, opposite_status)
        ev.enable_vacation(date, enable)
        ev.write_db()
        return "OK"

    all_commands['email_list_tripnotes'] = Command(
        ('email', 'list_tripnotes'),
        AccountName(help_ref='account_name'),
        perm_filter='can_email_tripnote_toggle',
        fs=FormatSuggestion([
        ('%s%s -- %s: %s\n%s\n',
         ("dummy", format_day('start_date'), format_day('end_date'),
          "enable", "text"))]))
    def email_list_tripnotes(self, operator, uname):
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_toggle(operator.get_entity_id(), acc)
        try:
            self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
            hide = False
        except:
            hide = True
        ev = Email.EmailVacation(self.db)
        ev.find_by_entity(acc.entity_id)
        now = self._today()
        act_date = None
        for r in ev.get_vacation():
            if r['start_date'] > r['end_date']:
                # TODO: should use logger -- but how to access it?
                # logger.warn("bogus tripnote for %s, start at %s, end at %s",
                #             uname, r['start_date'], r['end_date'])
                print ("WARNING: bogus tripnote for %s, start at %s, end at %s"
                       % (uname, r['start_date'], r['end_date']))
                ev.delete_vacation(r['start_date'])
                ev.write_db()
                continue
            if r['enable'] == 'F':
                continue
            if r['end_date'] < now:
                continue
            if r['start_date'] > now:
                break
            # get_vacation() returns a list ordered by start_date, so
            # we know this one is newer.
            act_date = r['start_date']
        result = []
        for r in ev.get_vacation():
            text = r['vacation_text']
            if r['enable'] == 'F':
                enable = "OFF"
            elif r['end_date'] < now:
                enable = "OLD"
            elif r['start_date'] > now:
                enable = "PENDING"
            else:
                enable = "ON"
            if r['start_date'] == act_date:
                enable = "ACTIVE"
            elif hide:
                text = "<text is hidden>"
            lines = text.split('\n')
            if len(lines) > 3:
                lines[2] += "[...]"
            text = '\n'.join(lines[:3])
            # TODO: FormatSuggestion won't work with a format_day()
            # coming first, so we use an empty dummy string as a
            # workaround.
            result.append({'dummy': "",
                           'start_date': r['start_date'],
                           'end_date': r['end_date'],
                           'enable': enable,
                           'text': text})
        if result:
            return result
        else:
            return "No tripnotes for %s" % uname
    
    # email add_tripnote <uname> <text> <begin-date>[-<end-date>]
    all_commands['email_add_tripnote'] = Command(
        ('email', 'add_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='tripnote_text'),
        SimpleString(help_ref='string_from_to'),
        perm_filter='can_email_tripnote_edit')
    def email_add_tripnote(self, operator, uname, text, when=None):
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
        date_start, date_end = self._parse_date_from_to(when)
        now = self._today()
        if date_end < now:
            raise CerebrumError, "Won't add already obsolete tripnotes"
        ev = Email.EmailVacation(self.db)
        ev.find_by_entity(acc.entity_id)
        for v in ev.get_vacation():
            if v['start_date'] == date_start:
                raise CerebrumError, ("There's a tripnote starting on %s "+
                                      "already") % str(date_start)[:10]
        text = text.replace('\\n', '\n')
        ev.add_vacation(date_start, text, date_end, enable=True)
        ev.write_db()
        return "OK"

    # email remove_tripnote <uname> [<when>]
    all_commands['email_remove_tripnote'] = Command(
        ('email', 'remove_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_edit')
    def email_remove_tripnote(self, operator, uname, when=None):
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
        start = self._parse_date(when)
        ev = Email.EmailVacation(self.db)
        ev.find_by_entity(acc.entity_id)
        date = self._find_tripnote(uname, ev, when)
        ev.delete_vacation(date)
        ev.write_db()
        return "OK"

    def _find_tripnote(self, uname, ev, when=None, enabled=None):
        vacs = ev.get_vacation()
        if enabled is not None:
            nv = []
            for v in vacs:
                if (v['enable'] == 'T') == enabled:
                    nv.append(v)
            vacs = nv
        if len(vacs) == 0:
            if enabled is None:
                raise CerebrumError, "User %s has no stored tripnotes" % uname
            elif enabled:
                raise CerebrumError, "User %s has no enabled tripnotes" % uname
            else:
                raise CerebrumError, "User %s has no disabled tripnotes" % uname
        elif len(vacs) == 1:
            return vacs[0]['start_date']
        elif when is None:
            raise CerebrumError, ("User %s has more than one tripnote, "+
                                  "specify which one by adding the "+
                                  "start date to command") % uname
        start = self._parse_date(when)
        best = None
        for r in vacs:
            delta = abs (r['start_date'] - start)
            if best is None or delta < best_delta:
                best = r['start_date']
                best_delta = delta
        # TODO: in PgSQL, date arithmetic is in days, but casting
        # it to int returns seconds.  The behaviour is undefined
        # in the DB-API.
        if abs(int(best_delta)) > 1.5*86400:
            raise CerebrumError, ("There are no tripnotes starting "+
                                  "at %s") % when
        return best

    # email update <uname>
    # Anyone can run this command.  Ideally, it should be a no-op,
    # and we should remove it when that is true.
    all_commands['email_update'] = Command(
        ('email', 'update'),
        AccountName(help_ref='account_name', repeat=True))
    def email_update(self, operator, uname):
        acc = self._get_account(uname)
        acc.update_email_addresses()
        return "OK"

    # (email virus)

    def __get_email_target_and_account(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et = Email.EmailTarget(self.db)
        acc = None
        if address.count('@'):
            try:
                ea = Email.EmailAddress(self.db)
                ea.find_by_address(address)
                et.find(ea.email_addr_target_id)
            except Errors.NotFoundError:
                raise CerebrumError, "No such address: '%s'" % address
            if et.email_target_type in (self.const.email_target_account,
                                        self.const.email_target_deleted):
                acc = self._get_account(et.email_target_entity_id, idtype='id')
        else:
            acc = self._get_account(address)
            try:
                et.find_by_entity(acc.entity_id)
            except Errors.NotFoundError:
                raise CerebrumError, ("Account '%s' has no email target" %
                                      address)
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

    #
    # entity commands
    #
    all_commands['entity_info'] = None
    def entity_info(self, operator, entity_id):
        """Returns basic information on the given entity id"""
        entity = self._get_entity(id=entity_id)
        return self._entity_info(entity)

    def _entity_info(self, entity):
        result = {}
        result['type'] = self.num2str(entity.entity_type)
        result['entity_id'] = entity.entity_id
        if entity.entity_type in \
            (self.const.entity_group, self.const.entity_account): 
            result['creator_id'] = entity.creator_id
            result['create_date'] = entity.create_date
            result['expire_date'] = entity.expire_date
            # FIXME: Should be a list instead of a string, but text clients doesn't 
            # know how to view such a list
            result['spread'] = ", ".join([self.num2str(a.spread)
                                         for a in entity.get_spread()])
        if entity.entity_type == self.const.entity_group:
            result['name'] = entity.group_name
            result['description'] = entity.description
            result['visibility'] = entity.visibility
            try:
                result['gid'] = entity.posix_gid
            except AttributeError:
                pass    
        elif entity.entity_type == self.const.entity_account:
            result['name'] = entity.account_name
            result['owner_id'] = entity.owner_id
            #result['home'] = entity.home
           # TODO: de-reference disk_id
            #result['disk_id'] = entity.disk_id
           # TODO: de-reference np_type
           # result['np_type'] = entity.np_type
        elif entity.entity_type == self.const.entity_person:   
            result['name'] = entity.get_name(self.const.system_cached,
                                             getattr(self.const,
                                                     cereconf.DEFAULT_GECOS_NAME))
            result['export_id'] = entity.export_id
            result['birthdate'] =  entity.birth_date
            result['description'] = entity.description
            result['gender'] = self.num2str(entity.gender)
            # make boolean
            result['deceased'] = entity.deceased == 'T'
            names = []
            for name in entity.get_all_names():
                source_system = self.num2str(name.source_system)
                name_variant = self.num2str(name.name_variant)
                names.append((source_system, name_variant, name.name))
            result['names'] = names    
            affiliations = []
            for row in entity.get_affiliations():
                affiliation = {}
                affiliation['ou'] = row['ou_id']
                affiliation['affiliation'] = self.num2str(row.affiliation)
                affiliation['status'] = self.num2str(row.status)
                affiliation['source_system'] = self.num2str(row.source_system)
                affiliations.append(affiliation)
            result['affiliations'] = affiliations     
        elif entity.entity_type == self.const.entity_ou:
            for attr in '''name acronym short_name display_name
                           sort_name'''.split():
                result[attr] = getattr(entity, attr)               
                
        return result
    
    # entity history
    all_commands['entity_history'] = None
    def entity_history(self, operator, entity_id, limit=100):
        entity = self._get_entity(id=entity_id)
        self.ba.can_show_history(operator.get_entity_id(), entity)
        result = self.db.get_log_events(any_entity=entity_id)
        events = []
        entities = Set()
        change_types = Set()
        # (dirty way of unwrapping DB-iterator) 
        result = [r for r in result]
        # skip all but the last entries 
        result = result[-limit:]
        for row in result:
            event = {}
            change_type = int(row['change_type_id'])
            change_types.add(change_type)
            event['type'] = change_type

            event['date'] = row['tstamp']
            event['subject'] = row['subject_entity']
            event['dest'] = row['dest_entity']
            params = row['change_params']
            if params:
                params = pickle.loads(params)
            event['params'] = params
            change_by = row['change_by']
            if change_by:
                entities.add(change_by)
                event['change_by'] = change_by
            else:
                event['change_by'] = row['change_program']
            entities.add(event['subject'])
            entities.add(event['dest'])
            events.append(event)
        # Resolve to entity_info, return as dict
        entities = dict([(str(e), self._entity_info(e)) 
                        for e in entities if e])
        # resolv change_types as well, return as dict
        change_types = dict([(str(t), self.change_type2details.get(t))
                        for t in change_types])
        return events, entities, change_types

    #
    # group commands
    #

    # group add
    all_commands['group_add'] = Command(
        ("group", "add"), AccountName(help_ref="account_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_add(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="account")

    # group gadd
    all_commands['group_gadd'] = Command(
        ("group", "gadd"), GroupName(help_ref="group_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_gadd(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="group")

    def _group_add(self, operator, src_name, dest_group,
                  group_operator=None, type=None):
        if type == "group":
            src_entity = self._get_group(src_name)
        elif type == "account":
            src_entity = self._get_account(src_name)
        return self._group_add_entity(operator, src_entity, 
                                      dest_group, group_operator)    

    def _group_add_entity(self, operator, src_entity, dest_group,
                          group_operator=None):
        group_operator = self._get_group_opcode(group_operator)
        group_d = self._get_group(dest_group)
        if operator:
            self.ba.can_alter_group(operator.get_entity_id(), group_d)
        # Make the error message for the most common operator error
        # more friendly.  Don't treat this as an error, useful if the
        # operator has specified more than one entity.
        if group_d.has_member(src_entity.entity_id, src_entity.entity_type,
                              group_operator):
            return ("%s is already a member of %s" %
                    (self._get_name_from_object(src_entity), dest_group))
        # This can still fail, e.g., if the entity is a member with a
        # different operation.
        try:
            group_d.add_member(src_entity.entity_id, src_entity.entity_type,
                               group_operator)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK"

    # group add_entity
    all_commands['group_add_entity'] = None
    def group_add_entity(self, operator, src_entity_id, dest_group_id,
                  group_operator=None):
        """Adds a entity to a group. Both the source entity and the group
           should be entity IDs"""          
        # tell _group_find later on that dest_group is a entity id          
        dest_group = 'id:%s' % dest_group_id
        src_entity = self._get_entity(id=src_entity_id)
        if not src_entity.entity_type in \
            (self.const.entity_account, self.const.entity_group):
            raise CerebrumError, \
              "Entity %s is not a legal type " \
              "to become group member" % src_entity_id
        return self._group_add_entity(operator, src_entity, dest_group,
                               group_operator)

    # group create
    all_commands['group_create'] = Command(
        ("group", "create"), GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="string_description"),
        fs=FormatSuggestion("Group created as a normal group, internal id: %i", ("group_id",)),
        perm_filter='can_create_group')
    def group_create(self, operator, groupname, description):
        self.ba.can_create_group(operator.get_entity_id())
        g = self.Group_class(self.db)
        g.populate(creator_id=operator.get_entity_id(),
                   visibility=self.const.group_visibility_all,
                   name=groupname, description=description)
        try:
            g.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(g.entity_id)}

    # group request, like group create, but only send request to
    # people with the access to the 'group create' command

    all_commands['group_request'] = Command(
        ("group", "request"), GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="string_description"), SimpleString(help_ref="string_spread"),
	GroupName(help_ref="group_name_moderator"))    

    def group_request(self, operator, groupname, description, spread, moderator):
	opr = operator.get_entity_id()
        acc = self.Account_class(self.db)
	acc.find(opr)
        fromaddr = acc.get_primary_mailaddress()
	toaddr = cereconf.GROUP_REQUESTS_SENDTO
	spreadstring = "(" + spread + ")"
	spreads = []
	spreads = re.split(" ",spread)
	subject = "Cerebrum group create request %s" % groupname
	body = []
	body.append("Please create a new group:")
	body.append("")
	body.append("Groupname: %s." % groupname)
	body.append("Description:  %s" % description)
	body.append("Requested by: %s" % fromaddr)
	body.append("Moderator: %s" % moderator)
	body.append("")
	body.append("group create %s \"%s\"" % (groupname, description))
	for i in range(len(spreads)):
	    if (self._get_constant(spreads[i],"No such spread") in \
		[self.const.spread_nis_fg,self.const.spread_ans_nis_fg]):
                pg = PosixGroup.PosixGroup(self.db)
		if not pg.illegal_name(groupname):
		    body.append("group promote_posix %s" % groupname)
		else:
		    raise CerebrumError, "Illegal groupname, max 8 characters allowed."
		    break
	    else:
		pass	    
	body.append("spread add group %s %s" % (groupname, spreadstring))
	body.append("access grant group_mod %s group %s" (moderator, groupname))
	body.append("")
	body.append("")
        Utils.sendmail(toaddr, fromaddr, subject, "\n".join(body))
	return "Request sent to brukerreg@hia.no"

    #  group def
    all_commands['group_def'] = Command(
        ('group', 'def'), AccountName(), GroupName(help_ref="group_name_dest"))
    def group_def(self, operator, accountname, groupname):
        account = self._get_account(accountname, actype="PosixUser")
        grp = self._get_group(groupname, grtype="PosixGroup")
        op = operator.get_entity_id()
        self.ba.can_set_default_group(op, account, grp)
        account.gid_id = grp.entity_id
        account.write_db()
        return "OK"

    # group delete
    all_commands['group_delete'] = Command(
        ("group", "delete"), GroupName(), YesNo(help_ref="yes_no_force", default="No"),
        perm_filter='can_delete_group')
    def group_delete(self, operator, groupname, force=None):
        grp = self._get_group(groupname)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        if self._is_yes(force):
##             u, i, d = grp.list_members()
##             for op, tmp in ((self.const.group_memberop_union, u),
##                             (self.const.group_memberop_intersection, i),
##                             (self.const.group_memberop_difference, d)):
##                 for m in tmp:
##                     grp.remove_member(m[1], op)
            try:
                pg = self._get_group(groupname, grtype="PosixGroup")
                pg.delete()
            except CerebrumError:
                pass   # Not a PosixGroup
        grp.delete()
        return "OK"

    # group remove
    all_commands['group_remove'] = Command(
        ("group", "remove"), AccountName(help_ref="account_name_member", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_remove(self, operator, src_name, dest_group,
                     group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="account")

    # group gremove
    all_commands['group_gremove'] = Command(
        ("group", "gremove"), GroupName(repeat=True),
        GroupName(repeat=True), GroupOperation(optional=True),
        perm_filter='can_alter_group')
    def group_gremove(self, operator, src_name, dest_group,
                      group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="group")

    def _group_remove(self, operator, src_name, dest_group,
                      group_operator=None, type=None):
        if type == "group":
            src_entity = self._get_group(src_name)
        elif type == "account":
            src_entity = self._get_account(src_name)
        group_d = self._get_group(dest_group)
        return self._group_remove_entity(operator, src_entity, group_d,
                                         group_operator)

    def _group_remove_entity(self, operator, member, group,
                             group_operation):
        group_operation = self._get_group_opcode(group_operation)
        self.ba.can_alter_group(operator.get_entity_id(), group)
        if not group.has_member(member.entity_id, member.entity_type,
                                group_operation):
            return ("%s isn't a member of %s" %
                    (self._get_name_from_object(member), group.group_name))
        try:
            group.remove_member(member.entity_id, group_operation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK"

    # group remove_entity
    all_commands['group_remove_entity'] = None
    def group_remove_entity(self, operator, member_entity, group_entity,
                            group_operation):
        group = self._get_entity(id=group_entity)
        member = self._get_entity(id=member_entity)
        return self._group_remove_entity(operator, member, 
                                         group, group_operation)
                               
    
    # group info
    all_commands['group_info'] = Command(
        ("group", "info"), GroupName(),
        fs=FormatSuggestion([("Name:         %s\n" +
                              "Spreads:      %s\n" +
                              "Description:  %s\n" +
                              "Expire:       %s\n" +
                              "Entity id:    %i""",
                              ("name", "spread", "description",
                               format_day("expire_date"),
                               "entity_id")),
                             ("Moderator:    %s %s (%s)",
                              ('owner_type', 'owner', 'opset')),
                             ("Gid:          %i",
                              ('gid',))]))
    def group_info(self, operator, groupname):
        # TODO: Group visibility should probably be checked against
        # operator for a number of commands
        try:
            grp = self._get_group(groupname, grtype="PosixGroup")
        except CerebrumError:
            grp = self._get_group(groupname)
        ret = [ self._entity_info(grp) ]
        # find owners
        aot = BofhdAuthOpTarget(self.db)
        targets = []
        for row in aot.list(target_type='group', entity_id=grp.entity_id):
            targets.append(int(row['op_target_id']))
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for row in ar.list_owners(targets):
            aos.clear()
            aos.find(row['op_set_id'])
            id = int(row['entity_id'])
            en = self._get_entity(id=id)
            if en.entity_type == self.const.entity_account:
                owner = en.account_name
            elif en.entity_type == self.const.entity_group:
                owner = en.group_name
            else:
                owner = '#%d' % id
            ret.append({'owner_type': str(self.num2const[int(en.entity_type)]),
                        'owner': owner,
                        'opset': aos.name})
        return ret

    # group list
    all_commands['group_list'] = Command(
        ("group", "list"), GroupName(),
        fs=FormatSuggestion("%-9s %-10s %s", ("op", "type", "name"),
                            hdr="%-9s %-10s %s" % ("MemberOp","Type","Name")))
    def group_list(self, operator, groupname):
        """List direct members of group"""
        def compare(a, b):
            return cmp(a['type'], b['type']) or cmp(a['name'], b['name'])
        group = self._get_group(groupname)
        ret = []
        u, i, d = group.list_members(get_entity_name=True)
        for t, rows in ((str(self.const.group_memberop_union), u),
                        (str(self.const.group_memberop_intersection), i),
                        (str(self.const.group_memberop_difference), d)):
            unsorted = []
            for r in rows:
                # yes, we COULD have used row NAMES instead of
                # numbers, but somebody decided to return simple 
                # tuples instead of the usual db_row objects ...
                unsorted.append({'op': t,
                                 'id': r[1],
                                 'type': str(self.num2const[int(r[0])]),
                                 'name': r[2]})
            unsorted.sort(compare)
            ret.extend(unsorted)
        return ret

    # group list_all
    all_commands['group_list_all'] = Command(
        ("group", "list_all"), SimpleString(help_ref="string_group_filter", optional=True),
        fs=FormatSuggestion("%8i %s", ("id", "name"), hdr="%8s %s" % ("Id", "Name")),
        perm_filter='is_superuser')
    def group_list_all(self, operator, filter=None):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers (is is slooow)")
        # superseeded by group_search - note that filter (which was never
        # implemented) is NOT passed on   
        return self.group_search(operator)    

    # group list_expanded
    all_commands['group_list_expanded'] = Command(
        ("group", "list_expanded"), GroupName(),
        fs=FormatSuggestion("%8i %s", ("member_id", "name"), hdr="Id       Name"))
    def group_list_expanded(self, operator, groupname):
        """List members of group after expansion"""
        group = self._get_group(groupname)
        return [{'member_id': a[0],
                 'name': a[1]
                 } for a in group.get_members(get_entity_name=True)]

    # group personal <uname>+
    all_commands['group_personal'] = Command(
        ("group", "personal"), AccountName(repeat=True),
        fs=FormatSuggestion("Group created, posix gid: %i\n"+
                            "The user may have to restart bofh to access the "+
                            "'group add' command", ("group_id",)),
        perm_filter='can_create_personal_group')
    def group_personal(self, operator, uname):
        """This is a separate command for convenience and consistency.
        A personal group is always a PosixGroup, and has the same
        spreads as the user."""
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_create_personal_group(op, acc)
        # 1. Create group
        group = self.Group_class(self.db)
        try:
            group.find_by_name(uname)
            raise CerebrumError, "Group %s already exists" % uname
        except Errors.NotFoundError:
            group.populate(creator_id=op,
                           visibility=self.const.group_visibility_all,
                           name=uname,
                           description=('Personal file group for %s' % uname))
            group.write_db()
        # 2. Promote to PosixGroup
        pg = PosixGroup.PosixGroup(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        # 3. make user the owner of the group so he can administer it
        op_set = BofhdAuthOpSet(self.db)
        op_set.find_by_name('ureg_group')
        op_target = BofhdAuthOpTarget(self.db)
        op_target.populate(group.entity_id, 'group')
        op_target.write_db()
        role = BofhdAuthRole(self.db)
        role.grant_auth(acc.entity_id, op_set.op_set_id, op_target.op_target_id)
        # 4. make user a member of his personal group
        self._group_add(None, uname, uname, type="account")
        # 5. add spreads corresponding to its owning user
        self.__spread_sync_group(acc, group)
        return {'group_id': int(pg.posix_gid)}

    # group posix_create
    all_commands['group_promote_posix'] = Command(
        ("group", "promote_posix"), GroupName(),
        SimpleString(help_ref="string_description", optional=True),
        fs=FormatSuggestion("Group promoted to PosixGroup, posix gid: %i",
                            ("group_id",)), perm_filter='can_create_group')
    def group_promote_posix(self, operator, group, description=None):
        self.ba.can_create_group(operator.get_entity_id())
        is_posix = False
        try:
            self._get_group(group, grtype="PosixGroup")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixGroup" % group)

        group=self._get_group(group)
        pg = PosixGroup.PosixGroup(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(pg.posix_gid)}

    # group posix_demote
    all_commands['group_demote_posix'] = Command(
        ("group", "demote_posix"), GroupName(), perm_filter='can_delete_group')
    def group_demote_posix(self, operator, group):
        grp = self._get_group(group, grtype="PosixGroup")
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.delete()
        return "OK"
    
    # group search
    all_commands['group_search'] = Command(
        ("group", "search"), GroupSearchType(optional=True),
        fs=FormatSuggestion("%8i %s", ("id", "name"), hdr="%8s %s" % ("Id", "Name")),
        perm_filter='can_search_group')
    def group_search(self, operator, filter={}):
        # FIXME: Check filters to avoid "Search all" for all
        group = self.Group_class(self.db)
        ret = []
        # unpack filters (security.. hehe) 
        filter_name = filter.get('name', None)
        filter_desc = filter.get('desc',  None)
        filter_spread = filter.get('spread',  None)
        for r in group.search(filter_spread=filter_spread,  
                              filter_name=filter_name,
                              filter_desc=filter_desc):
            ret.append({'id': r.group_id,
                        'name': r.name,
                        'desc': r.description,
                      })
        return ret

    
    # group set_expire
    all_commands['group_set_expire'] = Command(
        ("group", "set_expire"), GroupName(), Date(), perm_filter='can_delete_group')
    def group_set_expire(self, operator, group, expire):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.expire_date = self._parse_date(expire)
        grp.write_db()
        return "OK"

    # group set_visibility
    all_commands['group_set_visibility'] = Command(
        ("group", "set_visibility"), GroupName(), GroupVisibility(),
        perm_filter='can_delete_group')
    def group_set_visibility(self, operator, group, visibility):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.visibility = self._map_visibility_id(visibility)
        grp.write_db()
        return "OK"

    # group user
    all_commands['group_user'] = Command(
        ('group', 'user'), AccountName(), fs=FormatSuggestion(
        "%-9s %-18s %s", ("memberop", "group", "spreads"),
        hdr="%-9s %-18s %s" % ("Operation", "Group", "Spreads")))
    def group_user(self, operator, accountname):
        account = self._get_account(accountname)
        group = self.Group_class(self.db)
        ret = []
        for row in group.list_groups_with_entity(account.entity_id):
            grp = self._get_group(row['group_id'], idtype="id")
            ret.append({'memberop': str(self.num2const[int(row['operation'])]),
                        'group': grp.group_name,
                        'spreads': ",".join(["%s" % self.num2const[int(a['spread'])]
                                             for a in grp.get_spread()])})
        return ret

    #
    # misc commands
    #

    # misc affiliations
    all_commands['misc_affiliations'] = Command(
        ("misc", "affiliations"),
        fs=FormatSuggestion("%-14s %-14s %s", ('aff', 'status', 'desc'),
                            hdr="%-14s %-14s %s" % ('Affiliation', 'Status',
                                                    'Description')))
    def misc_affiliations(self, operator):
        tmp = {}
        for co in self.const.fetch_constants(self.const.PersonAffStatus):
            aff = str(co.affiliation)
            if aff not in tmp:
                tmp[aff] = [{'aff': aff,
                             'status': '',
                             'desc': co.affiliation._get_description()}]
            tmp[aff].append({'aff': '',
                             'status': "%s" % co._get_status(),
                             'desc': co._get_description()})
        # fetch_constants returns a list sorted according to the name
        # of the constant.  Since the name of the constant and the
        # affiliation status usually are kept related, the list for
        # each affiliation will tend to be sorted as well.  Not so for
        # the affiliations themselves.
        keys = tmp.keys()
        keys.sort()
        ret = []
        for k in keys:
            for r in tmp[k]:
                ret.append(r)
        return ret

    # misc checkpassw
    all_commands['misc_change_request'] = Command(
        ("misc", "change_request"), Id(), Date())
    def misc_change_request(self, operator, request_id, date):
        date = self._parse_date(date)
        br = BofhdRequests(self.db, self.const)
        old_req = br.get_requests(request_id=request_id)[0]
        if old_req['requestee_id'] != operator.get_entity_id():
            raise PermissionDenied("You are not the requestee")
        br.delete_request(request_id=request_id)
        br.add_request(operator.get_entity_id(), date,
                       old_req['operation'], old_req['entity_id'],
                       old_req['destination_id'],
                       old_req['state_data'])
        return "OK"

    # misc checkpassw
    all_commands['misc_checkpassw'] = Command(
        ("misc", "checkpassw"), AccountPassword())
    def misc_checkpassw(self, operator, password):
        pc = PasswordChecker.PasswordChecker(self.db)
        try:
            pc.goodenough(None, password, uname="foobar")
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError, "Bad password: %s" % m
        ac = self.Account_class(self.db)
        crypt = ac.enc_auth_type_crypt3_des(password)
        md5 = ac.enc_auth_type_md5_crypt(password)
        return "OK.  crypt3-DES: %s   MD5-crypt: %s" % (crypt, md5)

    # misc clear_passwords
    all_commands['misc_clear_passwords'] = Command(
        ("misc", "clear_passwords"), AccountName(optional=True))
    def misc_clear_passwords(self, operator, account_name=None):
        operator.clear_state(state_types=('new_account_passwd', 'user_passwd'))
        return "OK"


    all_commands['misc_dadd'] = Command(
        ("misc", "dadd"), SimpleString(help_ref='string_host'), DiskId(),
        perm_filter='is_superuser')
    def misc_dadd(self, operator, hostname, diskname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        host = self._get_host(hostname)
        disk = Utils.Factory.get('Disk')(self.db)
        disk.populate(host.entity_id, diskname, 'HiA user disk')
        disk.write_db()
        if len(diskname.split("/")) != 4:
            return "OK.  Warning: disk did not follow expected pattern."
        return "OK"

    all_commands['misc_dls'] = Command(
        ("misc", "dls"), SimpleString(help_ref='string_host'),
        fs=FormatSuggestion("%-8i %-8i %s", ("disk_id", "host_id", "path",),
                            hdr="DiskId   HostId   Path"))
    def misc_dls(self, operator, hostname):
        host = self._get_host(hostname)
        disks = {}
        disk = Utils.Factory.get('Disk')(self.db)
        for row in disk.list(host.host_id):
            disks[row['disk_id']] = {'disk_id': row['disk_id'],
                                     'host_id': row['host_id'],
                                     'path': row['path']}
        disklist = disks.keys()
        disklist.sort(lambda x, y: cmp(disks[x]['path'], disks[y]['path']))
        ret = []
        for d in disklist:
            ret.append(disks[d])
        return ret

    all_commands['misc_drem'] = Command(
        ("misc", "drem"), SimpleString(help_ref='string_host'), DiskId(),
        perm_filter='is_superuser')
    def misc_drem(self, operator, hostname, diskname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        host = self._get_host(hostname)
        disk = Utils.Factory.get('Disk')(self.db)
        disk.find_by_path(diskname, host_id=host.entity_id)
        raise NotImplementedError, "API does not support disk removal"

    all_commands['misc_hadd'] = Command(
        ("misc", "hadd"), SimpleString(help_ref='string_host'),
        perm_filter='is_superuser')
    def misc_hadd(self, operator, hostname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        host = Utils.Factory.get('Host')(self.db)
        host.populate(hostname, 'HiA host')
        host.write_db()
        return "OK"

    all_commands['misc_hrem'] = Command(
        ("misc", "hrem"), SimpleString(help_ref='string_host'),
        perm_filter='is_superuser')
    def misc_hrem(self, operator, hostname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        host = self._get_host(hostname)
        raise NotImplementedError, "API does not support host removal"

    # misc list_passwords
    def misc_list_passwords_prompt_func(self, session, *args):
        """  - G�r inn i "vis-info-om-oppdaterte-brukere-modus":
  1 Skriv ut passordark
  1.1 Lister ut templates, ber bofh'er om � velge en
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
        #if not tpl_lang.endswith("letter"):
        #    if not all_args:
        #        return {'prompt': 'Oppgi skrivernavn'}
        #    skriver = all_args.pop(0)
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
	# kommenterer ut dette fram til det er kommet fram en bedre l�sning
	# p� problemet med overf�ring av passordark til HiA-maskinen
        #if not tpl_lang.endswith("letter"):
        #    skriver = args.pop(0)
        #else:
        #    skriver = cereconf.PRINT_PRINTER
	try:
            acc = self._get_account(operator.get_entity_id(), idtype='id')
	    opr=acc.account_name
        except Errors.NotFoundError:
	    raise CerebrumError, ("Could not find the operator id!")
	time_temp = strftime("%Y-%m-%d-%H%M%S", localtime())
	selection = args.pop(0)
        cache = self._get_cached_passwords(operator)
        th = TemplateHandler(tpl_lang, tpl_name, tpl_type)
        tmp_dir = Utils.make_temp_dir(dir=cereconf.JOB_RUNNER_LOG_DIR,
                                      prefix="bofh_spool")
	out_name = "%s/%s-%s.%s" % (tmp_dir, opr, time_temp, tpl_type)
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
                try:
                    address = person.get_entity_address(source=self.const.system_fs,
                                                        type=self.const.address_post)
                except Errors.NotFoundError:
                    try:
                        address = person.get_entity_address(source=self.const.system_sap,
                                                            type=self.const.address_post)
                    except Errors.NotFoundError:
                        ret.append("Error: Couldn't get authoritative address for %s" % account.account_name)
                        continue
                if not address:
                    ret.append("Error: Couldn't get authoritative address for %s" % account.account_name)
                    continue
                address = address[0]
                alines = address['address_text'].split("\n")+[""]
                mapping['address_line1'] = fullname
                mapping['address_line2'] = alines[0]
                mapping['address_line3'] = alines[1]
                mapping['zip'] = address['postal_number']
                mapping['city'] = address['city']
                mapping['country'] = address['country']

                mapping['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
                mapping['emailadr'] =  "TODO"  # We probably don't need to support this...
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

    # misc mmove
    all_commands['misc_list_requests'] = Command(
        ("misc", "list_requests"),
        fs=FormatSuggestion("%-6i %-10s %-16s %-15s %-10s %-20s %s",
                            ("id", "requestee", format_time("when"),
                             "op", "entity", "destination", "args"),
                            hdr="%-6s %-10s %-16s %-15s %-10s %-20s %s" % \
                            ("Id", "Requestee", "When", "Op", "Entity",
                             "Destination", "Arguments")))
    def misc_list_requests(self, operator):
        br = BofhdRequests(self.db, self.const)
        ret = []
        for r in br.get_requests(operator_id=operator.get_entity_id(),
                                 given=True):
            op = self.num2const[int(r['operation'])]
            dest = None
            if op in (self.const.bofh_move_user, self.const.bofh_move_request):
                disk = Utils.Factory.get('Disk')(self.db)
                disk.find(r['destination_id'])
                dest = disk.path
            elif op in (self.const.bofh_move_give,):
                dest = self._get_entity_name(self.const.entity_group,
                                             r['destination_id'])
            print "R: %s" % r['run_at']
            ret.append({'when': r['run_at'],
                        'requestee': self._get_entity_name(self.const.entity_account, r['requestee_id']),
                        'op': str(op),
                        'entity': self._get_entity_name(self.const.entity_account, r['entity_id']),
                        'destination': dest,
                        'args': r['state_data'],
                        'id': r['request_id']
                        })
        return ret

    all_commands['misc_reload'] = Command(
        ("misc", "reload"), 
        perm_filter='is_superuser')
    def misc_reload(self, operator):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        self.server.read_config()
        return "OK"

    # misc stedkode <pattern>
    all_commands['misc_stedkode'] = Command(
        ("misc", "stedkode"), SimpleString(),
        fs=FormatSuggestion([
        (" %06s    %s",
         ('stedkode', 'short_name')),
        ("   affiliation %-7s @%s",
         ('affiliation', 'domain'))],
         hdr="Stedkode   Organizational unit"))
    def misc_stedkode(self, operator, pattern):
        output = []
        ou = self.OU_class(self.db)
        if re.match(r'[0-9]{1,6}$', pattern):
            fak = [ pattern[0:2] ]
            inst = [ pattern[2:4] ]
            avd = [ pattern[4:6] ]
            if len(fak[0]) == 1:
                fak = [ int(fak[0]) * 10 + x for x in range(10) ]
            if len(inst[0]) == 1:
                inst = [ int(inst[0]) * 10 + x for x in range(10) ]
            if len(avd[0]) == 1:
                avd = [ int(avd[0]) * 10 + x for x in range(10) ]
            # the following loop may look scary, but we will never
            # call get_stedkoder() more than 10 times.
            for f in fak:
                for i in inst:
                    if i == '':
                        i = None
                    for a in avd:
                        if a == '':
                            a = None
                        for r in ou.get_stedkoder(fakultet=f, institutt=i,
                                                  avdeling=a):
                            ou.clear()
                            ou.find(r['ou_id'])
                            output.append({'stedkode':
                                           '%02d%02d%02d' % (ou.fakultet,
                                                             ou.institutt,
                                                             ou.avdeling),
                                           'short_name':
                                           ou.short_name})
        else:
            if pattern.count('%') == 0:
                pattern = '%' + pattern + '%'
            for r in ou.get_stedkoder_by_name(pattern):
                ou.clear()
                ou.find(r['ou_id'])
                output.append({'stedkode':
                               '%02d%02d%02d' % (ou.fakultet,
                                                 ou.institutt,
                                                 ou.avdeling),
                               'short_name': ou.short_name})
        if len(output) == 1:
            eed = Email.EntityEmailDomain(self.db)
            try:
                eed.find(ou.ou_id)
            except Errors.NotFoundError:
                pass
            ed = Email.EmailDomain(self.db)
            for r in eed.list_affiliations():
                affname = "<any>"
                if r['affiliation']:
                    affname = str(self.num2const[int(r['affiliation'])])
                ed.clear()
                ed.find(r['domain_id'])
                output.append({'affiliation': affname,
                               'domain': ed.email_domain_name})
        return output

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


    #
    # perm commands
    #

    # perm opset_list
    all_commands['perm_opset_list'] = Command(
        ("perm", "opset_list"), 
        fs=FormatSuggestion("%-6i %s", ("id", "name"), hdr="Id     Name"),
        perm_filter='is_superuser')
    def perm_opset_list(self, operator):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aos = BofhdAuthOpSet(self.db)
        ret = []
        for r in aos.list():
            ret.append({'id': r['op_set_id'],
                        'name': r['name']})
        return ret

    # perm opset_show
    all_commands['perm_opset_show'] = Command(
        ("perm", "opset_show"), SimpleString(help_ref="string_op_set"),
        fs=FormatSuggestion("%-6i %-16s %s", ("op_id", "op", "attrs"),
                            hdr="%-6s %-16s %s" % ("Id", "op", "Attributes")),
        perm_filter='is_superuser')
    def perm_opset_show(self, operator, name):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(name)
        ret = []
        for r in aos.list_operations():
            c = AuthConstants(int(r['op_code']))
            ret.append({'op': str(c),
                        'op_id': r['op_id'],
                        'attrs': ", ".join(
                ["%s" % r2['attr'] for r2 in aos.list_operation_attrs(r['op_id'])])})
        return ret

    # perm target_list
    all_commands['perm_target_list'] = Command(
        ("perm", "target_list"), SimpleString(help_ref="string_perm_target"),
        Id(optional=True),
        fs=FormatSuggestion("%-8i %-15i %-10s %-18s %s",
                            ("tgt_id", "entity_id", "target_type", "name", "attrs"),
                            hdr="%-8s %-15s %-10s %-18s %s" % (
        "TargetId", "TargetEntityId", "TargetType", "TargetName", "Attrs")),
        perm_filter='is_superuser')
    def perm_target_list(self, operator, target_type, entity_id=None):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        ret = []
        if target_type.isdigit():
            rows = aot.list(target_id=target_type)
        else:
            rows = aot.list(target_type=target_type, entity_id=entity_id)
        for r in rows:
            if r['target_type'] == 'group':
                name = self._get_entity_name(self.const.entity_group, r['entity_id'])
            elif r['target_type'] == 'disk':
                name = self._get_entity_name(self.const.entity_disk, r['entity_id'])
            elif r['target_type'] == 'host':
                name = self._get_entity_name(self.const.entity_host, r['entity_id'])
            else:
                name = "unknown"
            ret.append({'tgt_id': r['op_target_id'],
                        'entity_id': r['entity_id'],
                        'name': name,
                        'target_type': r['target_type'],
                        'attrs': r['attr'] or '<none>'})
        return ret

    # perm add_target
    all_commands['perm_add_target'] = Command(
        ("perm", "add_target"),
        SimpleString(help_ref="string_perm_target_type"), Id(),
        SimpleString(help_ref="string_attribute", optional=True),
        perm_filter='is_superuser')
    def perm_add_target(self, operator, target_type, entity_id, attr=None):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        if entity_id.isdigit():
            entity_id = int(entity_id)
        else:
            raise CerebrumError("Integer entity_id expected; got %r" %
                                (entity_id,))
        aot = BofhdAuthOpTarget(self.db)
        aot.populate(entity_id, target_type, attr)
        aot.write_db()
        return "OK, target id=%d" % aot.op_target_id

    # perm del_target
    all_commands['perm_del_target'] = Command(
        ("perm", "del_target"), Id(help_ref="id:op_target"),
        perm_filter='is_superuser')
    def perm_del_target(self, operator, op_target_id, attr):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        aot.find(op_target_id)
        aot.delete()
        return "OK"

    # perm list
    all_commands['perm_list'] = Command(
        ("perm", "list"), Id(help_ref='id:entity_ext'),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_list(self, operator, entity_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        if entity_id.startswith("group:"):
            entities = [ self._get_group(entity_id.split(":")[-1]).entity_id ]
        elif entity_id.startswith("account:"):
            account = self._get_account(entity_id.split(":")[-1])
            group = self.Group_class(self.db)
            entities = [account.entity_id]
            for row in group.list_groups_with_entity(account.entity_id):
                if row['operation'] == int(self.const.group_memberop_union):
                    entities.append(row['group_id'])
        else:
            if not entity_id.isdigit():
                raise CerebrumError("Expected entity-id")
            entities = [entity_id]
        bar = BofhdAuthRole(self.db)
        ret = []
        for r in bar.list(entities):
            ret.append({'entity_id': self._get_entity_name(None, r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    # perm grant
    all_commands['perm_grant'] = Command(
        ("perm", "grant"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"), perm_filter='is_superuser')
    def perm_grant(self, operator, entity_id, op_set_name, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(op_set_name)

        bar.grant_auth(entity_id, aos.op_set_id, op_target_id)
        return "OK"

    # perm revoke
    all_commands['perm_revoke'] = Command(
        ("perm", "revoke"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"), perm_filter='is_superuser')
    def perm_revoke(self, operator, entity_id, op_set_name, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(op_set_name)
        bar.revoke_auth(entity_id, aos.op_set_id, op_target_id)
        return "OK"

    # perm who_owns
    all_commands['perm_who_owns'] = Command(
        ("perm", "who_owns"), Id(help_ref="id:entity_ext"),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_who_owns(self, operator, id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        if id.startswith("group:"):
            group = self._get_group(id.split(":")[-1])
            aot = BofhdAuthOpTarget(self.db)
            target_ids = []
            for r in aot.list(target_type='group', entity_id=group.entity_id):
                target_ids.append(r['op_target_id'])
        else:
            if not id.isdigit():
                raise CerebrumError("Expected target-id")
            target_ids = [int(id)]
        if not target_ids:
            raise CerebrumError("No target_ids for %s" % id)
        ret = []
        for r in bar.list_owners(target_ids):
            ret.append({'entity_id': self._get_entity_name(None, r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    #
    # person commands
    #

    # person accounts
    all_commands['person_accounts'] = Command(
        ("person", "accounts"), PersonId(),
        fs=FormatSuggestion("%6i %-10s %s", ("account_id", "name", format_day("expire")),
                            hdr="%6s %-10s %s" % ("Id", "Name", "Expire")))
    def person_accounts(self, operator, id):
        if id.find(":") == -1 and not id.isdigit():
            ac = self._get_account(id)
            id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(id))
        account = self.Account_class(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(person.entity_id):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name,
                        'expire': account.expire_date})
        return ret

    def _person_affiliation_add_helper(self, operator, person, ou, aff, aff_status):
        """Helper-function for adding an affiliation to a person with
        permission checking.  person is expected to be a person
        object, while ou, aff and aff_status should be the textual
        representation from the client"""
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(stedkode=ou)

        # Assert that the person already have the affiliation
        has_aff = False
        for a in person.get_affiliations():
            if a['ou_id'] == ou.entity_id and a['affiliation'] == aff:
                if a['status'] <> aff_status:
                    raise CerebrumError, \
                          "Person has conflicting aff_status for this ou/affiliation combination"
                has_aff = True
                break
        if not has_aff:
            self.ba.can_add_affiliation(operator.get_entity_id(), person, ou, aff, aff_status)
            if (aff == self.const.affiliation_ansatt or
                aff == self.const.affiliation_student):
                raise PermissionDenied(
                    "Student/Ansatt affiliation can only be set by FS/LT")
            person.add_affiliation(ou.entity_id, aff,
                                   self.const.system_manual, aff_status)
            person.write_db()
        return ou, aff, aff_status

    # person affilation_add
    all_commands['person_affiliation_add'] = Command(
        ("person", "affiliation_add"), PersonId(), OU(), Affiliation(), AffiliationStatus(),
        perm_filter='can_add_affiliation')
    def person_affiliation_add(self, operator, person_id, ou, aff, aff_status):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status)
        return "OK, added %s@%s to %s" % (aff, self._format_ou_name(ou), person.entity_id)

    # person affilation_remove
    all_commands['person_affiliation_remove'] = Command(
        ("person", "affiliation_remove"), PersonId(), OU(), Affiliation(),
        perm_filter='can_remove_affiliation')
    def person_affiliation_remove(self, operator, person_id, ou, aff):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        self.ba.can_remove_affiliation(operator.get_entity_id(), person, ou, aff)
        for row in person.list_affiliations(person_id=person.entity_id,
                                            affiliation=aff):
            if row['ou_id'] != int(ou.entity_id):
                continue
            if int(row['source_system']) not \
                   in [int(self.const.system_fs), int(self.const.system_sap)]:
                person.delete_affiliation(ou.entity_id, aff,
                                          row['source_system'])
        return "OK, removed %s@%s from %s" % (aff, self._format_ou_name(ou), person.entity_id)

    # person create
    all_commands['person_create'] = Command(
        ("person", "create"), PersonId(),
        Date(help_ref='date_birth'), PersonName(help_ref='person_name_first'), 
	PersonName(help_ref='person_name_last'), OU(),
        Affiliation(), AffiliationStatus(),
        fs=FormatSuggestion("Created: %i",
        ("person_id",)), perm_filter='can_create_person')
    def person_create(self, operator, person_id, bdate, person_name_first,
		      person_name_last, ou, affiliation, aff_status):
        stedkode = ou
        try:
            ou = self._get_ou(stedkode=ou)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % ou
        try:
            aff = self._get_affiliationid(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown affiliation type (%s)" % affiliation
        self.ba.can_create_person(operator.get_entity_id(), ou, aff)
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
                        description='Manually created')
        person.affect_names(self.const.system_manual, self.const.name_first, self.const.name_last)
        person.populate_name(self.const.name_first,
                             person_name_first.encode('iso8859-1'))
	person.populate_name(self.const.name_last,
                             person_name_last.encode('iso8859-1'))
        try:
            person.write_db()
            self._person_affiliation_add_helper(
                operator, person, stedkode, str(aff), aff_status)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    # person find
    all_commands['person_find'] = Command(
        ("person", "find"), PersonSearchType(), SimpleString(),
        fs=FormatSuggestion("%6i   %10s   %-12s  %s",
                            ('id', format_day('birth'), 'export_id', 'name'),
                            hdr="%6s   %10s   %-12s  %s" % \
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
            elif search_type == 'stedkode':
                ou = self._get_ou(stedkode=value)
                # We potentially get multiple rows for a person when
                # s/he has more than one kind of affiliation.  Store
                # result in a dict to get rid of dups.
                result = {}
                for r in person.list_affiliations(ou_id=ou.entity_id):
                    result[r['person_id']] = r
                matches = result.values()
            else:
                raise CerebrumError, "Unknown search type (%s)" % search_type
        ret = []
        for row in matches:
            person = self._get_person('entity_id', row['person_id'])
            pname = person.get_name(self.const.system_cached,
                                    getattr(self.const,
                                            cereconf.DEFAULT_GECOS_NAME))
            # Ideally we'd fetch the authoritative last name, but
            # it's a lot of work.  We cheat and use the last word
            # of the name, which should work for 99.9% of the users.
            ret.append({'id': row['person_id'],
                        'birth': person.birth_date,
                        'export_id': person.export_id,
                        'name': pname,
                        'lastname': pname.split(" ")[-1] })
        ret.sort(lambda a,b: (cmp(a['lastname'], b['lastname']) or
                              cmp(a['name'], b['name'])))
        return ret
    
    # person info
    all_commands['person_info'] = Command(
        ("person", "info"), PersonId(),
        fs=FormatSuggestion([
        ("Name:          %s\n" +
         "Export ID:     %s\n" +
         "Birth:         %s\n" +
         "Affiliations:  %s [from %s]",
         ("name", "export_id", format_day("birth"),
          "affiliation_1", "source_system_1")),
        ("               %s [from %s]",
         ("affiliation", "source_system")),
        ("Fnr:           %s [from %s]",
         ("fnr", "fnr_src"))
        ]))
    def person_info(self, operator, person_id):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        data = [{'name': person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME)),
                 'export_id': person.export_id,
                 'birth': person.birth_date}]
        affiliations = []
        sources = []
        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (
                self.const.PersonAffStatus(row['status']),
                self._format_ou_name(ou)))
            sources.append(str(self.const.AuthoritativeSystem(row['source_system'])))
        if affiliations:
            data[0]['affiliation_1'] = affiliations[0]
            data[0]['source_system_1'] = sources[0]
        else:
            data[0]['affiliation_1'] = "<none>"
            data[0]['source_system_1'] = "<nowhere>"
        for i in range(1, len(affiliations)):
            data.append({'affiliation': affiliations[i],
                         'source_system': sources[i]})
        if self.ba.is_superuser(operator.get_entity_id()):
            for row in person.get_external_id(id_type=self.const.externalid_fodselsnr):
                data.append({'fnr': row['external_id'],
                             'fnr_src': str(
                    self.const.AuthoritativeSystem(row['source_system']))})
        return data

    # person set_id
    all_commands['person_set_id'] = Command(
        ("person", "set_id"), PersonId(help_ref="person_id:current"),
        PersonId(help_ref="person_id:new"))
    def person_set_id(self, operator, current_id, new_id):
        person = self._get_person(*self._map_person_id(current_id))
        idtype, id = self._map_person_id(new_id)
        self.ba.can_set_person_id(operator.get_entity_id(), person, idtype)
        person.affect_external_id(self.const.system_manual, idtype)
        person.populate_external_id(self.const.system_manual,
                                    idtype, id)
        person.write_db()
        return "OK"

    #person set name
    all_commands['person_set_name'] = Command(
	("person", "set_name"),PersonId(help_ref="person_id_other"),
	PersonName(help_ref="person_name_full"),
	fs=FormatSuggestion("Name altered for: %i",
        ("person_id",)),
	perm_filter='is_superuser')
    def person_set_name(self, operator, person_id, person_fullname):
        person = self._get_person(*self._map_person_id(person_id))
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")

	for a in person.get_affiliations():
	    if (int(a['source_system']) in \
		[int(self.const.system_fs), int(self.const.system_sap)]):
		raise CerebrumError, "You can't alter name of a person registered in an authorative source system!"
	    else:
		pass
	    person.affect_names(self.const.system_manual, self.const.name_full)
	    person.populate_name(self.const.name_full,
				 person_fullname.encode('iso8859-1'))
	    
	    try:
		person.write_db()
	    except self.db.DatabaseError, m:
		raise CerebrumError, "Database error: %s" % m
	    return {'person_id': person.entity_id}

    # person student_info
    all_commands['person_student_info'] = Command(
        ("person", "student_info"), PersonId(),
        fs=FormatSuggestion([
        ("Studieprogrammer: %s, %s, %s, tildelt=%s->%s privatist: %s",
         ("studprogkode", "studierettstatkode", "opphortstatus", format_day("dato_tildelt"),
          format_day("dato_gyldig_til"), "privatist")),
        ("Eksamensmeldinger: %s (%s), %s",
         ("ekskode", "programmer", format_day("dato"))),
        ("Utd. plan: %s, %s, %d, %s",
         ("studieprogramkode", "terminkode_bekreft", "arstall_bekreft",
          format_day("dato_bekreftet"))),
        ("Semesterreg: %s, %s, betalt: %s, endret: %s",
         ("regformkode", "betformkode", format_day("dato_betaling"),
          format_day("dato_regform_endret"))),
        ("Klasse: %s, (%s)", ("klassekode", "kullkode"))
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
        db = Database.connect(user="cerebrum", service="FSHIA.uio.no",
                              DB_driver='Oracle')
        fs = HiAFS(db)
        for row in fs.GetStudentStudierett(fodselsdato, pnum)[1]:
            har_opptak["%s" % row['studieprogramkode']] = \
			    row['status_privatist']
            ret.append({'studprogkode': row['studieprogramkode'],
                        'studierettstatkode': row['studierettstatkode'],
                        'opphortstatus': row['opphortstudierettstatkode'],
                        'dato_tildelt': DateTime.DateTimeFromTicks(row['dato_tildelt']),
                        'dato_gyldig_til': DateTime.DateTimeFromTicks(row['dato_gyldig_til']),
                        'privatist': row['status_privatist']})

        for row in fs.GetStudentEksamen(fodselsdato, pnum)[1]:
            programmer = []
            for row2 in fs.GetEmneIStudProg(row['emnekode'])[1]:
                if har_opptak.has_key("%s" % row2['studieprogramkode']):
                    programmer.append(row2['studieprogramkode'])
            ret.append({'ekskode': row['emnekode'],
                        'programmer': ",".join(programmer),
                        'dato': DateTime.DateTimeFromTicks(row['dato_opprettet'])})
                      
        for row in fs.GetStudentUtdPlan(fodselsdato, pnum)[1]:
            ret.append({'studieprogramkode': row['studieprogramkode'],
                        'terminkode_bekreft': row['terminkode_bekreft'],
                        'arstall_bekreft': row['arstall_bekreft'],
                        'dato_bekreftet': DateTime.DateTimeFromTicks(row['dato_bekreftet'])})

        for row in fs.GetStudentSemReg(fodselsdato, pnum)[1]:
            ret.append({'regformkode': row['regformkode'],
                        'betformkode': row['betformkode'],
                        'dato_betaling': DateTime.DateTimeFromTicks(row['dato_betaling']),
                        'dato_regform_endret': DateTime.DateTimeFromTicks(row['dato_regform_endret'])})

	for row in fs.GetStudentKullOgKlasse(fodselsdato, pnum)[1]:
	    ret.append({'kullkode': row['kullkode'],
			'klassekode': row['klassekode']})

        db.close()
        return ret

    # person user_priority
    all_commands['person_set_user_priority'] = Command(
        ("person", "set_user_priority"), AccountName(),
        SimpleString(help_ref='string_old_priority'),
        SimpleString(help_ref='string_new_priority'))
    def person_set_user_priority(self, operator, account_name,
                                 old_priority, new_priority):
        account = self._get_account(account_name)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_set_person_user_priority(operator.get_entity_id(), account)
        old_priority = int(old_priority)
        new_priority = int(new_priority)
        ou = None
        affiliation = None
        for row in account.get_account_types():
            if row['priority'] == old_priority:
                ou = row['ou_id']
                affiliation = row['affiliation']
        if ou is None:
            raise CerebrumError("Must specify an existing priority")
        account.set_account_type(ou, affiliation, new_priority)
        account.write_db()
        return "OK"

    all_commands['person_list_user_priorities'] = Command(
        ("person", "list_user_priorities"), PersonId(),
        fs=FormatSuggestion(
        "%8s %8i %s", ('uname', 'priority', 'affiliation'),
        hdr="%8s %8s %s" % ("Uname", "Priority", "Affiliation")))
    def person_list_user_priorities(self, operator, person_id):
        ac = Utils.Factory.get('Account')(self.db)
        person = self._get_person(*self._map_person_id(person_id))
        ret = []
        for row in ac.get_account_types(all_persons_types=True,
                                        owner_id=person.entity_id):
            ac2 = self._get_account(row['account_id'], idtype='id')
            ou = self._get_ou(ou_id=row['ou_id'])
            ret.append({'uname': ac2.account_name,
                        'priority': row['priority'],
                        'affiliation': '%s@%s' % (
                self.num2const[int(row['affiliation'])], self._format_ou_name(ou))})
            ## This seems to trigger a wierd python bug:
            ## self.num2const[int(row['affiliation'], self._format_ou_name(ou))])})
        return ret
    #
    # printer commands
    #

    all_commands['printer_qoff'] = Command(
        ("print", "qoff"), AccountName(), perm_filter='can_alter_printerquota')
    def printer_qoff(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_alter_printerquota(operator.get_entity_id(), account)
        pq = self._get_printerquota(account.entity_id)
        if pq is None:
            return "User has no quota"
        pq.has_printerquota = 'F'
        pq.write_db()
        return "Quota disabled"

    all_commands['printer_qpq'] = Command(
        ("print", "qpq"), AccountName(),
        fs=FormatSuggestion("Has quota Quota Pages printed This "+
                            "term Weekly q. Max acc. Term q. \n"+
                            "%-9s %5i %13i %9i %9i %8i %7i",
                            ('has_printerquota', 'printer_quota',
                            'pages_printed', 'pages_this_semester',
                            'weekly_quota', 'max_quota', 'termin_quota')))
    def printer_qpq(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_query_printerquota(operator.get_entity_id(), account)
        pq = self._get_printerquota(account.entity_id)
        if pq is None:
            return "User has no quota"
        return {'printer_quota': pq.printer_quota,
                'pages_printed': pq.pages_printed,
                'pages_this_semester': pq.pages_this_semester,
                'termin_quota': pq.termin_quota,
                'has_printerquota': pq.has_printerquota,
                'weekly_quota': pq.weekly_quota,
                'max_quota': pq.max_quota}

    all_commands['printer_upq'] = Command(
        ("print", "upq"), AccountName(), SimpleString(), perm_filter='can_alter_printerquota')
    def printer_upq(self, operator, accountname, pages):
        account = self._get_account(accountname)
        self.ba.can_alter_printerquota(operator.get_entity_id(), account)
        pq = self._get_printerquota(account.entity_id)
        if pq is None:
            return "User has no quota"
        try:
            pages = int(pages)
        except ValueError:
            raise CerebrumError("Enter an integer")
        if pages > pq.max_quota:
            raise CerebrumError("Quota too high, max is %i" % (
                pq.max_quota or 0))
        pq.printer_quota = pages
        pq.write_db()
        return "OK"

    #
    # quarantine commands
    #

    # quarantine disable
    all_commands['quarantine_disable'] = Command(
        ("quarantine", "disable"), EntityType(default="account"), Id(),
        QuarantineType(), Date(), perm_filter='can_disable_quarantine')
    def quarantine_disable(self, operator, entity_type, id, qtype, date):
        entity = self._get_entity(entity_type, id)
        date = self._parse_date(date)
        qtype = int(self._get_constant(qtype, "No such quarantine"))
        self.ba.can_disable_quarantine(operator.get_entity_id(), entity, qtype)
        entity.disable_entity_quarantine(qtype, date)
        return "OK"

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
        try:
            entity.add_entity_quarantine(qtype, operator.get_entity_id(), why, date_start, date_end)
        except AttributeError:    
            raise CerebrumError("Quarantines cannot be set on %s" % entity_type)
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
    #
    # spread commands
    #

    # spread add
    all_commands['spread_add'] = Command(
        ("spread", "add"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
    def spread_add(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = int(self._get_constant(spread, "No such spread"))
	# TODO probably not the most optimal solution, 
	if spread == int(self.const.spread_hia_novell_user):
	    return "Please use the command 'user home_create' to assign an extra homedir to the user!"
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        try:
            entity.add_spread(spread)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        if entity_type == 'account':
            self.__spread_sync_group(entity)
        return "OK"

    # spread list
    all_commands['spread_list'] = Command(
        ("spread", "list"),
        fs=FormatSuggestion("%-14s %s", ('name', 'desc'),
                            hdr="%-14s %s" % ('Name', 'Description')))
    def spread_list(self, operator):
        ret = []
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _SpreadCode):
                ret.append({'name': "%s" % tmp, 'desc': unicode(tmp._get_description(), 'iso8859-1')})
        return ret

    # spread remove
    all_commands['spread_remove'] = Command(
        ("spread", "remove"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
    def spread_remove(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = int(self._get_constant(spread, "No such spread"))
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        if spread == int(self.const.spread_hia_email):
            raise CerebrumError, "Cannot remove IMAP spread without deleting user"
        entity.delete_spread(spread)
        if entity_type == 'account':
            self.__spread_sync_group(entity)
        return "OK"

    def __spread_sync_group(self, account, group=None):
        """Make sure the group has the NIS spreads corresponding to
        the NIS spreads of the account.  The account and group
        arguments may be passed as Entity objects.  If group is None,
        the group with the same name as account is modified, if it
        exists."""
        if group is None:
            name = account.get_name(self.const.account_namespace)
            try:
                group = self._get_group(name)
            except CerebrumError:
                return
        mapping = { int(self.const.spread_uio_nis_user):
                    int(self.const.spread_uio_nis_fg),
                    int(self.const.spread_uio_ad_account):
                    int(self.const.spread_uio_ad_group),
                    int(self.const.spread_ifi_nis_user):
                    int(self.const.spread_ifi_nis_fg) }
        wanted = []
        for r in account.get_spread():
            spread = int(r['spread'])
            if spread in mapping:
                wanted.append(mapping[spread])
        for r in group.get_spread():
            spread = int(r['spread'])
            if not spread in mapping.values():
                pass
            elif spread in wanted:
                wanted.remove(spread)
            else:
                group.delete_spread(spread)
        for spread in wanted:
            group.add_spread(spread)

    #
    # user commands
    #

    # user affiliation_add
    all_commands['user_affiliation_add'] = Command(
        ("user", "affiliation_add"), AccountName(), OU(), Affiliation(), AffiliationStatus(),
        perm_filter='can_add_affiliation')
    def user_affiliation_add(self, operator, accountname, ou, aff, aff_status):
        account = self._get_account(accountname)
        person = self._get_person('entity_id', account.owner_id)
        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status)
        self.ba.can_add_account_type(operator.get_entity_id(), account, ou, aff, aff_status)
        account.set_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, added %s@%s to %s" % (aff, self._format_ou_name(ou), account.owner_id)
    
    # user affiliation_remove
    all_commands['user_affiliation_remove'] = Command(
        ("user", "affiliation_remove"), AccountName(), OU(), Affiliation(),
        perm_filter='can_remove_affiliation')
    def user_affiliation_remove(self, operator, accountname, ou, aff): 
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_remove_account_type(operator.get_entity_id(), account, ou, aff)
        account.del_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK"

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
                    name = "%s/%s@%s" % (
                        self.num2const[int(aff['affiliation'])],
                        self.num2const[int(aff['status'])],
                        self._format_ou_name(ou))
                    map.append((("%s", name), int(aff['affiliation'])))
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

    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('PosixUser', session, *args)

    def _user_create_set_account_type(self, account, owner_id, affiliation):
        person = self._get_person('entity_id', owner_id)
        try:
            affiliation=self.const.PersonAffiliation(affiliation)
            # make sure exist
            int(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError, "Invalid affiliation %s" % affiliation
        for aff in person.get_affiliations():
            if aff['affiliation'] == affiliation:
                ou = self._get_ou(aff['ou_id'])
                break
        else:
            raise CerebrumError, \
                "Owner did not have any affiliation %s" % affiliation        
        account.set_account_type(ou.entity_id, affiliation)
        
    # user create
    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')
    def user_create(self, operator, *args):
        if args[0].startswith('group:'):
            group_id, np_type, filegroup, shell, home, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = int(self._get_constant(np_type, "Unknown account type"))
        else:
            if len(args) == 8:
                idtype, person_id, affiliation, filegroup, shell, home, nhome, uname = args
            else:
                idtype, person_id, yes_no, affiliation, filegroup, shell, home, nhome, uname = args
            owner_type = self.const.entity_person
            owner_id = self._get_person("entity_id", person_id).entity_id
            np_type = None
            
        group=self._get_group(filegroup, grtype="PosixGroup")
        posix_user = PosixUser.PosixUser(self.db)
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        disk_id, home = self._get_disk_or_home(home)
        if home is not None:
            if home[0] == ':':
                home = home[1:]
            else:
                raise CerebrumError, "Invalid disk"
        ndisk_id, nhome = self._get_disk_or_home(nhome)
        if nhome is not None:
            if nhome[0] == ':':
                nhome = nhome[1:]
            else:
                raise CerebrumError, "Invalid disk"
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
                posix_user.add_spread(self._get_constant(spread,
                                                         "No such spread"))
            posix_user.set_home(self.const.spread_nis_user,
                                disk_id=disk_id, home=home,
                                status=self.const.home_status_not_created)
            posix_user.set_home(self.const.spread_hia_novell_user,
                                disk_id=ndisk_id, home=nhome,
                                status=self.const.home_status_not_created)

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
                self._user_create_set_account_type(posix_user, owner_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        return {'uid': uid}

    
    # user home_create (set extra home per spread for a given account)
    all_commands['user_home_create'] = Command(
	("user", "home_create"), AccountName(), Spread(), DiskId(), perm_filter='can_create_user')
    def user_home_create(self, operator, accountname, spread, disk):
	hdisk = Utils.Factory.get('Disk')(self.db)
	account = self._get_account(accountname)
	disk_id, home = self._get_disk_or_home(disk)
        if home is not None:
            if home[0] == ':':
                home = home[1:]
            else:
                raise CerebrumError, "Invalid disk"
	self.ba.can_create_user(operator.get_entity_id(), account)
	if (self._get_constant(spread, "No such spread") not in \
	    [self.const.spread_nis_user, self.const.spread_ans_nis_user,
	     self.const.spread_hia_novell_user, self.const.spread_hia_ad_account]):
	    raise CerebrumError, "Cannot assign home in a non-home spread!"
	if account.has_spread(self._get_constant(spread)):
	    try:
		account.get_home(self._get_constant(spread))
		raise CerebrumError, "User already has a home in spread %s, use user move" % spread
	    except:
		account.set_home(self._get_constant(spread, "No such spread"), 
				 disk_id=disk_id, home=home,
				 status=self.const.home_status_not_created)
	else:
	    account.add_spread(self._get_constant(spread, "No such spread"))
	    account.set_home(self._get_constant(spread, "No such spread"), 
			     disk_id=disk_id, home=home,
			     status=self.const.home_status_not_created)
	account.write_db()
	return "Home updated for %s in spread %s" % (accountname, spread)
	    
    # user delete
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
                       state_data=int(self.const.spread_uio_nis_user))
        return "User %s queued for deletion immediately" % account.account_name

        # raise NotImplementedError, "Feel free to implement this function"

    # user gecos
    all_commands['user_gecos'] = Command(
        ("user", "gecos"), AccountName(), PosixGecos(),
        perm_filter='can_set_gecos')
    def user_gecos(self, operator, accountname, gecos):
        account = self._get_account(accountname, actype="PosixUser")
        # Set gecos to NULL if user requests a whitespace-only string.
        self.ba.can_set_gecos(operator.get_entity_id(), account)
        account.gecos = gecos.strip() or None
        account.write_db()
        return "OK"

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
                try:
                    dest = self._get_entity_name(None, dest)
                except Errors.NotFoundError:
                    pass
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
        for row in account.get_account_types():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (self.num2const[int(row['affiliation'])],
                                           self._format_ou_name(ou)))
	disk = Utils.Factory.get('Disk')(self.db)
	spreads = []
	hm = []
	spreads = account.get_spread()
	for row in spreads:
	    try:
		tmp = account.get_home(int(row['spread']))
		disk.clear()
		disk.find(tmp['disk_id'])
		print tmp['disk_id']
		hm.append("%s/%s (%s)" % (disk.path, account.account_name, self.num2const[int(row['spread'])]))
	    except Errors.NotFoundError:
		tmp = {'disk_id': None, 'home': None}
	ret = {'entity_id': account.entity_id,
	       'spread': ",".join(["%s" % self.num2const[int(a['spread'])]
				   for a in account.get_spread()]),
	       'affiliations': (",\n" + (" " * 15)).join(affiliations),
	       'expire': account.expire_date,
	       'home': ("\n" + (" " * 15)).join(hm)}
	if is_posix:
            group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            ret['uid'] = account.posix_uid
            ret['dfg_posix_gid'] = group.posix_gid
            ret['dfg_name'] = group.group_name
            ret['gecos'] = account.gecos
            ret['shell'] = str(self.num2const[int(account.shell)])
        # TODO: Return more info about account
        if account.get_entity_quarantine():
	    ret['quarantined'] = 'Yes'
	return ret


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

    # user move
    def user_move_prompt_func(self, session, *args):
        all_args = list(args[:])
        print all_args
        if not all_args:
            mt = MoveType()
            return mt.get_struct(self)
        mtype = all_args.pop(0)
        if not all_args:
            an = AccountName()
            return an.get_struct(self)
        ac_name = all_args.pop(0)
        if mtype in ("immediate", "batch", "nofile", "hard_nofile"):
            if not all_args:
                di = DiskId()
                r = di.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif mtype in ("student", "student_immediate", "confirm", "cancel"):
            return {'last_arg': True}
        elif mtype in ("request",):
            if not all_args:
                di = DiskId()
                return di.get_struct(self)
            disk = all_args.pop(0)
            if not all_args:
                ss = SimpleString(help_ref="string_why")
                r = ss.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif mtype in ("give",):
            if not all_args:
                who = GroupName()
                return who.get_struct(self)
            who = all_args.pop(0)
            if not all_args:
                ss = SimpleString(help_ref="string_why")
                r = ss.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        raise CerebrumError, "Bad user_move command (%s)" % mtype
        
    all_commands['user_move'] = Command(
        ("user", "move"), prompt_func=user_move_prompt_func,
        perm_filter='can_move_user')
    def user_move(self, operator, move_type, accountname, *args):
        account = self._get_account(accountname)
        if account.is_expired():
            raise CerebrumError, "Account %s has expired" % account.account_name
        br = BofhdRequests(self.db, self.const)
        spread = int(self.const.spread_uio_nis_user)
        if move_type in ("immediate", "batch", "nofile"):
            disk_id, home = self._get_disk_or_home(args[0])
            self.ba.can_move_user(operator.get_entity_id(), account, disk_id)
            if disk_id is None:
                raise CerebrumError, "Bad destination disk"
            if move_type == "immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               self.const.bofh_move_user_now,
                               account.entity_id, disk_id, state_data=spread)
                return "Command queued for immediate execution"
            elif move_type == "batch":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, disk_id, state_data=spread)
                return "move queued for execution at %s" % br.batch_time
            elif move_type == "nofile":
                old = account.get_home(spread)
                account.set_home(spread, disk_id=disk_id, home=home,
                                 status=old['status'])
                account.write_db()
                return "OK, user moved"
        elif move_type in ("hard_nofile",):
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hard_nofile")
            account.set_home(spread, disk_id=None, home=args[0],
                             status=self.const.home_status_on_disk)
            account.write_db()
            return "OK, user moved to hardcoded homedir"
        elif move_type in ("student", "student_immediate", "confirm", "cancel"):
            self.ba.can_give_user(operator.get_entity_id(), account)
            if move_type == "student":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_student,
                               account.entity_id, None, state_data=spread)
                return "student-move queued for execution at %s" % br.batch_time
            elif move_type == "student_immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               const.bofh_move_student,
                               account.entity_id, None, state_data=spread)
                return "student-move queued for immediate execution"
            elif move_type == "confirm":
                r = br.get_requests(entity_id=account.entity_id,
                                    operation=self.const.bofh_move_request)
                if not r:
                    raise CerebrumError, "No matching request found"
                br.delete_request(account.entity_id,
                                  operation=self.const.bofh_move_request)
                # Flag as authenticated
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, r[0]['destination_id'],
                               state_data=spread)
                return "move queued for execution at %s" % br.batch_time
            elif move_type == "cancel":
                # TBD: Should superuser delete other request types as well?
                count = 0
                for tmp in br.get_requests(entity_id=account.entity_id):
                    if tmp['operation'] in (
                        self.const.bofh_move_student, self.const.bofh_move_user,
                        self.const.bofh_move_give, self.const.bofh_move_request,
                        self.const.bofh_move_user_now):
                        count += 1
                        br.delete_request(request_id=tmp['request_id'])
                return "OK, %i bofhd requests deleted" % count
        elif move_type in ("request",):
            disk, why = args[0], args[1]
            disk_id = self._get_disk(disk)
            self.ba.can_receive_user(operator.get_entity_id(), account, disk_id)
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_request,
                           account.entity_id, disk_id, why)
            return "OK, request registered"
        elif move_type in ("give",):
            self.ba.can_give_user(operator.get_entity_id(), account)
            group, why = args[0], args[1]
            group = self._get_group(group)
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_give,
                           account.entity_id, group.entity_id, why)
            return "OK, 'give' registered"

    # user password
    all_commands['user_password'] = Command(
        ('user', 'password'), AccountName(), AccountPassword(optional=True))
    def user_password(self, operator, accountname, password=None):
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)
        if password is None:
            password = account.make_passwd(accountname)
        else:
            if (operator.get_entity_id() <> account.entity_id and not self.ba.is_superuser(operator.get_entity_id())):
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
        if account.get_entity_quarantine():
            return "OK.  Warning: user has quarantine"
        return "Password altered. Please use misc list_password to print or view the new password."
	
    # user promote_posix
    all_commands['user_promote_posix'] = Command(
        ('user', 'promote_posix'), AccountName(), Spread(), GroupName(),
        PosixShell(default="bash"), DiskId(),
        perm_filter='can_create_user')
    def user_promote_posix(self, operator, accountname, spread,
                           dfg=None, shell=None, home=None):
        is_posix = False
        try:
            self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixUser" % accountname)
        account = self._get_account(accountname)
        spread = int(self._get_constant(spread, "No such spread"))
        pu = PosixUser.PosixUser(self.db)
        uid = pu.get_free_uid()
        group = self._get_group(dfg, grtype='PosixGroup')
        shell = self._get_shell(shell)
        disk_id, home = self._get_disk_or_home(home)
        if home is not None:
            if home[0] == ':':
                home = home[1:]
            else:
                raise CerebrumError, "Invalid disk"
        person = self._get_person("entity_id", account.owner_id)
        self.ba.can_create_user(operator.get_entity_id(), person, disk_id)
        pu.populate(uid, group.entity_id, None, shell, parent=account)
        pu.set_home(spread, disk_id=disk_id, home=home,
                    status=self.const.home_status_not_created)
        pu.write_db()
        return "OK"

    # user posix_delete
    all_commands['user_demote_posix'] = Command(
        ('user', 'demote_posix'), AccountName(), perm_filter='can_create_user')
    def user_demote_posix(self, operator, accountname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("currently limited to superusers")
        user = self._get_account(accountname, actype="PosixUser")
        user.delete_posixuser()
        return "ok"

    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)
    
    # user create
    all_commands['user_reserve'] = Command(
        ('user', 'create_reserve'), prompt_func=user_create_basic_prompt_func,
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='can_create_user')
    def user_reserve(self, operator, idtype, person_id, affiliation, uname):
        person = self._get_person("entity_id", person_id)
        account = self.Account_class(self.db)
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

    # user set_expire
    all_commands['user_set_expire'] = Command(
        ('user', 'set_expire'), AccountName(), Date(),
        perm_filter='can_delete_user')
    def user_set_expire(self, operator, accountname, date):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.expire_date = self._parse_date(date)
        account.write_db()
        return "OK"

    # user set_np_type
    all_commands['user_set_np_type'] = Command(
        ('user', 'set_np_type'), AccountName(), SimpleString(help_ref="string_np_type"),
        perm_filter='can_delete_user')
    def user_set_np_type(self, operator, accountname, np_type):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.np_type = self._map_np_type(np_type)
        account.write_db()
        return "OK"

    def user_set_owner_prompt_func(self, session, *args):
        all_args = list(args[:])
        if not all_args:
            return {'prompt': 'Account name'}
        account_name = all_args.pop(0)
        if not all_args:
            return {'prompt': 'Entity type (group/person)',
                    'default': 'person'}
        entity_type = all_args.pop(0)
        if not all_args:
            return {'prompt': 'Id of the type specified above'}
        id = all_args.pop(0)
        if entity_type == 'person':
            if not all_args:
                person = self._get_person(*self._map_person_id(id))
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s/%s@%s" % (
                        self.num2const[int(aff['affiliation'])],
                        self.num2const[int(aff['status'])],
                        self._format_ou_name(ou))
                    map.append((("%s", name), int(aff['affiliation'])))
                if not len(map) > 1:
                    raise CerebrumError(
                        "Person has no affiliations. Try person affiliation_add")
                return {'prompt': "Choose affiliation from list", 'map': map,
                        'last_arg': True}
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type',
                        'last_arg': True}
            np_type = all_args.pop(0)
        raise CerebrumError, "Client called prompt func with too many arguments"

    all_commands['user_set_owner'] = Command(
        ("user", "set_owner"), prompt_func=user_set_owner_prompt_func,
        perm_filter='is_superuser')
    def user_set_owner(self, operator, *args):
        if args[1] == 'person':
            accountname, entity_type, id, affiliation = args
            new_owner = self._get_person(*self._map_person_id(id))
        else:
            accountname, entity_type, id, np_type = args
            new_owner = self._get_entity(entity_type, id)
            np_type = int(self._get_constant(np_type, "Unknown account type"))

        account = self._get_account(accountname)
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may assign account ownership")
        new_owner = self._get_entity(entity_type, id)
        if account.owner_type == self.const.entity_person:
            for row in account.get_account_types():
                account.del_account_type(row['ou_id'], row['affiliation'])
        account.owner_type = new_owner.entity_type
        account.owner_id = new_owner.entity_id
        if args[1] == 'group':
            account.np_type = np_type
        account.write_db()
        if new_owner.entity_type == self.const.entity_person:
            self._user_create_set_account_type(account, account.owner_id, affiliation)
        return "OK"

    # user shell
    all_commands['user_shell'] = Command(
        ("user", "shell"), AccountName(), PosixShell(default="bash"))
    def user_shell(self, operator, accountname, shell=None):
        account = self._get_account(accountname, actype="PosixUser")
        shell = self._get_shell(shell)
        self.ba.can_set_shell(operator.get_entity_id(), account, shell)
        account.shell = shell
        account.write_db()
        return "OK"

    # user student_create
    all_commands['user_student_create'] = Command(
        ('user', 'student_create'), PersonId())
    def user_student_create(self, operator, person_id):
        raise NotImplementedError, "Feel free to implement this function"

    #
    # commands that are noe available in jbofh, but used by other clients
    #

    all_commands['get_persdata'] = None

    def get_persdata(self, operator, uname):
        ac = self._get_account(uname)
        person_id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(person_id))
        ret = {
            'is_personal': len(ac.get_account_types()),
            'fnr': [{'id': r['external_id'],
                     'source': "%s" % self.num2const[r['source_system']]}
                    for r in person.get_external_id(id_type=self.const.externalid_fodselsnr)]
            }
        ac_types = ac.get_account_types(all_persons_types=True)        
        if ret['is_personal']:
            ac_types.sort(lambda x,y: int(x['priority']-y['priority']))
            for at in ac_types:
                ac2 = self._get_account(at['account_id'], idtype='id')
                ret.setdefault('users', []).append(
                    (ac2.account_name, '%s@UIO_HOST' % ac2.account_name,
                     at['priority'], at['ou_id'], "%s" % self.num2const[int(at['affiliation'])]))
            # TODO: kall ac.list_accounts_by_owner_id(ac.owner_id) for
            # � hente ikke-personlige konti?
        if ac.home is not None:
            ret['home'] = ac.home
        else:
            disk = Utils.Factory.get('Disk')(self.db)
            disk.find(ac.disk_id)
            ret['home'] = '%s/%s' % (disk.path, ac.account_name)
        ret['navn'] = {'cached': person.get_name(
            self.const.system_cached, self.const.name_full)}
        try:
            ret['work_title'] = person.get_name(
                self.const.system_sap, self.const.name_work_title)
        except Errors.NotFoundError:
            pass
        try:
            ret['personal_title'] = person.get_name(
                self.const.system_sap, self.const.name_personal_title)
        except Errors.NotFoundError:
            pass
        return ret

    #
    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable
    #
    def _get_account(self, id, idtype=None, actype="Account"):
        if actype == 'Account':
            account = self.Account_class(self.db)
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

    def _get_email_domain(self, name):
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(name)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown e-mail domain (%s)" % name
        return ed

    def _get_host(self, name):
        host = Utils.Factory.get('Host')(self.db)
        try:
            host.find_by_name(name)
            return host
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown host: %s" % name

    def _get_group(self, id, idtype=None, grtype="Group"):
        if grtype == "Group":
            group = self.Group_class(self.db)
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
        return self._get_constant(shell, "Unknown shell")
    
    def _get_opset(self, opset):
        aos = BofhdAuthOpSet(self.db)
        try:
            aos.find_by_name(opset)
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find op set with name %s" % opset
        return aos

    def _format_ou_name(self, ou):
        return "%02i%02i%02i (%s)" % (ou.fakultet, ou.institutt, ou.avdeling,
                                      ou.short_name)

    def _get_ou(self, ou_id=None, stedkode=None):
        ou = self.OU_class(self.db)
        ou.clear()
        if ou_id is not None:
            ou.find(ou_id)
        else:
            if len(stedkode) != 6 or not stedkode.isdigit():
                raise CerebrumError("Expected 6 digits in stedkode")
            ou.find_stedkode(stedkode[0:2], stedkode[2:4], stedkode[4:6],
                             institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
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
            try:
                int(id)
            except ValueError:
                raise CerebrumError, "Expected int as id"
            ety = Entity.Entity(self.db)
            return ety.get_subclassed_object(id)
        raise CerebrumError, "Invalid idtype"

    def _find_persons(self, arg):
        if arg.isdigit() and len(arg) > 10:  # finn personer fra fnr
            arg = 'fnr:%s' % arg
        ret = []
        person = self.person
        person.clear()
        if arg.find(":") != -1:
            idtype, id = arg.split(":")
            if idtype == 'exp':
                person.clear()
                try:
                    person.find_by_export_id(id)
                    ret.append({'person_id': person.entity_id})
                except Errors.NotFoundError:
                    raise CerebrumError, "Unkown person id"
            elif idtype == 'entity_id':
                person.clear()
                try:
                    person.find(id)
                    ret.append({'person_id': person.entity_id})
                except Errors.NotFoundError:
                    raise CerebrumError, "Unkown person id"
            elif idtype == 'fnr':
                for ss in [self.const.system_fs, self.const.system_sap,
                           self.const.system_manual, self.const.system_migrate]:
                    try:
                        person.clear()
                        person.find_by_external_id(self.const.externalid_fodselsnr, id,
                                                   source_system=ss)
                        ret.append({'person_id': person.entity_id})
                    except Errors.NotFoundError:
                        pass
        elif arg.find("-") != -1:
            # finn personer p� f�dselsdato
            ret = person.find_persons_by_bdate(self._parse_date(arg))

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
        except Errors.TooManyRowsError:
            raise CerebrumError, "ID not unique %s=%s" % (idtype, id)
        return person

    def _map_person_id(self, id):
        """Map <idtype:id> to const.<idtype>, id.  Recognizes
        f�dselsnummer without <idtype>.  Also recognizes entity_id"""
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
        raise CerebrumError, "Unknown person_id type"

    def _get_printerquota(self, account_id):
        pq = PrinterQuotas.PrinterQuotas(self.db)
        try:
            pq.find(account_id)
            return pq
        except Errors.NotFoundError:
            return None

    def _get_name_from_object(self, entity):
        # optimise for common case
        if isinstance(entity, self.Account_class):
            return entity.account_name
        elif isinstance(entity, self.Group_class):
            return entity.group_name
        else:
            # TODO: extend as needed for quasi entity classes like Disk
            return self._get_entity_name(entity.entity_type, entity.entity_id)

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

    def _get_disk_or_home(self, home):
        host = None
        if home.find(":") != -1:
            host, path = home.split(":")
            return None, ':'+path   # We currently don't use the host part
        else:
            path = home
        disk = Utils.Factory.get('Disk')(self.db)
        try:
            disk.find_by_path(path, host)
            disk_id = disk.entity_id
            path = None
        except Errors.NotFoundError:
            disk_id = None
        return disk_id, path

    def _get_disk(self, path):
        disk, home = self._get_disk_or_home(path)
        if disk is None:
            raise CerebrumError("Unknown disk: %s" % path)
        return disk

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

    # The next two functions require all affiliations to be in upper case,
    # and all affiliation statuses to be in lower case.  If this changes,
    # the user will have to type exact case.
    def _get_affiliationid(self, code_str):
        try:
            c = self.const.PersonAffiliation(code_str.upper())
            # force a database lookup to see if it's a valid code
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation")

    def _get_affiliation_statusid(self, affiliation, code_str):
        try:
            c = self.const.PersonAffStatus(affiliation, code_str.lower())
            int(c)
            return c
        except Errors.NotFoundError:
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
        if isinstance(date, DateTime.DateTimeType):
            date = date.Format("%Y-%m-%d")
        try:
            return self.db.Date(*([ int(x) for x in date.split('-')]))
        except:
            raise CerebrumError, "Illegal date: %s" % date

    def _today(self):
        return self._parse_date("%d-%d-%d" % time.localtime()[:3])
	    
    def _parse_range(self, selection):
        lst = []
        try:
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
        except ValueError:
            raise CerebrumError, "Error parsing range '%s'" % selection
        lst.sort()
        return lst
