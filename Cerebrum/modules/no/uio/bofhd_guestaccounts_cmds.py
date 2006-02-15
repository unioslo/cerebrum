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
from mx import DateTime

import cereconf
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum.Utils import Factory 
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.no.uio import bofhd_guestaccounts_utils
    

class BofhdExtension(object):
    all_commands = {}
    Group_class = Factory.get('Group')

    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.bgu = bofhd_guestaccounts_utils.BofhdUtils(server)
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

        arg_help = {
            'release_type': ['release_type', 'Enter release type',
                             """Enter either a guest user name or a range of names.
E.g. guest007 or guest010-guest040."""],
            'guest_owner_group' : ['guest_owner_group', 'Enter name of owner group']
            }
        return (group_help, command_help, arg_help)


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

        
    def user_create_guest_prompt_func(self, session, *args):
        #print "args = ", args
        all_args = list(args[:])
        # get number of new guest users
        if not all_args:
            return {'prompt': 'How many guest users?', 'default': '1'}
        nr_of_guests = int(all_args.pop(0))
        # Get group name. 
        if not all_args:
            return {'prompt': 'Enter owner group name',
                    'default': cereconf.GUESTS_OWNER_GROUP}
        # get default file_group
        owner_group_name = all_args.pop(0)
        if not all_args:
            return {'prompt': "Default filegroup",
                    'default': cereconf.GUESTS_DEFAULT_FILEGROUP}
        filegroup = all_args.pop(0)
        # get shell
        if not all_args:
            return {'prompt': "Shell", 'default': 'bash'}
        shell = all_args.pop(0)
        # get disk
        if not all_args:
            return {'prompt': "Disk", 'help_ref': 'disk', 'last_arg': True}
        disk = all_args.pop(0)
        return {'last_arg': True}


    # user create_guest <nr> <group_id> <filegroup> <shell> <disk> <uname-prefix>
    all_commands['user_create_guest'] = Command(
        ('user', 'create_guest'), prompt_func=user_create_guest_prompt_func,
        perm_filter='can_create_guests')
    def user_create_guest(self, operator, *args):
        "Create <nr> new guest users"
        nr, owner_group_name, filegroup, shell, home = args
        owner_type = self.const.entity_group
        owner_id = self._get_group(owner_group_name).entity_id
        np_type = self.const.account_guest
        group = self._get_group(filegroup, grtype="PosixGroup")
        posix_user = PosixUser.PosixUser(self.db)
        shell = self._get_shell(shell)
        if home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hardcoded path")
            disk_id, home = None, home[1:]
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)        

        ret = []
        ac = Factory.get('Account')(self.db)    
        # Find the names of the next <nr> of guest users
        for uname in self.bgu.find_new_guestusernames(nr):
            posix_user.clear()
            # Create the guest_users
            uid = posix_user.get_free_uid()
            posix_user.populate(uid, group.entity_id, gecos, shell, name=uname,
                                owner_type=owner_type,
                                owner_id=owner_id, np_type=np_type,
                                creator_id=operator.get_entity_id(),
                                expire_date=expire_date)            
            try:
                posix_user.write_db()
                for spread in cereconf.GUESTS_USER_SPREADS:
                    posix_user.add_spread(self.const.Spread(spread))
                homedir_id = posix_user.set_homedir(
                    disk_id=disk_id, home=home,
                    status=self.const.home_status_not_created)
                posix_user.set_home(self.const.spread_uio_nis_user, homedir_id)
                # For correct ordering of ChangeLog events, new users
                # should be signalled as "exported to" a certain system
                # before the new user's password is set.  Such systems are
                # flawed, and should be fixed.
                passwd = posix_user.make_passwd(uname)
                posix_user.set_password(passwd)
                # And, to write the new password to the database, we have
                # to .write_db() one more time...
                posix_user.write_db()
            except self.db.DatabaseError, m:
                raise CerebrumError, "Database error: %s" % m
            # Add guest_trait and set quarantine
            ac.clear()
            ac.find_by_name(uname)
            today = DateTime.today()
            ac.populate_trait(co.trait_guest_owner, target_id=None)
            #self.logger.debug("Set guest trait for %s" % uname)
            ac.add_entity_quarantine(co.quarantine_generell, operator,
                                     "Available guest user.", today.date) 
            #self.logger.debug("Set quarantine for %s" % uname)
            ac.write_db()
            ret.append((uname, uid))
        return "OK, created guest_users:\n %s " % self._pretty_print(ret)


    def user_request_guest_prompt_func(self, session, *args):
        all_args = list(args[:])
        if not all_args:
            return {'prompt': 'How many guest users?', 'default': '1'}
        nr_of_guests = int(all_args[0])
        all_args.pop(0)
        # try:
        #     nr_of_guests = int(all_args[0])
        #     all_args.pop(0)
        # except ValueError:
        #     all_args.pop(0)  # If not an integer. Ask again
        #     if not all_args:
        #         return {'prompt': 'How many guest users?', 'default': '1'}        
        # Date checking
        today = DateTime.today()
        default_date = today + DateTime.RelativeDateTime(days=cereconf.GUESTS_DEFAULT_PERIOD)
        max_date = today + DateTime.RelativeDateTime(days=cereconf.GUESTS_MAX_PERIOD)
        if not all_args:
            return {'prompt': 'Enter end date',
                    'default': default_date.date}
        # Don't give up until a correct date is entered
        # while self.not_good(all_args[0], today, max_date):
        #     all_args.pop(0)
        #     if not all_args:
        #         return {'prompt': 'Enter end date (YYYY-MM-DD)',
        #                 'default': default_date.date}    
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
            self.ba.can_request_guests(operator.get_entity_id(), groupname,
                                       query_run_any=True)
            owner = self._get_group(groupname)
        except Errors.NotFoundError:
            raise CerebrumError("No group with name %s" % groupname)
        try:
            user_list = self.bgu.request_guest_users(int(nr), end_date,
                                                         self.const.entity_group,
                                                         owner.entity_id)
            for uname, e_id, passwd in user_list:
                operator.store_state("new_account_passwd",
                                     {'account_id': entity_id, 'password': passwd})
            
            ret = "OK, reserved guest users:\n%s\n" % self._pretty_print(user_list)
            ret += "Please use misc list_passwords to print or view the passwords."
            return ret
        except bofhd_guestaccounts_utils.GuestAccountException, e:
            raise CerebrumError(str(e))
        
    
    # user release_guest [<guest> || <range>]+
    all_commands['user_release_guest'] = Command(
        ('user', 'release_guest'), SimpleString(help_ref='release_type'))              
    def user_release_guest(self, operator, *args):
        guests = []        
        if not args:
            raise CerebrumError("Usage: user release_guest [<guest> || <range>]+")
        # Each arg should be an guest account name or an interval 
        for arg in args:
            if '-' in arg:
                first, last = arg.split('-')
                first = int(first[5:])
                last = int(last[5:])
                for i in range(first, last+1):
                    guests.append('guest%s' % str(i).zfill(3))
            else:
                guests.append(arg)

        for guest in guests:
            # Fjern query_run_any=True når ting er klart
            try:
                owner_id = self.bgu.get_owner(guest)
                owner_group = self._get_group(owner_id, idtype='id')
                self.ba.can_release_guests(operator.get_entity_id(),
                                           owner_group.get_name(self.const.group_namespace),
                                           query_run_any=True)
                self.bgu.release_guest(guest, operator.get_entity_id())
            except Errors.NotFoundError:
                raise CerebrumError("Could not find guest user with name %s" % guest)
            except PermissionDenied:
                raise CerebrumError("No permission to release guest user %s" % guest)
            except bofhd_guestaccounts_utils.GuestAccountException, e:
                raise CerebrumError("Could not release guest user. %s" % str(e))

        return "OK, released guests:\n%s" % self._pretty_print(guests)

                    
    # user guests <owner>
    all_commands['user_guests'] = Command(
        ('user', 'guests'), GroupName(help_ref="guest_owner_group"))
    def user_guests(self, operator, groupname): 
        owner = self._get_group(groupname)
        try:
            tmp = self.bgu.list_guest_users(owner.entity_id)
        except:
            raise CerebrumError("Could not list guest users.")

        return "The following guest users is owned by %s:\n%s" % (
            groupname, self._pretty_print(tmp))


    all_commands['user_guests_status'] = Command(
        ('user', 'guests_status'))
    def user_guests_status(self, operator):
        return "%d guest users available." % self.bgu.nr_available_accounts()


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


    def _get_shell(self, shell):
        return self._get_constant(self.const.PosixShell, shell, "shell")


    def _get_constant(self, code_cls, code_str, code_type="value"):
        c = code_cls(code_str)
        try:
            int(c)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown %s: %s" % (code_type, code_str))
        return c


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


    def _get_disk(self, path, host_id=None, raise_not_found=True):
        disk = Factory.get('Disk')(self.db)
        try:
            if isinstance(path, str):
                disk.find_by_path(path, host_id)
            else:
                disk.find(path)
            return disk, disk.entity_id, None
        except Errors.NotFoundError:
            if raise_not_found:
                raise CerebrumError("Unknown disk: %s" % path)
            return disk, None, path


    def _pretty_print(self, guests):
        """Return a pretty string of the names in guestlist. If the
        list contains more than 2 consecutive names they should be
        written as an interval."""
    
        intervals = []
        int2name = {}

        if isinstance(guests[0], tuple):
            guestlist = [x[0] for x in guests]
        else:
            guestlist = guests
        guestlist.sort()    # sort the list before looking for ranges.
        for name in guestlist:
            nr = int(name[-3:])
            int2name[nr] = name
            if intervals and nr - intervals[-1][1] == 1:
                intervals[-1][1] = nr
            else:
                intervals.append([nr, nr])
    
        ret = []
        for i,j in intervals:
            if i == j:
                ret.append(int2name[i])
            else:
                ret.append('%s - %s' % (int2name[i], int2name[j]))
    
        return '\n'.join(ret)

# arch-tag: bddd54d2-6272-11da-906d-7a8b01ac279a
