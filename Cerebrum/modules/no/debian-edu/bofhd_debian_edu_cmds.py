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

import re
import sys
import time
import os
import cyruslib
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
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.Email import _EmailDomainCategoryCode
from Cerebrum.modules import PasswordChecker
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthOpSet, \
     AuthConstants, BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.debian-edu import bofhd_debian_edu_help
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
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)
        self.fixup_imaplib()

    def fixup_imaplib(self):
        import imaplib
        def nonblocking_open(self, host, port):
            import socket
            import select
            import errno
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setblocking(False)
            err = self.sock.connect_ex((self.host, self.port))
            # I don't think connect_ex() can ever return success immediately,
            # it has to wait for a roundtrip.
            assert err
            if err <> errno.EINPROGRESS:
                raise ConnectException(errno.errorcode[err])

            ignore, wset, ignore = select.select([], [self.sock], [], 1.0)
            if not wset:
                raise TimeoutException
            err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err == 0:
                self.sock.setblocking(True)
                self.file = self.sock.makefile('rb')
                return
            raise ConnectException(errno.errorcode[err])
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
        return (bofhd_debian_edu_help.group_help, bofhd_debian_edu_help.command_help,
                bofhd_debian_edu_help.arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()


    #
    # email commands start
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
        ("Type:             %s",
         ("target_type",)),
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
        ttype_name = str(self.const.EmailTarget(ttype))
        ret = [ {'target_type': ttype_name } ]
        # The target_type in ret is overwritten when it is considered
        # redundant information.
        if ttype == self.const.email_target_Mailman:
            ret = self._email_info_mailman(uname, et)
        elif ttype == self.const.email_target_multi:
            ret += self._email_info_multi(uname, et)
        elif ttype == self.const.email_target_pipe:
            ret = self._email_info_pipe(uname, et)
        elif ttype == self.const.email_target_forward:
            ret += self._email_info_forward(uname, et)
        elif ttype == self.const.email_target_account:
            ret = self._email_info_account(operator, acc, et)
        elif ttype == self.const.email_target_deleted:
            ret += self._email_info_account(operator, acc, et)
        else:
            raise CerebrumError, ("email info for target type %s isn't "
                                  "implemented") % ttype_name
        return ret

    def _email_info_account(self, operator, acc, et):
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
            info["server_type"] = str(self.const.EmailServerType(type))
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
            spam_lev = self.const.EmailSpamLevel(esf.email_spam_level)
            spam_act = self.const.EmailSpamAction(esf.email_spam_action)
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
                    if used is None:
                        used = 'N/A'
                    else:
                        used = str(used/1024)
                except TimeoutException:
                    used = 'DOWN'
                except ConnectException, e:
                    used = str(e)
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
            affiliations[ou] = affname
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
        try:
            lp, dom = localaddr.split('@')
        except ValueError:
            raise CerebrumError, "invalid format for e-mail address"
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
        codes = self.const.fetch_constants(self.const.EmailSpamLevel,
                                           prefix_match=level)
        if len(codes) == 1:
            levelcode = codes[0]
        elif len(codes) == 0:
            raise CerebrumError, "Spam level code not found: %s" % level
        else:
            raise CerebrumError, ("'%s' does not uniquely identify a spam "+
                                  "level") % level
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
        codes = self.const.fetch_constants(self.const.EmailSpamAction,
                                           prefix_match=action)
        if len(codes) == 1:
            actioncode = codes[0]
        elif len(codes) == 0:
            raise CerebrumError, "Spam action code not found: %s" % action
        else:
            raise CerebrumError, ("'%s' does not uniquely identify a spam "+
                                  "action") % action
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
                self.logger.warn(
                    "bogus tripnote for %s, start at %s, end at %s"
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
    # email-commands end
    #
   
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

    # misc change_request
    all_commands['misc_change_request'] = Command(
        ("misc", "change_request"), Id(help_ref="id:request_id"), Date())
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

    #
    # misc-commands end
    #

    #
    # person commands start
    #

    # person create
    all_commands['person_create'] = Command(
        ("person", "create"), PersonId(),
        Date(help_ref='date_birth'), PersonName(help_ref="person_name_first"), 
	PersonName(help_ref="person_name_last"), OU(),
        Affiliation(), AffiliationStatus(),
        fs=FormatSuggestion("Created: %i",
        ("person_id",)), perm_filter='can_create_person')
    def person_create(self, operator, person_id, bdate, person_name_first,
		      person_name_last, ou, affiliation, aff_status):
	print ou
        try:
            ou = self._get_ou(int(ou))
	    print ou.entity_id
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
        person.affect_names(self.const.system_manual, self.const.name_first, 
			    self.const.name_last)
        person.populate_name(self.const.name_first,
                             person_name_first.encode('iso8859-1'))
	person.populate_name(self.const.name_last,
                             person_name_last.encode('iso8859-1'))
        try:
            person.write_db()
            self._person_affiliation_add_helper(
                operator, person, ou, str(aff), aff_status)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

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

    # person affiliation commands
    def _person_affiliation_add_helper(self, operator, person, ou, aff, aff_status):
        """Helper-function for adding an affiliation to a person with
        permission checking.  person is expected to be a person
        object, while ou, aff and aff_status should be the textual
        representation from the client"""
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(ou)

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
        return "OK, added %s@%s to %s" % (aff, ou, person.entity_id)

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
        ou = self._get_ou(ou)
        self.ba.can_remove_affiliation(operator.get_entity_id(), person, ou, aff)
        for row in person.list_affiliations(person_id=person.entity_id,
                                            affiliation=aff):
            if row['ou_id'] != int(ou.entity_id):
                continue
            if int(row['source_system']) not \
                   in [int(self.const.system_fs), int(self.const.system_lt)]:
                person.delete_affiliation(ou.entity_id, aff,
                                          row['source_system'])
        return "OK, removed %s@%s from %s" % (aff, ou, person.entity_id)

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
                # s/he has moreef than one kind of affiliation.  Store
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
                ou))
        return {'name': person.get_name(self.const.system_cached,
                                        getattr(self.const,
                                                cereconf.DEFAULT_GECOS_NAME)),
                'affiliations': (",\n" + (" " * 15)).join(affiliations),
                'export_id': person.export_id,
                'birth': person.birth_date}
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
        try:
            old_priority = int(old_priority)
            new_priority = int(new_priority)
        except ValueError:
            raise CerebrumError, "priority must be a number"
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
                self.num2const[int(row['affiliation'])], ou)})
            ## This seems to trigger a wierd python bug:
            ## self.num2const[int(row['affiliation'], ou)])})
        return ret

    #
    # person commands end
    #

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

    #
    # quarantine commands end
    #

    # 
    # spread commands start
    #
    # spread add
    all_commands['spread_add'] = Command(
        ("spread", "add"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
    def spread_add(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spread = int(self._get_constant(spread, "No such spread"))
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
        if spread == int(self.const.spread_uio_imap):
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
    # group commands start
    #

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
    # user commands start
    #

    # user _create_basic_prompt
    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)
    
    # user _create_prompt_func_helper

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
                        ou)
                    map.append((("%s", name),
                                (int(aff['ou_id']), int(aff['affiliation']))))
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

    # user create
    all_commands['user_reserve'] = Command(
        ('user', 'create_reserve'), prompt_func=user_create_basic_prompt_func,
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='is_superuser')
    def user_reserve(self, operator, *args):
        if args[0].startswith('group:'):
            group_id, np_type, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = int(self._get_constant(np_type, "Unknown account type"))
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
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        try:
            account.write_db()
            if affiliation is not None:
                ou_id, affiliation = affiliation
                self._user_create_set_account_type(
                    account, person.entity_id, ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(account.entity_id),
                                                    'password': passwd})
        return {'account_id': int(account.entity_id)}

    # user create_set_account_type
    def _user_create_set_account_type(self, account,
                                      owner_id, ou_id, affiliation):
        person = self._get_person('entity_id', owner_id)
        try:
            affiliation=self.const.PersonAffiliation(affiliation)
            # make sure exist
            int(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError, "Invalid affiliation %s" % affiliation
        for aff in person.get_affiliations():
            if aff['ou_id'] == ou_id and aff['affiliation'] == affiliation:
                break
        else:
            raise CerebrumError, \
                "Owner did not have any affiliation %s" % affiliation        
        account.set_account_type(ou_id, affiliation)

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
                                           ou))
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

    # user commands end

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
    
    def _get_ou(self, ou_id=None):
	ou = self.OU_class(self.db)
        ou.clear()
        if ou_id is not None:
            ou.find(ou_id)
        else:
            if not ou_id.isdigit():
                raise CerebrumError("Expected a digit")
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

# arch-tag: e8f36d36-0488-4d11-ba87-dd399acd0f4f
