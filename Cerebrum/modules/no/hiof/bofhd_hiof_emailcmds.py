# -*- coding: iso-8859-1 -*-

# Copyright 2007-2009 University of Oslo, Norway
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
from Cerebrum.modules.no.hiof import bofhd_hiof_help
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailMixin
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules import Email

def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

class BofhdExtension(BofhdEmailMixin, BofhdCommandBase):
    OU_class = Utils.Factory.get('OU')
    # Done bu super?
    #Account_class = Factory.get('Account')
    #Group_class = Factory.get('Group')
    all_commands = {}

    #copy_commands = (
        ##
        ## copy relevant email-cmds and util methods
        ##
        #'email_add_address', 'email_remove_address',
        #'email_info', 'email_primary_address',
        #'email_create_domain', 'email_domain_configuration',
        #'email_domain_info', 'email_add_domain_affiliation',
        #'email_remove_domain_affiliation',
        #'_email_info_account', '__get_valid_email_addrs',
        #'_email_info_spam', 'email_update',
        #'_email_info_forwarding','email_reassign_address',
        #'_email_info_mailman', '_email_info_multi',
        #'_email_info_file', '_email_info_pipe',
        #'_email_info_filters', '_email_info_contact_info',
        #'_email_info_forward', '_set_email_primary_address',
        #'_onoff', '_has_category',
        #'_sync_category', '_update_email_for_ou',
        #'_get_account', '_get_email_domain',
        #'_split_email_address', '_remove_email_address',
        #'_get_affiliationid', '_format_ou_name',
        #'_get_host'
        #)
    copy_commands = (
        #
        # copy relevant helper commands,
        #
        '_onoff', '_has_category', '_sync_category', '_get_affiliationid',
        '_format_ou_name', '_get_host', '_get_account'
        )

    # Decide which email mixins to use?
    email_mixin_commands = ('email_add_address',
                            'email_remove_address',
                            'email_reassign_address',
                            'email_info',
                            'email_update',
                            'email_add_domain_affiliation',
                            'email_remove_domain_affiliation',
                            'email_create_domain',
                            'email_domain_configuration',
                            'email_domain_info',
                            'email_primary_address', )

    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uio_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
            UiOBofhdExtension

        non_all_cmds = ('num2str', )
        for func in BofhdExtension.copy_commands:
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in non_all_cmds:
                BofhdExtension.all_commands[func] = UiOBofhdExtension.all_commands[func]
        x = object.__new__(cls)
        return x

    def __init__(self, server, default_zone='hiof'):
        super(BofhdExtension, self).__init__(server)
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
        # Copy in all defined commands from the superclass that is not defined
        # in this class.
        for key, cmd in super(BofhdExtension, self).all_commands.iteritems():
            if not self.all_commands.has_key(key):
                self.all_commands[key] = cmd

        # ...and the desired email mixin commands
        for key in self.email_mixin_commands:
            self.all_commands[key] = self.default_email_commands[key]

    def get_help_strings(self):
        return (bofhd_hiof_help.group_help,
                bofhd_hiof_help.command_help,
                bofhd_hiof_help.arg_help)

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
                    if not getattr(self.ba, tmp.perm_filter)(
                            account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

    def _email_info_basic(self, acc, et):
        """ Basic email info. """
        info = {}
        data = [info, ]
        if (et.email_target_type != self.const.email_target_Mailman and
                et.email_target_alias is not None):
            info['alias_value'] = et.email_target_alias
        info["account"] = acc.account_name
        if et.email_server_id:
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
            info["server"] = es.name
            info["server_type"] = "N/A"
        else:
            info["server"] = "<none>"
            info["server_type"] = "N/A"
        return data

    def _email_info_detail(self, acc):
        """ Get quotas from Cerebrum, and usage from Cyrus. """
        # NOTE: Very similar to ofk/giske and uio

        info = []
        eq = Email.EmailQuota(self.db)

        # Get quota and usage
        try:
            eq.find_by_target_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)

            if es.email_server_type == self.const.email_server_type_cyrus:
                used = 'N/A'
                limit = None
                pw = self.db._read_password(cereconf.CYRUS_HOST,
                                            cereconf.CYRUS_ADMIN)
                try:
                    cyrus = imaplib.IMAP4(es.name)
                    # IVR 2007-08-29 If the server is too busy, we do not want
                    # to lock the entire bofhd.
                    # 5 seconds should be enough
                    cyrus.socket().settimeout(5)
                    cyrus.login(cereconf.CYRUS_ADMIN, pw)
                    res, quotas = cyrus.getquota("user." + acc.account_name)
                    cyrus.socket().settimeout(None)
                    if res == "OK":
                        for line in quotas:
                            try:
                                folder, qtype, qused, qlimit = line.split()
                                if qtype == "(STORAGE":
                                    used = str(int(qused)/1024)
                                    limit = int(qlimit.rstrip(")"))/1024
                            except ValueError:
                                # line.split fails e.g. because quota isn't set
                                # on server
                                folder, junk = line.split()
                                self.logger.warning(
                                    "No IMAP quota set for '%s'" %
                                    acc.account_name)
                                used = "N/A"
                                limit = None
                except (TimeoutException, socket.error):
                    used = 'DOWN'
                except ConnectException, e:
                    used = str(e)
                info.append({'quota_hard': eq.email_quota_hard,
                             'quota_soft': eq.email_quota_soft,
                             'quota_used': used})
                if limit is not None and limit != eq.email_quota_hard:
                    info.append({'quota_server': limit})
            else:
                # Just get quotas
                info.append({'dis_quota_hard': eq.email_quota_hard,
                             'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass
        return info

    #
    # email replace_server [username] [servername]
    #
    all_commands['email_replace_server'] = Command(
        ('email', 'replace_server'),
        AccountName(help_ref='account_name'),
        SimpleString(),
        fs=FormatSuggestion("Ok, new email server: %s", ('new_server', )),
        perm_filter='can_email_address_add')

    def email_replace_server(self, operator, user, server_name):
        """ Replace the server for an email target. """
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        #et, acc = self._get_email_target_and_account(user)
        et = self._get_email_target_for_account(user)
        es = Email.EmailServer(self.db)
        es.clear()
        try:
            es.find_by_name(server_name)
        except Errors.NotFoundError:
            raise CerebrumError("No such server: '%s'" % server_name)
        if et.email_server_id != es.entity_id:
            et.email_server_id = es.entity_id
            try:
                et.write_db()
            except self.db.DatabaseError, m:
                raise CerebrumError("Database error: %s" % m)
        else:
            raise CerebrumError(
                "No change, from-server equeals to-server: %s" % server_name)
        return {'new_server': server_name, }
