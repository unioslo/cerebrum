# -*- coding: iso-8859-1 -*-

# Copyright 2002-2005 University of Oslo, Norway
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

# This file is an implementation of bofhd_commands for the INDIGO
# project. It contains a few basic commands for manipulation of
# person, organization and user information.  

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
from Cerebrum.modules.no.feidegvs import bofhd_feidegvs_help
from Cerebrum.modules.templates.letters import TemplateHandler

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

class ConnectException(Exception):
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
            self.name_codes[int(t['code'])] = t['description']
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
        def nonblocking_open(self, host=None, port=None):
            import socket
            import select
            import errno
            # Perhaps using **kwargs is cleaner, but this works, too.
            if host is None:
                if not hasattr(self, "host"):
                    self.host = ''
            else:
                self.host = host
            if port is None:
                if not hasattr(self, "port"):
                    self.port = 143
            else:
                self.port = port

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
        return (bofhd_feidegvs_help.group_help, bofhd_feidegvs_help.command_help,
                bofhd_feidegvs_help.arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()


    #
    # email commands
    #

    def _split_email_address(self, addr):
        if addr.count('@') == 0:
            raise CerebrumError, \
                  "E-mail address (%s) must include domain" % addr
        lp, dom = addr.split('@')
        if addr != addr.lower() and \
               dom not in cereconf.LDAP['rewrite_email_domain']:
            raise CerebrumError, \
                  "E-mail address (%s) can't contain upper case letters" % addr
        return lp, dom
                                                    
    # email add_address <address or account> <address>+
    all_commands['email_add_address'] = Command(
        ('email', 'add_address'),
        AccountName(help_ref='account_name'),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='is_superuser')
    def email_add_address(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        ttype = et.email_target_type
        if ttype not in (self.const.email_target_Mailman,
                         self.const.email_target_forward,
                         self.const.email_target_file,
                         self.const.email_target_multi,
                         self.const.email_target_pipe,
                         self.const.email_target_account):
            raise CerebrumError, ("Can't add e-mail address to target "+
                                  "type %s") % self.num2const[ttype]
        ea = Email.EmailAddress(self.db)
        lp, dom = self._split_email_address(address)
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
        return "OK, added '%s' as email-address for '%s'" % (address, uname)
    
    # email remove_address <account> <address>+
    all_commands['email_remove_address'] = Command(
        ('email', 'remove_address'),
        AccountName(help_ref='account_name'),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='is_superuser')
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
        if address.count('@') != 1:
            raise CerebrumError, "Malformed e-mail address (%s)" % address
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
        addresses = et.get_addresses()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.email_target_id)
            primary = epat.email_primaddr_id
        except Errors.NotFoundError:
            primary = None

        if primary == ea.email_addr_id:
            if len(addresses) == 1:
                # We're down to the last address, remove the primary
                epat.delete()
            else:
                raise CerebrumError, \
                      "Can't remove primary address <%s>" % address
        ea.delete()
        if len(addresses) > 1:
            # there is at least one address left
            return "OK, removed '%s'" % address
        # clean up and remove the target.
        et.delete()
        return "OK, also deleted e-mail target"

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
        ("Account:          %s\nMail server:      %s (%s)",
         ("account", "server", "server_type")),
        ("Default address:  %s",
         ("def_addr", )),
        # We use valid_addr_1 and (multiple) valid_addr to enable
        # programs to get the information reasonably easily, while
        # still keeping the suggested output format pretty.
        ("Valid addresses:  %s",
         ("valid_addr_1", )),
        ("                  %s",
         ("valid_addr",)),
        ("Mail quota:       %d MiB, warn at %d%% (not enforced)",
         ("dis_quota_hard", "dis_quota_soft")),
        ("Mail quota:       %d MiB, warn at %d%% (%s MiB used)",
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

        ret = []
        if ttype not in (self.const.email_target_account,
                         self.const.email_target_Mailman,
                         self.const.email_target_pipe):
            ret += [ {'target_type': ttype_name } ]

        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.email_target_id)
        except Errors.NotFoundError:
            if ttype == self.const.email_target_account:
                ret.append({'def_addr': "<none>"})
        else:
            ret.append({'def_addr': self.__get_address(epat)})

        if ttype == self.const.email_target_Mailman:
            ret += self._email_info_mailman(uname, et)
        elif ttype == self.const.email_target_multi:
            ret += self._email_info_multi(uname, et)
        elif ttype == self.const.email_target_pipe:
            ret += self._email_info_pipe(uname, et)
        elif ttype == self.const.email_target_forward:
            ret += self._email_info_forward(uname, et)
        elif ttype == self.const.email_target_account:
            ret += self._email_info_account(operator, acc, et)
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
            ret += self._email_info_detail(acc)
            ret += self._email_info_forwarding(et, addrs)
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

    def _email_info_detail(self, acc):
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
        return info

    def _email_info_forwarding(self, target, addrs):
        info = []
        forw = []
        local_copy = ""
        ef = Email.EmailForward(self.db)
        ef.find(target.email_target_id)
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

    # The first address in the list becomes the primary address.
    _interface2addrs = {
        'post': ["%(local_part)s@%(domain)s"],
        'mailcmd': ["%(local_part)s-request@%(domain)s"],
        'mailowner': ["%(local_part)s-owner@%(domain)s",
                      "%(local_part)s-admin@%(domain)s",
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
        addrs = self.__get_valid_email_addrs(et)
        ret += self._email_info_spam(et)
        ret += self._email_info_forwarding(et, addrs)
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
            raise CerebrumError, "%s: e-mail domain already exists" % domainname
        except Errors.NotFoundError:
            pass
        if not re.match(r'[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+', domainname):
            raise CerebrumError, "%s: illegal e-mail domain name" % domainname
        if len(desc) < 3:
            raise CerebrumError, "Please supply a better description"
        ed.populate(domainname, desc)
        ed.write_db()
        return "OK, domain '%s' created" % domainname

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
        if onoff.lower() in ('on', 'true', 'yes'):
            return True
        elif onoff.lower() in ('off', 'false', 'no'):
            return False
        raise CerebrumError, "Enter one of ON or OFF, not %s" % onoff

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
            ou = self._get_ou(ou_id=r['entity_id'])
            affname = "<any>"
            if r['affiliation']:
                affname = str(self.num2const[int(r['affiliation'])])
            affiliations[ou.name] = affname
        aff_list = affiliations.keys()
        aff_list.sort()
        for ou in aff_list:
            ret.append({'affil': affiliations[ou], 'ou': ou})
        return ret

    # email add_domain_affiliation <domain> <sted> [<affiliation>]
    all_commands['email_add_domain_affiliation'] = Command(
        ("email", "add_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(), Affiliation(optional=True),
        perm_filter="can_email_domain_create")
    def email_add_domain_affiliation(self, operator, domainname, sted, aff=None):
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        try:
            ou = self._get_ou(ou_id=sted)
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
            count = self._update_email_for_ou(ou.entity_id, aff_id)
            # Perhaps we should return the values with a format
            # suggestion instead, but the message is informational,
            # and we have three different formats so it would be
            # awkward to do "right".
            return "OK, %d accounts updated" % count
        else:
            old_dom = eed.entity_email_domain_id
            if old_dom <> ed.email_domain_id:
                eed.entity_email_domain_id = ed.email_domain_id
                eed.write_db()
                count = self._update_email_for_ou(ou.entity_id, aff_id)
                ed.clear()
                ed.find(old_dom)
                return "OK (was %s), %d accounts updated" % \
                       (ed.email_domain_name, count)
            return "OK (no change)"

    def _update_email_for_ou(self, ou_id, aff_id):
        """Updates the e-mail addresses for all accounts where the
        given affiliation is their primary, and returns the number of
        modified accounts."""

        count = 0
        acc = self.Account_class(self.db)
        acc2 = self.Account_class(self.db)
        for r in acc.list_accounts_by_type(ou_id=ou_id, affiliation=aff_id):
            acc2.clear()
            acc2.find(r['account_id'])
            primary = acc2.get_account_types()[0]
            if (ou_id == primary['ou_id'] and
                (aff_id is None or aff_id == primary['affiliation'])):
                acc2.update_email_addresses()
                count += 1
        return count

    # email remove_domain_affiliation <domain> <sted> [<affiliation>]
    all_commands['email_remove_domain_affiliation'] = Command(
        ("email", "remove_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(), Affiliation(optional=True),
        perm_filter="can_email_domain_create")
    def email_remove_domain_affiliation(self, operator, domainname, sted,
                                        aff=None):
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        try:
            ou = self._get_ou(ou_id=sted)
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
        return "OK, removed domain-affiliation for '%s'" % domainname

    # email quota <uname>+ hardquota-in-mebibytes [softquota-in-percent]
    all_commands['email_quota'] = Command(
        ('email', 'quota'),
        AccountName(help_ref='account_name', repeat=True),
        Integer(help_ref='number_size_mib'),
        Integer(help_ref='number_percent', optional=True),
        perm_filter='can_email_set_quota')
    def email_quota(self, operator, uname, hquota,
                    squota=cereconf.EMAIL_SOFT_QUOTA):
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_set_quota(op, acc)
        if not hquota.isdigit() or not str(squota).isdigit():
            raise CerebrumError, "Quota must be numeric"
        hquota = int(hquota)
        squota = int(squota)
        if hquota < 100:
            raise CerebrumError, "The hard quota can't be less than 100 MiB"
        if hquota > 1024*1024:
            raise CerebrumError, "The hard quota can't be more than 1 TiB"
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
            # If we're supposed to put a request in BofhdRequests we'll have to
            # be sure that the user getting the quota is a Cyrus-user. If not,
            # Cyrus will spew out errors telling us "user foo is not a cyrus-user".
            est = Email.EmailServerTarget(self.db)
            try:
                est.find(et.email_target_id)
            except Errors.NotFoundError:
                raise CerebrumError, ("The account %s has no e-mail server "+
                                      "associated with it") % uname
            es = Email.EmailServer(self.db)
            es.find(est.email_server_id)
                    
            if es.email_server_type == self.const.email_server_type_cyrus:
                br = BofhdRequests(self.db, self.const)
                # if this operator has already asked for a quota change, but
                # process_bofh_requests hasn't run yet, delete the existing
                # request to avoid the annoying error message.
                for r in br.get_requests(operation=self.const.bofh_email_hquota,
                                         operator_id=op, entity_id=acc.entity_id):
                    br.delete_request(request_id=r['request_id'])
                br.add_request(op, br.now, self.const.bofh_email_hquota,
                               acc.entity_id, None)
        return "OK, set quota for '%s'" % uname

    # email update <uname>
    # Anyone can run this command.  Ideally, it should be a no-op,
    # and we should remove it when that is true.
    all_commands['email_update'] = Command(
        ('email', 'update'),
        AccountName(help_ref='account_name', repeat=True))
    def email_update(self, operator, uname):
        acc = self._get_account(uname)
        acc.update_email_addresses()
        return "OK, updated e-mail address for '%s'" % uname

    # email help

    def __get_email_target_and_account(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et = Email.EmailTarget(self.db)
        acc = None
        if address.count('@') > 1:
            raise CerebrumError, "Malformed e-mail address (%s)" % address
        elif address.count('@') == 1:
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

    # entity_info    
    def _entity_info(self, entity):
        result = {}
        result['type'] = self.num2str(entity.entity_type)
        result['entity_id'] = entity.entity_id
        if entity.entity_type in \
            (self.const.entity_group, self.const.entity_account): 
            result['creator_id'] = entity.creator_id
            result['create_date'] = entity.create_date
            result['expire_date'] = entity.expire_date
            # FIXME: Should be a list instead of a string, but text
            # clients doesn't know how to view such a list
            result['spread'] = ", ".join([str(self.const.Spread(r['spread']))
                                          for r in entity.get_spread()])
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
        src_name = self._get_name_from_object(src_entity)
        # Make the error message for the most common operator error
        # more friendly.  Don't treat this as an error, useful if the
        # operator has specified more than one entity.
        if group_d.has_member(src_entity.entity_id, src_entity.entity_type,
                              group_operator):
            return "%s is already a member of %s" % (src_name, dest_group)
        # This can still fail, e.g., if the entity is a member with a
        # different operation.
        try:
            group_d.add_member(src_entity.entity_id, src_entity.entity_type,
                               group_operator)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        # Warn the user about NFS filegroup limitations.
        for spread_name in cereconf.NIS_SPREADS:
            fg_spread = getattr(self.const, spread_name)
            for row in group_d.get_spread():
                if row['spread'] == fg_spread:
                    count = self._group_count_memberships(src_entity.entity_id,
                                                          fg_spread)
                    if count > 16:
                        return ("WARNING: %s is a member of %d groups with "
                                "spread %s" % (src_name, count, fg_spread))
        return "OK, added %s to %s" % (src_name, dest_group)

    def _group_count_memberships(self, entity_id, spread):
        """Count how many groups of a given spread entity_id has
        entity_id as a member, either directly or indirectly."""
        groups = {}
        gr = Utils.Factory.get("Group")(self.db)
        for r in gr.list_groups_with_entity(entity_id):
            # TODO: list_member_groups recurses upwards and returns a
            # list with the "root" as the last element.  We should
            # actually look at just that root and recurse downwards to
            # generate group lists to process difference and
            # intersection correctly.  Seems a lot of work to support
            # something we don't currently use, and it's probably
            # better to improve the API of list_member_groups anyway.
            if r['operation'] != self.const.group_memberop_union:
                continue
            # It would be nice if list_groups_with_entity included the
            # spread column, but that would lead to duplicate rows.
            # So we do the filtering here.
            gr.clear()
            gr.find(r['group_id'])
            for sp_row in gr.get_spread():
                if (sp_row['spread'] == spread):
                    groups[int(r['group_id'])] = True
            for group_id in gr.list_member_groups(r['group_id'],
                                                  spreads=(spread,)):
                groups[group_id] = True
        return len(groups.keys())

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

    # group delete
    all_commands['group_delete'] = Command(
        ("group", "delete"), GroupName(), YesNo(help_ref="yes_no_force", default="No"),
        perm_filter='can_delete_group')
    def group_delete(self, operator, groupname, force=None):
        grp = self._get_group(groupname)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        if self._is_yes(force):
            try:
                pg = self._get_group(groupname, grtype="PosixGroup")
                pg.delete()
            except CerebrumError:
                pass   # Not a PosixGroup
        self._remove_auth_target("group", grp.entity_id)
        self._remove_auth_role(grp.entity_id)
        grp.delete()
        return "OK, deleted group '%s'" % groupname

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
        member_name = self._get_name_from_object(member)
        if not group.has_member(member.entity_id, member.entity_type,
                                group_operation):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        if member.entity_type == self.const.entity_account:
            try:
                pu = PosixUser.PosixUser(self.db)
                pu.find(member.entity_id)
                if pu.gid_id == group.entity_id:
                    raise CerebrumError, ("Can't remove %s from primary group" %
                                          member_name)
            except Errors.NotFoundError:
                pass
        try:
            group.remove_member(member.entity_id, group_operation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)

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
                              ('gid',)),
                             ("Members:      %i groups, %i accounts",
                              ('c_group_u', 'c_account_u')),
                             ("Members (intersection): %i groups, %i accounts",
                              ('c_group_i', 'c_account_i')),
                             ("Members (difference):   %i groups, %i accounts",
                              ('c_group_d', 'c_account_d'))]))
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
        # Count group members of different types
        u, i, d = grp.list_members()
        
        for members, op in ((u, 'u'), (i, 'i'), (d, 'd')):
            tmp = {}
            for ret_pfix, entity_type in (
                ('c_group_', int(self.const.entity_group)),
                ('c_account_', int(self.const.entity_account))):
                tmp[ret_pfix+op] = len(
                    [x for x in members if int(x[0]) == entity_type])
            if [x for x in tmp.values() if x > 0]:
                ret.append(tmp)
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
        # TBD: the default is to leave out include expired accounts or
        # groups.  How should we make the information about expired
        # members available?
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

    # group set_description
    all_commands['group_set_description'] = Command(
        ("group", "set_description"),
        GroupName(), SimpleString(help_ref="string_description"),
        perm_filter='can_delete_group')
    def group_set_description(self, operator, group, description):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.description = description
        grp.write_db()
        return "OK, description for group '%s' updated" % group

    # group set_expire
    all_commands['group_set_expire'] = Command(
        ("group", "set_expire"), GroupName(), Date(), perm_filter='can_delete_group')
    def group_set_expire(self, operator, group, expire):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.expire_date = self._parse_date(expire)
        grp.write_db()
        return "OK, set expire-date for '%s'" % group

    # group set_visibility
    all_commands['group_set_visibility'] = Command(
        ("group", "set_visibility"), GroupName(), GroupVisibility(),
        perm_filter='can_delete_group')
    def group_set_visibility(self, operator, group, visibility):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.visibility = self._map_visibility_id(visibility)
        grp.write_db()
        return "OK, set visibility for '%s'" % group

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
                        'entity_id': grp.entity_id,
                        'group': grp.group_name,
                        'spreads': ",".join(["%s" % self.num2const[int(a['spread'])]
                                             for a in grp.get_spread()])})
        ret.sort(lambda a,b: cmp(a['group'], b['group']))
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
    # TBD: this command should be renamed "misc check_password"
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
        return "OK, passwords cleared"

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
	    mapping['address_line2'] = account.acount_name
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
    # TBD: this command should be renamed "misc check_user_password"
    all_commands['misc_user_passwd'] = Command(
        ("misc", "user_passwd"), AccountName(), AccountPassword())
    def misc_user_passwd(self, operator, accountname, password):
        ac = self._get_account(accountname)
        if isinstance(password, unicode):  # crypt.crypt don't like unicode
            password = password.encode('iso8859-1')
        # Only people who can set the password are allowed to check it
        self.ba.can_set_password(operator.get_entity_id(), ac)
        old_pass = ac.get_account_authentication(self.const.auth_type_md5_crypt)
        salt = old_pass[:old_pass.rindex('$')]
        if ac.enc_auth_type_md5_crypt(password, salt=salt) == old_pass:
            return "Password is correct"
        return "Incorrect password"

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
        for r in account.list_accounts_by_owner_id(person.entity_id,
                                                   filter_expired=False):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name,
                        'expire': account.expire_date})
        return ret

    def _person_affiliation_add_helper(self, operator, person, sted, aff, aff_status):
        """Helper-function for adding an affiliation to a person with
        permission checking.  person is expected to be a person
        object, while ou, aff and aff_status should be the textual
        representation from the client"""
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(ou_id=sted)

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
        return "OK, added %s@%s to %s" % (aff, ou.name, person.entity_id)

    # person affilation_remove
    all_commands['person_affiliation_remove'] = Command(
        ("person", "affiliation_remove"), PersonId(), OU(), Affiliation(),
        perm_filter='can_remove_affiliation')
    def person_affiliation_remove(self, operator, person_id, sted, aff):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(ou_id=sted)
        self.ba.can_remove_affiliation(operator.get_entity_id(), person, ou, aff)
        for row in person.list_affiliations(person_id=person.entity_id,
                                            affiliation=aff):
            if row['ou_id'] != int(ou.entity_id):
                continue
            if int(row['source_system']) <> int(self.const.system_sas):
                person.delete_affiliation(ou.entity_id, aff,
                                          row['source_system'])
        return "OK, removed %s@%s from %s" % (aff, ou.name, person.entity_id)

    # person create
    all_commands['person_create'] = Command(
        ("person", "create"), PersonId(),
        Date(help_ref='date_birth'), PersonName(help_ref="person_name_first"), 
	PersonName(help_ref="person_name_last"), OU(),
        Affiliation(), AffiliationStatus(),
        fs=FormatSuggestion("Created: %i",
        ("person_id",)), perm_filter='can_create_person')
    def person_create(self, operator, person_id, bdate, person_name_first,
		      person_name_last, sted, affiliation, aff_status):
        try:
            ou = self._get_ou(ou_id=sted)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % ou
        try:
            aff = self._get_affiliationid(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown affiliation type (%s)" % affiliation
        self.ba.can_create_person(operator.get_entity_id(), ou.entity_id, aff)
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
                operator, person, ou.entity_id, str(aff), aff_status)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    # person find
    all_commands['person_find'] = Command(
        ("person", "find"), PersonSearchType(), SimpleString(),
        SimpleString(optional=True),
        fs=FormatSuggestion("%6i   %10s   %-12s  %s",
                            ('id', format_day('birth'), 'export_id', 'name'),
                            hdr="%6s   %10s   %-12s  %s" % \
                            ('Id', 'Birth', 'Exp-id', 'Name')))
    def person_find(self, operator, search_type, value, filter=None):
        # TODO: Need API support for this
        matches = []
        if search_type == 'person_id':
            person = self._get_person(*self._map_person_id(value))
            matches = [{'person_id': person.entity_id}]
        else:
            person = self.person
            person.clear()
            if search_type == 'name':
                if len(value.strip()) < 2:
                    raise CerebrumError, \
                          "You have to specify at least two letters of the name"
                if '%' not in value and '_' not in value:
                    # Add wildcards to start and end of value.
                    value = '%' + value + '%'
                if value <> value.lower():
                    matches = person.find_persons_by_name(value,
                                                          case_sensitive=True)
                else:
                    matches = person.find_persons_by_name(value)
            elif search_type == 'fnr':
                matches = person.list_external_ids(
                    id_type=self.const.externalid_fodselsnr,
                    external_id=value)
            elif search_type == 'date':
                matches = person.find_persons_by_bdate(self._parse_date(value))
            elif search_type == 'stedkode':
                ou = self._get_ou(ou_id=value)
                if filter is not None:
                    try:
                        filter=self.const.PersonAffiliation(filter)
                    except Errors.NotFoundError:
                        raise CerebrumError, "Invalid affiliation %s" % affiliation
                matches = person.list_affiliations(ou_id=ou.entity_id,
                                                   affiliation=filter)
            else:
                raise CerebrumError, "Unknown search type (%s)" % search_type
        ret = []
        seen = {}
        for row in matches:
            # We potentially get multiple rows for a person when
            # s/he has more than one source system or affiliation.
            col = 'entity_id'
            if not row.has_key(col):
                col = 'person_id'
            if row[col] in seen:
                continue
            seen[row[col]] = True
            person = self._get_person('entity_id', row[col])
            pname = person.get_name(self.const.system_cached,
                                    getattr(self.const,
                                            cereconf.DEFAULT_GECOS_NAME))
            # Ideally we'd fetch the authoritative last name, but
            # it's a lot of work.  We cheat and use the last word
            # of the name, which should work for 99.9% of the users.
            ret.append({'id': row[col],
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
                 'birth': person.birth_date,
                 'entity_id': person.entity_id}]
        affiliations = []
        sources = []
        for row in person.get_affiliations():
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (
                self.const.PersonAffStatus(row['status']),
                ou.name))
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
        account = self.Account_class(self.db)
        account_ids = [int(r['account_id'])
                       for r in account.list_accounts_by_owner_id(person.entity_id)]
        if (self.ba.is_superuser(operator.get_entity_id()) or
            operator.get_entity_id() in account_ids):
            for row in person.get_external_id(id_type=self.const.externalid_fodselsnr):
                data.append({'fnr': row['external_id'],
                             'fnr_src': str(
                    self.const.AuthoritativeSystem(row['source_system']))})
        return data

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
        qconst = self._get_constant(qtype, "No such quarantine")
        qtype = int(qconst)
        self.ba.can_disable_quarantine(operator.get_entity_id(), entity, qtype)
        entity.disable_entity_quarantine(qtype, date)
        return "OK, disabled quarantine %s for %s" % (
            qconst, self._get_name_from_object (entity))

    # quarantine list
    all_commands['quarantine_list'] = Command(
        ("quarantine", "list"),
        fs=FormatSuggestion("%-16s  %1s  %-17s %s",
                            ('name', 'lock', 'shell', 'desc'),
                            hdr="%-15s %-4s %-17s %s" % \
                            ('Name', 'Lock', 'Shell', 'Description')))
    def quarantine_list(self, operator):
        ret = []
        for c in self.const.fetch_constants(self.const.Quarantine):
            lock = 'N'; shell = '-'
            rule = cereconf.QUARANTINE_RULES.get(str(c), {})
            if 'lock' in rule:
                lock = 'Y'
            if 'shell' in rule:
                shell = rule['shell'].split("/")[-1]
            ret.append({'name': "%s" % c,
                        'lock': lock,
                        'shell': shell,
                        'desc': c._get_description()})
        return ret

    # quarantine remove
    all_commands['quarantine_remove'] = Command(
        ("quarantine", "remove"), EntityType(default="account"), Id(), QuarantineType(),
        perm_filter='can_remove_quarantine')
    def quarantine_remove(self, operator, entity_type, id, qtype):
        entity = self._get_entity(entity_type, id)
        qconst = self._get_constant(qtype, "No such quarantine")
        qtype = int(qconst)
        self.ba.can_remove_quarantine(operator.get_entity_id(), entity, qtype)
        entity.delete_entity_quarantine(qtype)
        return "OK, removed quarantine %s for %s" % (
            qconst, self._get_name_from_object (entity))

    # quarantine set
    all_commands['quarantine_set'] = Command(
        ("quarantine", "set"), EntityType(default="account"), Id(repeat=True),
        QuarantineType(), SimpleString(help_ref="string_why"),
        SimpleString(help_ref="string_from_to"), perm_filter='can_set_quarantine')
    def quarantine_set(self, operator, entity_type, id, qtype, why, date):
        date_start, date_end = self._parse_date_from_to(date)
        entity = self._get_entity(entity_type, id)
        qconst = self._get_constant(qtype, "No such quarantine")
        qtype = int(qconst)
        self.ba.can_set_quarantine(operator.get_entity_id(), entity, qtype)
        rows = entity.get_entity_quarantine(type=qtype)
        if rows:
            raise CerebrumError("User already has a quarantine of this type")
        try:
            entity.add_entity_quarantine(qtype, operator.get_entity_id(), why, date_start, date_end)
        except AttributeError:    
            raise CerebrumError("Quarantines cannot be set on %s" % entity_type)
        return "OK, set quarantine %s for %s" % (
            qconst, self._get_name_from_object (entity))

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
        spreadconst = self._get_constant(spread, "No such spread")
        spread = int(spreadconst)
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        try:
            entity.add_spread(spread)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, added spread %s for %s" % (
            spreadconst, self._get_name_from_object (entity))

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
        spreadconst = self._get_constant(spread, "No such spread")
        spread = int(spreadconst)
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        entity.delete_spread(spread)
        return "OK, removed spread %s from %s" % (
            spreadconst, self._get_name_from_object (entity))


    #
    # user commands
    #




    # user affiliation_add
    all_commands['user_affiliation_add'] = Command(
        ("user", "affiliation_add"), AccountName(), OU(), Affiliation(), AffiliationStatus(),
        perm_filter='can_add_account_type')
    def user_affiliation_add(self, operator, accountname, ou, aff, aff_status):
        account = self._get_account(accountname)
        person = self._get_person('entity_id', account.owner_id)
        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status)
        self.ba.can_add_account_type(operator.get_entity_id(), account, ou, aff, aff_status)
        account.set_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, added %s@%s to %s" % (aff, ou.name,
                                          accountname)

    # user affiliation_remove
    all_commands['user_affiliation_remove'] = Command(
        ("user", "affiliation_remove"), AccountName(), OU(), Affiliation(),
        perm_filter='can_remove_account_type')
    def user_affiliation_remove(self, operator, accountname, sted, aff): 
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(ou_id=sted)
        self.ba.can_remove_account_type(operator.get_entity_id(),
                                        account, ou, aff)
        account.del_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, removed %s@%s from %s" % (aff, ou.name,
                                              accountname)

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
                        ou.name)
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
        raise CerebrumError, "Client called prompt func with too many arguments"


    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)
    
    # user create
    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_basic_prompt_func,
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='is_superuser')
    def user_create(self, operator, *args):
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
            for spread in cereconf.BOFHD_NEW_USER_SPREADS:
                account.add_spread(self._get_constant(spread,"No such spread"))
                if affiliation is not None:
                    ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                    self._user_create_set_account_type(account, person.entity_id, ou_id, affiliation)
                else:
                    raise CerebrumError,"You cannout build accounts for people without affiliation!"
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(account.entity_id),
                                                    'password': passwd})
        return {'account_id': int(account.entity_id)}

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
            ret.append(self._format_changelog_entry(r))
        return "\n".join(ret)

    # user info
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion([("Username:      %s\n"+
                              "Spreads:       %s\n" +
                              "Affiliations:  %s\n" +
                              "Expire:        %s\n" +
                              "Entity id:     %i\n" +
                              "Owner id:      %i (%s: %s)",
                              ("username", "spread", "affiliations",
                               format_day("expire"),
                               "entity_id", "owner_id",
                               "owner_type", "owner_desc")),
                             ("Quarantined:   %s",
                              ("quarantined",))]))
    def user_info(self, operator, accountname):
        account = self._get_account(accountname)
        if account.is_deleted() and not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError("User is deleted")
        affiliations = []
        for row in account.get_account_types(filter_expired=False):
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (self.num2const[int(row['affiliation'])],
                                           ou.name))

        ret = {'entity_id': account.entity_id,
               'username': account.account_name,
               'spread': ",".join(["%s" % self.num2const[int(a['spread'])]
                                   for a in account.get_spread()]),
               'affiliations': (",\n" + (" " * 15)).join(affiliations),
               'expire': account.expire_date,
               'owner_id': account.owner_id,
               'owner_type': str(self.num2const[int(account.owner_type)])}

        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            ret['owner_desc'] = person.get_name(self.const.system_cached,
                                                getattr(self.const,
                                                        cereconf.DEFAULT_GECOS_NAME))
        else:
            grp = self._get_group(account.owner_id, idtype='id')
            ret['owner_desc'] = grp.group_name
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
            if isinstance(password, unicode):  # crypt.crypt don't like unicode
                password = password.encode('iso8859-1')
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
        # Remove "weak password" quarantine
        for r in account.get_entity_quarantine():
            if int(r['quarantine_type']) == self.const.quarantine_autopassord:
                account.delete_entity_quarantine(self.const.quarantine_autopassord)

        if account.get_entity_quarantine():
            return "OK.  Warning: user has quarantine"
        return "Password altered. Please use misc list_password to print or view the new password."
    
    # user set_expire
    all_commands['user_set_expire'] = Command(
        ('user', 'set_expire'), AccountName(), Date(),
        perm_filter='can_delete_user')
    def user_set_expire(self, operator, accountname, date):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.expire_date = self._parse_date(date)
        account.write_db()
        return "OK, set expire-date for %s to %s" % (accountname, date)

    # user set_np_type
    all_commands['user_set_np_type'] = Command(
        ('user', 'set_np_type'), AccountName(), SimpleString(help_ref="string_np_type"),
        perm_filter='can_delete_user')
    def user_set_np_type(self, operator, accountname, np_type):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.np_type = self._map_np_type(np_type)
        account.write_db()
        return "OK, set np-type for %s to %s" % (accountname, np_type)


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
                    if len(id) == 0:
                        raise CerebrumError, "Must specify id"
                else:
                    idtype = 'name'
            if idtype == 'name':
                account.find_by_name(id, self.const.account_namespace)
            elif idtype == 'id':
                if isinstance(id, str) and not id.isdigit():
                    raise CerebrumError, "Entity id must be a number"
                account.find(id)
            else:
                raise CerebrumError, "unknown idtype: '%s'" % idtype
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
                raise CerebrumError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find %s with %s=%s" % (grtype, idtype, id)
        return group

    def _get_ou(self, ou_id):
        ou = self.OU_class(self.db)
        ou.clear()
        try:
            ou.find(ou_id)
            return ou
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown organizational unit"

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
                for ss in [self.const.system_sas,
                           self.const.system_manual]:
                    try:
                        person.clear()
                        person.find_by_external_id(self.const.externalid_fodselsnr, id,
                                                   source_system=ss)
                        ret.append({'person_id': person.entity_id})
                    except Errors.NotFoundError:
                        pass
        elif arg.find("-") != -1:
            # finn personer på fødselsdato
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
                if isinstance(id, str) and not id.isdigit():
                    raise CerebrumError, "Entity id must be a number"
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
            if len(id) == 0:
                raise CerebrumError, "id cannot be blank"
            return id_type, id
        raise CerebrumError, "Unknown person_id type"

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
            # TBD: Is this correct behaviour?  mx.DateTime.DateTime
            # objects allow comparison to None, although that is
            # hardly what we expect/want.
            return None
        if isinstance(date, DateTime.DateTimeType):
            date = date.Format("%Y-%m-%d")
        try:
            y, m, d = [int(x) for x in date.split('-')]
        except ValueError:
            raise CerebrumError, "Dates must be numeric"
        # TODO: this should be a proper delta, but rather than using
        # pgSQL specific code, wait until Python has standardised on a
        # Date-type.
        if y > 2050:
            raise CerebrumError, "Too far into the future: %s" % date
	if y < 1800:
	    raise CerebrumError, "Too long ago: %s" % date
        try:
            return DateTime.Date(y, m, d)
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

    def _format_from_cl(self, format, val):
        # TODO: using num2const is not optimal, but the
        # const.ChangeType(int) magic doesn't work for CLConstants
        if val is None:
            return ''

        if format == 'affiliation':
            return str(self.num2const[int(val)])
        elif format == 'disk':
            disk = Utils.Factory.get('Disk')(self.db)
            try:
                disk.find(val)
                return disk.path
            except Errors.NotFoundError:
                return "deleted_disk:%s" % val
        elif format == 'homedir':
            return 'homedir_id:%s' % val
        elif format == 'id_type':
            return str(self.num2const[int(val)])
        elif format == 'int':
            return str(val)
        elif format == 'name_variant':
            return str(self.num2const[int(val)])
        elif format == 'ou':
            ou = self._get_ou(ou_id=val)
            return ou.name
        elif format == 'quarantine_type':
            return str(self.num2const[int(val)])
        elif format == 'source_system':
            return str(self.num2const[int(val)])
        elif format == 'spread_code':
            return str(self.num2const[int(val)])
        elif format == 'string':
            return str(val)
        elif format == 'value_domain':
            return str(self.num2const[int(val)])
        else:
            self.logger.warn("bad cl format: %s", repr((format, val)))
            return ''

    def _format_changelog_entry(self, row):
        dest = row['dest_entity']
        if dest is not None:
            try:
                dest = self._get_entity_name(None, dest)
            except Errors.NotFoundError:
                pass
        this_cl_const = self.num2const[int(row['change_type_id'])]

        msg = this_cl_const.msg_string % {
            'subject': self._get_entity_name(None, row['subject_entity']),
            'dest': dest}

        # Append information from change_params to the string.  See
        # _ChangeTypeCode.__doc__
        if row['change_params']:
            params = pickle.loads(row['change_params'])
        else:
            params = {}

        if this_cl_const.format:
            for f in this_cl_const.format:
                repl = {}
                for part in re.findall(r'%\([^\)]+\)s', f):
                    fmt_type, key = part[2:-2].split(':')
                    repl['%%(%s:%s)s' % (fmt_type, key)] = self._format_from_cl(
                        fmt_type, params.get(key, None))
                if [x for x in repl.values() if x]:
                    for k, v in repl.items():
                        f = f.replace(k, v)
                    msg += ", " + f
        by = row['change_program'] or self._get_entity_name(None, row['change_by'])
        return "%s [%s]: %s" % (row['tstamp'], by, msg)

# arch-tag: 98930b8a-4170-453a-a5db-34177f3ac40f
