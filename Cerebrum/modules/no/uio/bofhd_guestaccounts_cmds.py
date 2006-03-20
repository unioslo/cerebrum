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
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.no.uio.bofhd_guestaccounts_utils \
     import BofhdUtils, GuestAccountException    

class BofhdExtension(object):
    all_commands = {}
    Group_class = Factory.get('Group')

    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.util = server.util
        self.co = Factory.get('Constants')(self.db)
        self.bgu = BofhdUtils(server)
        self.ba = BofhdAuth(self.db)
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500, timeout=60*30)

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
            'release_type':
            ['release_type', 'Enter release type',
             "Enter a guest user name or a range of names, e.g., guest007 "
             "or guest010-040."],
            'guest_owner_group':
            ['guest_owner_group', 'Enter name of owner group']
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

    
    def time_in_interval(self, date, min_date=None, max_date=None):
        """Return date as an DateTime object if it is inside the
        interval defined by min_date and max_date (both DateTime
        objects).  Raise CerebrumError otherwise.

        """
        if isinstance(date, str):
            m = re.match('(\d{4})-(\d\d?)-(\d\d?)', date)
            if not m:
                raise CerebrumError, "Couldn't parse date (%s)" % date
            date = DateTime.Date(int(m.group(1)), int(m.group(2)),
                                 int(m.group(3)))
        if min_date and date < min_date:
            raise CerebrumError, ("Date can't be earlier than %s" %
                                  str(min_date).split()[0])
        if max_date and date > max_date:
            raise CerebrumError, ("Date can't be later than %s" %
                                  str(max_date).split()[0])
        return date

    def user_create_guest_prompt_func(self, session, *args):
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
        owner_type = self.co.entity_group
        owner_id = self.util.get_target(owner_group_name,
                                        default_lookup="group").entity_id
        np_type = self.co.account_guest
        group = self.util.get_target(filegroup, default_lookup="group")
        posix_user = PosixUser.PosixUser(self.db)
        shell = self._get_shell(shell)
        disk_id = self._get_disk(home)[1]
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)

        ret = []
        ac = Factory.get('Account')(self.db)
        # Find the names of the next <nr> of guest users
        for uname in self.bgu.find_new_guestusernames(int(nr)):
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
                homedir_id = posix_user.set_homedir(
                    disk_id=disk_id, status=self.co.home_status_not_created)
                posix_user.set_home(self.co.spread_uio_nis_user, homedir_id)
                # For correct ordering of ChangeLog events, new users
                # should be signalled as "exported to" a certain system
                # before the new user's password is set.  Such systems are
                # flawed, and should be fixed.
                for spread in cereconf.GUESTS_USER_SPREADS:
                    posix_user.add_spread(self.co.Spread(spread))
            except self.db.DatabaseError, m:
                raise CerebrumError, "Database error: %s" % m
            posix_user.populate_trait(self.co.trait_guest_owner, target_id=None)
            # The password must be set _after_ the trait, or else it
            # won't be stored using the 'PGP-guest_acc' method.
            posix_user.set_password(posix_user.make_passwd(uname))
            posix_user.write_db()
            ret.append((uname, uid))
        return "OK, created guest_users:\n %s " % self._pretty_print(ret)

    def user_request_guest_prompt_func(self, session, *args):
        all_args = list(args[:])
        if not all_args:
            return {'prompt': 'How many guest users?', 'default': '1'}
        nr_of_guests = int(all_args[0])
        all_args.pop(0)
        # Date checking
        default_date = DateTime.today() + \
                       DateTime.RelativeDateTime(days=cereconf.GUESTS_DEFAULT_PERIOD)
        if not all_args:
            return {'prompt': 'Enter end date',
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
        self.ba.can_request_guests(operator.get_entity_id(), groupname)
        owner = self.util.get_target(groupname, default_lookup="group")
        today = DateTime.today()
        end_date = self.time_in_interval(end_date, today,
            today + DateTime.RelativeDateTime(days=cereconf.GUESTS_MAX_PERIOD))
        try:
            user_list = self.bgu.request_guest_users(int(nr), end_date,
                                                     self.co.entity_group,
                                                     owner.entity_id,
                                                     operator.get_entity_id())
            for uname, e_id, passwd in user_list:
                operator.store_state("new_account_passwd",
                                     {'account_id': e_id,
                                      'password': passwd})

            ret = "OK, reserved guest users:\n%s\n" % self._pretty_print(user_list)
            ret += "Please use misc list_passwords to print or view the passwords."
            return ret
        except GuestAccountException, e:
            raise CerebrumError(str(e))

    # user release_guest [<guest> || <range>]+
    all_commands['user_release_guest'] = Command(
        ('user', 'release_guest'),
        SimpleString(help_ref='release_type', repeat=True))
    def user_release_guest(self, operator, *args):
        guests = []        
        if not args:
            raise CerebrumError("Usage: user release_guest [<guest> || <range>]+")
        # Each arg should be an guest account name or an interval 
        for arg in args:
            if '-' in arg:
                first, last = arg.split('-')
                prefix = first.rstrip('0123456789')
                first = int(first[len(prefix):])
                last = int(last)
                for i in range(first, last+1):
                    guests.append('%s%03d' % (prefix, i))
            else:
                guests.append(arg)

        for guest in guests:
            try:
                owner_id = self.bgu.get_owner(guest)
                owner_group = self.util.get_target(owner_id)
                self.ba.can_release_guests(operator.get_entity_id(),
                                           owner_group.group_name)
                self.bgu.release_guest(guest, operator.get_entity_id())
            except Errors.NotFoundError:
                raise CerebrumError("Could not find guest user with name %s" % guest)
            except PermissionDenied:
                raise CerebrumError("No permission to release guest user %s" % guest)
            except GuestAccountException, e:
                raise CerebrumError("Could not release guest user. %s" % str(e))

        return "OK, released guests:\n%s" % self._pretty_print(guests)

                    
    # user guests <owner>
    all_commands['user_guests'] = Command(
        ('user', 'guests'), GroupName(help_ref="guest_owner_group"))
    def user_guests(self, operator, groupname): 
        owner = self.util.get_target(groupname, default_lookup="group")
        users = self.bgu.list_guest_users(owner_id=owner.entity_id)
        if not users:
            return "No guest users are owned by %s" % groupname
        return "The following guest users is owned by %s:\n%s" % (
            groupname, self._pretty_print(users))


    all_commands['user_guests_status'] = Command(
        ('user', 'guests_status'))
    def user_guests_status(self, operator):
        return "%d guest users available." % self.bgu.num_available_accounts()


    def _get_shell(self, shell):
        return self._get_constant(self.co.PosixShell, shell, "shell")


    def _get_constant(self, code_cls, code_str, code_type="value"):
        c = code_cls(code_str)
        try:
            int(c)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown %s: %s" % (code_type, code_str))
        return c


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
