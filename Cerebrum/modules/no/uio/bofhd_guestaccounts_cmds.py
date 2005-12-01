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

import re
import os
import time
from mx import DateTime

import cerebrum_path
import cereconf
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum.Utils import Factory 
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.no.uio import bofhd_uio_help
from Cerebrum.modules.no.uio import GuestAccount
    
class SimpleLogger(object):
    # Unfortunately we cannot user Factory.get_logger due to the
    # singleton behaviour of cerelog.get_logger().  Once this is
    # fixed, this class can be removed.
    def __init__(self, fname):
        self.stream = open(
            os.path.join(cereconf.AUTOADMIN_LOG_DIR, fname), 'a+')
        
    def show_msg(self, lvl, msg, exc_info=None):
        self.stream.write("%s %s [%i] %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            lvl, os.getpid(), msg))
        self.stream.flush()

    def debug2(self, msg, **kwargs):
        self.show_msg("DEBUG2", msg, **kwargs)
    
    def debug(self, msg, **kwargs):
        self.show_msg("DEBUG", msg, **kwargs)

    def info(self, msg, **kwargs):
        self.show_msg("INFO", msg, **kwargs)

    def error(self, msg, **kwargs):
        self.show_msg("ERROR", msg, **kwargs)

    def fatal(self, msg, **kwargs):
        self.show_msg("FATAL", msg, **kwargs)

    def critical(self, msg, **kwargs):
        self.show_msg("CRITICAL", msg, **kwargs)

class BofhdExtension(object):
    all_commands = {}

    def __init__(self, server):
        self.server = server
        self.logger = SimpleLogger('guest_bofhd.log')
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.ba = BofhdAuth(self.db)
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*30)
    def get_help_strings(self):
        group_help = {}

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'user': {
            'user_request_guest': 'Request a number of guest users for a certain time',
            'user_release_guest': 'Manually release guest users that was requested earlier',
            'user_guests': 'Show the guest users that are owned by a group',
            'user_guests_status': 'Show how many guest users are available'
            }
            }

        arg_help = {}
        return (group_help, command_help,
                arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()
    
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

    
    def not_good(self, end_date, today, max_date):
        m = re.match('(\d{4})-(\d\d)-(\d\d)', end_date)
        if not m:
            return True
        else:
            d = DateTime.Date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if d < today or d > max_date:
                return True
        return False
        
    def user_request_guest_prompt_func(self, session, *args):
        all_args = list(args[:])
        if not all_args:
            return {'prompt': 'How many guest users?', 'default': '1'}
        try:
            nr_of_guests = int(all_args[0])
            all_args.pop(0)
        except ValueError:
            all_args.pop(0)  # If not an integer. Ask again
            if not all_args:
                return {'prompt': 'How many guest users?', 'default': '1'}        
        # Date checking
        today = DateTime.today()
        default_date = today + DateTime.RelativeDateTime(weeks=cereconf.GUESTS_DEFAULT_PERIOD)
        max_date = today + DateTime.RelativeDateTime(months=cereconf.GUESTS_MAX_PERIOD)
        if not all_args:
            return {'prompt': 'Enter end date',
                    'default': default_date.date}
        # Don't give up until a correct date is entered
        while self.not_good(all_args[0], today, max_date):
            all_args.pop(0)
            if not all_args:
                return {'prompt': 'Enter end date (YYYY-MM-DD)',
                        'default': default_date.date}    
        end_date = all_args.pop(0)            
        # Get group name. If name is valid is checked in the other method
        if not all_args:
            return {'prompt': 'Enter owner group name', 'last_arg': True}
        owner = all_args.pop(0)
        return {'last_arg': True}

    # user request_guest <nr> <end-date> <entity_name>
    all_commands['user_request_guest'] = Command(
        ('user', 'request_guest'), prompt_func=user_request_guest_prompt_func,
        perm_filter='can_request_guests')
    def user_request_guest(self, operator, *args):
        nr, end_date, groupname = args
        try:
            # Fjern query_run_any=True når ting er klart
            self.ba.can_request_guests(operator.get_entity_id(), groupname, query_run_any=True)
            owner = self._get_group(groupname)
        except Errors.NotFoundError:
            raise CerebrumError("No group wit name %s" % groupname)
        entity_type = self.const.entity_group
        try:
            # FIXME, passwords
            user_list = GuestAccount.request_guest_users(int(nr), end_date,
                                                         entity_type, owner)
            ret = "OK, reserved guest users:\n%s\n" % '\n'.join(user_list)
            # Mer enn 3 brukere, skriv intervall. Pass på om ikke consecutive
            ret += "Please use misc list_passwords to print or view the passwords."
            return ret
        except GuestAccount.GuestAccountException, e:
            print str(e)
            raise CerebrumError("Could not allocate temporary_users. %s" % str(e))
        
    
    # user release_guest [<guest> || <range>]+
    all_commands['user_release_guest'] = Command(
        ('user', 'release_guest'))              # FIXME, hva skal vi sette her?
    def user_release_guest(self, operator, *args):
        guests = []
        if not args:
            # Dette er kanskje ikke måten å gjøre det på...
            return "Usage: user release_guest [<guest> || <range>]+"
        # Hver arg er enten en guest account eller intervall 
        for arg in args:
            if '..' in arg:
                first, last = arg.split('..')
                first = int(first[5:])
                last = int(last[5:])
                for i in range(first, last+1):
                    guests.append('guest%s' % str(i).zfill(3))
            else:
                guests.append(arg)

        for guest in guests:
            # Fjern query_run_any=True når ting er klart
            try:
                self.ba.can_release_guests(operator.get_entity_id(),
                                           GuestAccount.get_guest(guest), query_run_any=True)
                GuestAccount.release_guest(guest, operator.get_entity_id())
            except Errors.NotFoundError:
                raise CerebrumError("Could not find guest account with user name %s" % guest)
            except GuestAccount.GuestAccountException:
                raise CerebrumError("Could not release guest users.")

        # FIXME, utskrift
        return "OK, released guests:\n%s" % '\n'.join(guests)

                    
    # user guests <owner>
    all_commands['user_guests'] = Command(
        ('user', 'guests'), GroupName())
    def user_guests(self, operator, groupname): 
        owner = self._get_group(groupname)
        entity_type = self.const.entity_group 
        try:
            return GuestAccount.list_guest_users(entity_type, owner)
        except GuestAccount.GuestAccountException:
            raise CerebrumError("Could not list guest users.")
    

    all_commands['user_guests_status'] = Command(
        ('user', 'guests_status'))
    def user_guests_status(self, operator):
        return "%d guest accounts available." % GuestAccount.nr_available_accounts()


    def _get_group(self, id, idtype=None, grtype="Group"):
        group = Factory.get('Group')(self.db)    
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
