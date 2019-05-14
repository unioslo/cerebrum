# -*- coding: iso-8859-1 -*-

# Copyright 2002-2011 University of Oslo, Norway
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

from mx import DateTime

import cereconf
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum.Utils import Factory 
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.no.uit.bofhd_guestaccounts_utils \
     import BofhdUtils, GuestAccountException    


class BofhdExtension(BofhdCommandBase):
    all_commands = {}

    copy_commands = (
        #
        # copy relevant helper-functions
        #
        '_get_disk', '_get_shell', '_get_constant',
        '_parse_date_from_to', '_parse_date', '_today'
        )


    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uit_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uit.bofhd_uit_cmds import BofhdExtension as \
             UiTBofhdExtension

        non_all_cmds = ('num2str', 'user_set_owner_prompt_func',
                        'user_create_basic_prompt_func',)
        for func in BofhdExtension.copy_commands:
            setattr(cls, func, UiTBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in non_all_cmds:
                BofhdExtension.all_commands[func] = UiTBofhdExtension.all_commands[func]
        x = object.__new__(cls)
        return x


    def __init__(self, server):
        super(BofhdExtension, self).__init__(server)
        
        self.util = server.util
        self.bgu = BofhdUtils(server)
        self.ba = BofhdAuth(self.db)
    # end __init__


    def get_help_strings(self):
        group_help = {}

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'user': {
            'user_create_guest': 'Create a number of guest users for a certain time',
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
            ['guest_owner_group', 'Enter name of owner group'],
            'nr_guests':
            ['nr_guests', 'Enter number of guests'],
            'comment':
            ['comment', 'Enter comment']
            }
        return (group_help, command_help, arg_help)


    def user_create_guest_prompt_func(self, session, *args):
        all_args = list(args[:])
        # get number of new guest users
        if not all_args:
            return {'prompt': 'How many guest users?', 'default': '1'}
        try:
            int(all_args[0])
            all_args.pop(0)
        except ValueError:
            raise CerebrumError("Not a number: %s" % all_args[0])
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
            return {'prompt': "Disk", 'help_ref': 'disk'}
        disk = all_args.pop(0)
        # get prefix
        if not all_args:
            return {'prompt': "Name prefix",
                    'default': cereconf.GUESTS_PREFIX[-1], 
                    'last_arg': True}
        return {'last_arg': True}


    # user create_guest <nr> <group_id> <filegroup> <shell> <disk>
    all_commands['user_create_guest'] = Command(
        ('user', 'create_guest'), prompt_func=user_create_guest_prompt_func,
        perm_filter='can_create_guests')
    def user_create_guest(self, operator, *args):
        "Create <nr> new guest users"
        nr, owner_group_name, filegroup, shell, home, prefix = args
        owner_type = self.const.entity_group
        owner_id = self.util.get_target(owner_group_name,
                                        default_lookup="group").entity_id
        np_type = self.const.account_uit_guest
        group = self.util.get_target(filegroup, default_lookup="group")
        posix_user = Factory.get('PosixUser')(self.db)
        shell = self._get_shell(shell)
        disk_id, home = self._get_disk(home)[1:3]
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)

        ret = []
        # Find the names of the next <nr> of guest users
        for uname in self.bgu.find_new_guestusernames(int(nr), prefix=prefix):
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
                # For correct ordering of ChangeLog events, new users
                # should be signalled as "exported to" a certain system
                # before the new user's password is set.  Such systems are
                # flawed, and should be fixed.
                for spread in cereconf.GUESTS_USER_SPREADS:
                    posix_user.add_spread(self.const.Spread(spread))
                homedir_id = posix_user.set_homedir(
                    disk_id=disk_id, home=home,
                    status=self.const.home_status_not_created)
                posix_user.set_home(self.const.spread_uit_nis_user, homedir_id)
            except self.db.DatabaseError, m:
                raise CerebrumError, "Database error: %s" % m
            self.bgu.update_group_memberships(posix_user.entity_id)
            posix_user.populate_trait(self.const.trait_uit_guest_owner, target_id=None)
            # The password must be set _after_ the trait, or else it
            # won't be stored using the 'PGP-guest_acc' method.
            posix_user.set_password(posix_user.make_passwd(uname))
            posix_user.write_db()
            ret.append(uname)
        return "OK, created guest_users:\n %s " % self._pretty_print(ret)


    # user request_guest <nr> <to_from> <entity_name>
    all_commands['user_request_guest'] = Command(
        ('user', 'request_guest'),
        Integer(default="1", help_ref="nr_guests"),
        SimpleString(help_ref="string_from_to"),
        GroupName(help_ref="guest_owner_group"),
        SimpleString(help_ref="comment"),
        perm_filter='can_request_guests')
    def user_request_guest(self, operator, nr, date, groupname, comment):
        # date checking
        start_date, end_date = self._parse_date_from_to(date)        
        today = DateTime.today()
        if start_date < today:
            raise CerebrumError("Start date shouldn't be in the past")
        # end_date in allowed interval?
        if end_date < start_date:
            raise CerebrumError("End date can't be earlier than start_date")
        max_date = start_date + DateTime.RelativeDateTime(days=cereconf.GUESTS_MAX_PERIOD)
        if end_date > max_date:
            raise CerebrumError("End date can't be later than %s" % max_date.date)
        if not nr.isdigit():
            raise CerebrumError("'Number of accounts' requested must be a number;"
                                " '%s' isn't." % nr)

        try:
            self.ba.can_request_guests(operator.get_entity_id(), groupname)
        except Errors.NotFoundError:
            raise CerebrumError, "Group '%s' not found" % groupname
        owner = self.util.get_target(groupname, default_lookup="group")
        try:
            user_list = self.bgu.request_guest_users(int(nr), end_date, comment,
                                                     owner.entity_id,
                                                     operator.get_entity_id())
            for uname, comment, e_id, passwd in user_list:
                operator.store_state("new_account_passwd",
                                     {'account_id': e_id,
                                      'password': passwd})
        
            ret = "OK, reserved guest users:\n%s\n" % \
                  self._pretty_print([x[0] for x in user_list])
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
        users = self.bgu.list_guest_users(owner_id=owner.entity_id,
                                          include_comment=True,
                                          include_date=True)
        if not users:
            return "No guest users are owned by %s" % groupname
        if len(users) == 1:
            verb = 'user is'
            noun = 'Guest user'
        else:
            verb = 'users are'
            noun = 'Guest users'
        return ("The following guest %s owned by %s:\n%s\n%s" %
                (verb, groupname,
                 "%-12s   %-12s  %s" % (noun, "End date", "Comment"),
                 self._pretty_print(users, include_date=True,
                                    include_comment=True)))


    all_commands['user_guests_status'] = Command(
        ('user', 'guests_status'), SimpleString(optional=True))
    def user_guests_status(self, operator, *args):
        ret = ""
        if args and args[0] == "verbose" and self.ba.is_superuser(
            operator.get_entity_id()):
            tmp = self.bgu.list_guests_info()
            # Find status for all guests
            ret = "%-12s   %s:\n%s\n" % (
                "Guest users", "Status",
                self._pretty_print(tmp, include_comment=True))
            ret += "%d allocated guest users.\n" % len(
                [1 for x in tmp if x[2].startswith("allocated")])
            ret += "%d guest users in release_quarantine.\n" % len(
                [1 for x in tmp if x[2].startswith("in release_quarantine")])
        ret += "%d guest users available." % self.bgu.num_available_accounts()
        return ret


    def _pretty_print(self, guests, include_comment=False, include_date=False):
        """Return a pretty string of the names in guestlist. If the
        list contains more than 2 consecutive names they are written
        as an interval. If comment or date in included they must be
        equal within an interval.
        guests is either a list of guest names or a list of lists,
        where the inner lists are on the form [username, end_date,
        comment].

        """

        guests.sort()
        prev = -2
        prev_comment = None
        prev_date = None
        intervals = []
        for guest in guests:
            # Handle simple list of guest user names
            if not type(guest) is list:
                guest = [guest, None, None]
            num = int(guest[0][-3:])
            if intervals and num - prev == 1 and guest[1] == prev_date \
                   and guest[2] == prev_comment:
                intervals[-1][1] = guest
            else:
                intervals.append([guest, guest])
            prev = num
            prev_date = guest[1]
            prev_comment = guest[2]

        ret = []
        for i, j in intervals:
            if i == j:
                tmp = '%-12s   ' % i[0]
                if include_date:
                    tmp += '%-12s  ' % i[1]
                if include_comment:
                    tmp += '%s' % i[2]
            else:
                tmp = '%-8s-%s  ' % (i[0], j[0][-3:])
                if include_date:
                    tmp += ' %-12s  ' % i[1]
                if include_comment:
                    tmp += ' %s' % i[2]
            ret.append(tmp)
        return '\n'.join(ret)

