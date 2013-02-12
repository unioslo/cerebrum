# -*- coding: iso-8859-1 -*-
# Copyright 2013 University of Oslo, Norway
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
"""This is the bofhd functionality that is available for the TSD project.

Many of the commands are simply copied from UiO's command base and renamed for
the project, while other commands are changed to comply with the project.

Idealistically, we would move the basic commands into a super class, so we could
instead use inheritance, but unfortunately we don't have that much time.

Note that there are different bofhd extensions. One is for administrative tasks,
i.e. the superusers in TSD, and one is for the end users. End users are
communicating with bofhd through a web site, so that bofhd should only be
reachable from the web host.

"""

import os, traceback
import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
#from Cerebrum.modules import Host
from Cerebrum.modules import PasswordChecker
from Cerebrum.modules.bofhd import cmd_param as cmd
from Cerebrum.modules.dns.bofhd_dns_utils import DnsBofhdUtils
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import AAAARecord
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import IPv6Number
from Cerebrum.modules.dns import Subnet
from Cerebrum.modules.dns.Subnet import SubnetError
from Cerebrum.modules.dns.IPUtils import IPCalc
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import Utils
from Cerebrum.modules.hostpolicy.PolicyComponent import PolicyComponent
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.modules import dns
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode

from Cerebrum.modules.tsd.bofhd_auth import TSDBofhdAuth
from Cerebrum.modules.tsd import bofhd_help

def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

def date_to_string(date):
    """Takes a DateTime-object and formats a standard ISO-datestring
    from it.

    Custom-made for our purposes, since the standard XMLRPC-libraries
    restrict formatting to years after 1899, and we see years prior to
    that.

    """
    if not date:
        return "<not set>"
    return "%04i-%02i-%02i" % (date.year, date.month, date.day)

class TSDBofhdExtension(BofhdCommandBase):
    """Superclass for common functionality for TSD's bofhd servers."""

    def __init__(self, server, default_zone='tsdutv.usit.no.'):
        super(TSDBofhdExtension, self).__init__(server)
        self.ba = TSDBofhdAuth(self.db)
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
        for key, cmd in super(TSDBofhdExtension, self).all_commands.iteritems():
            if not self.all_commands.has_key(key):
                self.all_commands[key] = cmd

    def get_help_strings(self):
        """Return all help messages for TSD."""
        return (bofhd_help.group_help, bofhd_help.command_help,
                bofhd_help.arg_help)

class AdministrationBofhdExtension(TSDBofhdExtension):
    """The bofhd commands for the TSD project's system administrators.
    
    Here you have the commands that should be availble for the superusers
    
    """

    # Commands that should be publicised for an operator, e.g. in jbofh:
    all_commands = {}

    # Commands that are available, but not publicised, as they are normally
    # called through other systems, e.g. Brukerinfo. It should NOT be used as a
    # security feature - thus you have security by obscurity.
    hidden_commands = {}

    # Commands that should be copied from UiO's BofhdExtension. We don't want to
    # copy all of the commands for TSD, but tweak them a bit first.
    copy_commands = (
        # Person
        'person_create', 'person_find', 'person_info', 'person_accounts',
        'person_set_name', 'person_set_bdate', 'person_set_id',
        # User
        'user_history', 'user_info', 'user_find', 'user_set_expire',
        # Group
        'group_info', 'group_list', 'group_list_expanded', 'group_memberships',
        'group_delete', 'group_set_description', 'group_set_expire',
        'group_search', 
        # Quarantine
        'quarantine_disable', 'quarantine_list', 'quarantine_remove',
        'quarantine_set', 'quarantine_show',
        # OU
        'ou_search', 'ou_info', 'ou_tree',
        # TODO: find out if the remaining methods should be imported too:
        #
        # Access:
        #'access_disk', 'access_group', 'access_ou', 'access_user',
        #'access_global_group', 'access_global_ou', '_list_access',
        #'access_grant', 'access_revoke', '_manipulate_access',
        #'_get_access_id', '_validate_access', '_get_access_id_disk',
        #'_validate_access_disk', '_get_access_id_group', '_validate_access_group',
        #'_get_access_id_global_group', '_validate_access_global_group',
        #'_get_access_id_ou', '_validate_access_ou', '_get_access_id_global_ou',
        #'_validate_access_global_ou', 'access_list_opsets', 'access_show_opset',
        #'access_list', '_get_auth_op_target', '_grant_auth', '_revoke_auth',
        #'_get_opset',
        #
        # Misc
        'misc_affiliations', 'misc_clear_passwords', 'misc_verify_password',
        # Trait
        'trait_info', 'trait_list', 'trait_remove', 'trait_set',
        # Spread
        'spread_list', 'spread_add', 'spread_remove',
        # Entity
        'entity_history',
        # Helper functions
        '_find_persons', '_format_ou_name', '_get_person', '_get_disk',
        '_map_person_id', '_entity_info', 'num2str', '_get_affiliationid',
        '_get_affiliation_statusid', '_parse_date', '_today', 
        '_format_changelog_entry', '_format_from_cl', '_get_name_from_object',
        '_get_constant', '_is_yes', '_remove_auth_target', '_remove_auth_role',
        '_get_cached_passwords', '_parse_date_from_to',
        '_convert_ticks_to_timestamp', '_fetch_member_names',
        )

    def __new__(cls, *arg, **karg):
        """Hackish override to copy in methods from UiO's bofhd.

        A better fix would be to split bofhd_uio_cmds.py into separate classes.

        """
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
             UiOBofhdExtension
        non_all_cmds = ('num2str', 'user_set_owner_prompt_func',)
        for func in cls.copy_commands:
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in non_all_cmds:
                cls.all_commands[func] = UiOBofhdExtension.all_commands[func]
        x = object.__new__(cls)
        return x

    ##
    ## User commands

    # user_create_prompt_func_helper
    # TODO: need to remove unwanted functionality, e.g. affiliations
    def _user_create_prompt_func_helper(self, ac_type, session, *args):
        """A prompt_func on the command level should return

            {'prompt': message_string, 'map': dict_mapping}

        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list.

        """
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
                    raise CerebrumError("No persons matched")
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
                return {'prompt': "Shell", 'default': 'bash'}
            shell = all_args.pop(0)
            if not all_args:
                return {'prompt': 'E-mail spread', 'help_ref': 'string_spread'}
            email_spread = all_args.pop(0)
        if not all_args:
            ret = {'prompt': "Username", 'last_arg': True}
            posix_user = Factory.get('PosixUser')(self.db)
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
    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('PosixUser', session, *args)

    # user create
    all_commands['user_create'] = cmd.Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=cmd.FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')
    def user_create(self, operator, *args):
        """Creating a new account."""

        # TODO: remove functionality not needed in TSD! This method is copied
        # from UiA, and needs to be modified

        if args[0].startswith('group:'):
            group_id, np_type, shell, email_spread, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = self._get_constant(self.const.Account, np_type,
                                         "account type")
        else:
            if len(args) == 6:
                idtype, person_id, affiliation, shell, email_spread, uname = args
            else:
                idtype, person_id, yes_no, affiliation, shell, email_spread, uname = args
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
            
        filegroup = 'ansatt'
        group = self._get_group(filegroup, grtype="PosixGroup")
        posix_user = Factory.get('PosixUser')(self.db)
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        path = '/hia/ravn/u4'
        disk_id, home = self._get_disk(path)[1:3]
        posix_user.clear()
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)

        posix_user.populate(uid, group.entity_id, gecos, shell, name=uname,
                            owner_type=owner_type, owner_id=owner_id, 
                            np_type=np_type, creator_id=operator.get_entity_id(),
                            expire_date=expire_date)
        try:
            posix_user.write_db()
            for spread in cereconf.BOFHD_NEW_USER_SPREADS:
                posix_user.add_spread(self.const.Spread(spread))
            homedir_id = posix_user.set_homedir(
                disk_id=disk_id, home=home,
                status=self.const.home_status_not_created)
            posix_user.set_home(self.const.spread_nis_user, homedir_id)
            # For correct ordering of ChangeLog events, new users
            # should be signalled as "exported to" a certain system
            # before the new user's password is set.  Such systems are
            # flawed, and should be fixed.
            passwd = posix_user.make_passwd(uname)
            posix_user.set_password(passwd)
            if email_spread:
                if not int(self.const.Spread(email_spread)) in \
                   [int(self.const.spread_exchange_account),
                    int(self.const.spread_hia_email)]:
                    raise CerebrumError, "Not an e-mail spread: %s!" % email_spread
            try:
                posix_user.add_spread(self.const.Spread(email_spread))
            except Errors.NotFoundError:
                raise CerebrumError, "No such spread %s" % spread                            
            # And, to write the new password to the database, we have
            # to .write_db() one more time...
            posix_user.write_db()
            if posix_user.owner_type == self.const.entity_person:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(posix_user, owner_id,
                                                   ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        self._meld_inn_i_server_gruppe(int(posix_user.entity_id), operator)
        self._add_radiusans_spread(int(posix_user.entity_id), operator)
        
        return "Ok, create %s" % {'uid': uid}

    # user password
    all_commands['user_set_password'] = cmd.Command(
        ('user', 'set_password'), cmd.AccountName(), cmd.AccountPassword(optional=True))
    def user_set_password(self, operator, accountname, password=None):
        """Set password for a user. Copied from UiO, but renamed for TSD."""
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)
        if password is None:
            password = account.make_passwd(accountname)
        else:
            # this is a bit complicated, but the point is that
            # superusers are allowed to *specify* passwords for other
            # users if cereconf.BOFHD_SU_CAN_SPECIFY_PASSWORDS=True
            # otherwise superusers may change passwords by assigning
            # automatic passwords only.
            if self.ba.is_superuser(operator.get_entity_id()):
                if (operator.get_entity_id() != account.entity_id and
                    not cereconf.BOFHD_SU_CAN_SPECIFY_PASSWORDS):
                    raise CerebrumError("Superuser cannot specify passwords "
                                        "for other users")
            elif operator.get_entity_id() != account.entity_id:
                raise CerebrumError("Cannot specify password for another user.")
        try:
            account.goodenough(account, password)
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError("Bad password: %s" % m)
        account.set_password(password)
        try:
            account.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        operator.store_state("user_passwd", {'account_id': int(account.entity_id),
                                             'password': password})
        # Remove "weak password" quarantine
        for r in account.get_entity_quarantine():
            if int(r['quarantine_type']) == self.const.quarantine_autopassord:
                account.delete_entity_quarantine(self.const.quarantine_autopassord)
            if int(r['quarantine_type']) == self.const.quarantine_svakt_passord:
                account.delete_entity_quarantine(self.const.quarantine_svakt_passord)
        if account.is_deleted():
            return "OK.  Warning: user is deleted"
        elif account.is_expired():
            return "OK.  Warning: user is expired"
        elif account.get_entity_quarantine(only_active=True):
            return "Warning: user has an active quarantine"
        return "Password altered. Please use misc list_password."

    # user password
    all_commands['user_set_otpkey'] = cmd.Command(
        ('user', 'set_otpkey'), cmd.AccountName())
    def user_set_otpkey(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_set_otpkey(operator.get_entity_id(), account)
        account.regenerate_otpkey()
        try:
            account.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        # TODO: put the key in the session?
        # Remove "weak password" quarantine
        if account.is_deleted():
            return "OK.  Warning: user is deleted"
        elif account.is_expired():
            return "OK.  Warning: user is expired"
        elif account.get_entity_quarantine(only_active=True):
            return "Warning: user has an active quarantine"
        return "OTP-key regenerated."

    ##
    ## Group commands

    # group add_member
    all_commands['group_add_member'] = cmd.Command(
        ("group", "add_member"),
        cmd.MemberType(), cmd.MemberName(), cmd.GroupName(), 
        perm_filter='can_alter_group')
    def group_add_member(self, operator, member_type, src_name, dest_group):
        """Generic method for adding an entity to a given group.

        @type operator: 
        @param operator:

        @type src_name: String
        @param src_name: The name/id of the entity to add as the member.

        @type dest_group: String
        @param dest_group: The name/id of the group the member should be added
            to.

        @type member_type: String or EntityTypeCode (CerebrumCode)
        @param member_type: The entity_type of the member.

        """
        if member_type in ("group", self.const.entity_group):
            src_entity = self._get_group(src_name)
        elif member_type in ("account", self.const.entity_account):
            src_entity = self._get_account(src_name)
        elif member_type in ("person", self.const.entity_person):
            try:
                src_entity = self.util.get_target(src_name,
                                                  restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
        else:
            raise CerebrumError('Unknown entity type: %s' % member_type)
        dest_group = self._get_group(dest_group)
        return self._group_add_entity(operator, src_entity, dest_group)

    def _group_add_entity(self, operator, src_entity, dest_group):
        """Helper method for adding a given entity to given group.

        @type operator:
        @param operator:

        @type src_entity: Entity
        @param src_entity: The entity to add as a member.

        @type dest_group: Group
        @param dest_group: The group the member should be added to.

        """
        if operator:
            self.ba.can_alter_group(operator.get_entity_id(), dest_group)
        src_name = self._get_entity_name(src_entity.entity_id,
                                         src_entity.entity_type)
        # Make the error message for the most common operator error more
        # friendly.  Don't treat this as an error, useful if the operator has
        # specified more than one entity.
        if dest_group.has_member(src_entity.entity_id):
            return "%s is already a member of %s" % (src_name, dest_group)
        # Make sure that the src_entity does not have dest_group as a member
        # already, to avoid a recursion at export
        if src_entity.entity_type == self.const.entity_group:
            for row in src_entity.search_members(member_id=dest_group.entity_id, 
                                                 member_type=self.const.entity_group, 
                                                 indirect_members=True,
                                                 member_filter_expired=False):
                if row['group_id'] == src_entity.entity_id:
                    return "Recursive memberships are not allowed (%s is member of %s)" % (dest_group, src_name)
        # This can still fail, e.g., if the entity is a member with a different
        # operation.
        try:
            dest_group.add_member(src_entity.entity_id)
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        # TODO: If using older versions of NIS, a user could only be a member of
        # 16 group. You might want to be warned about this - Or is this only
        # valid for UiO?
        return "OK, added %s to %s" % (src_name, dest_group)

    # group remove_member
    all_commands['group_remove_member'] = cmd.Command(
        ("group", "remove_member"),
        cmd.MemberType(), cmd.MemberName(), cmd.GroupName(), 
        perm_filter='can_alter_group')
    def group_remove_member(self, operator, member_type, src_name, dest_group):
        """Remove a member from a given group.

        @type operator: 
        @param operator:

        @type member_type: String or EntityTypeCode (CerebrumCode)
        @param member_type: The entity_type of the member.

        @type src_name: String
        @param src_name: The name/id of the entity to remove as member.

        @type dest_group: String
        @param dest_group: The name/id of the group the member should be removed
            from.

        """
        if member_type in ("group", self.const.entity_group):
            src_entity = self._get_group(src_name)
        elif member_type in ("account", self.const.entity_account):
            src_entity = self._get_account(src_name)
        elif member_type in ("person", self.const.entity_person):
            try:
                src_entity = self.util.get_target(src_name,
                                                  restrict_to=['Person'])
            except Errors.TooManyRowsError:
                raise CerebrumError("Unexpectedly found more than one person")
        else:
            raise CerebrumError('Unknown entity type: %s' % member_type)
        dest_group = self._get_group(dest_group)
        return self._group_remove_entity(operator, src_entity, dest_group)

    def _group_remove_entity(self, operator, member, group):
        """Helper method for removing a member from a group.

        @type operator:
        @param operator:

        @type member: Entity
        @param member: The member to remove

        @type group: Group
        @param group: The group to remove the member from.

        """
        self.ba.can_alter_group(operator.get_entity_id(), group)
        member_name = self._get_entity_name(member.entity_id,
                                            member.entity_type)
        if not group.has_member(member.entity_id):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        if member.entity_type == self.const.entity_account:
            try:
                pu = Utils.Factory.get('PosixUser')(self.db)
                pu.find(member.entity_id)
                if pu.gid_id == group.entity_id:
                    raise CerebrumError("Can't remove %s from primary group %s" %
                                        (member_name, group.group_name))
            except Errors.NotFoundError:
                pass
        try:
            group.remove_member(member.entity_id)
        except self.db.DatabaseError, m:
            raise CerebrumError("Database error: %s" % m)
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)

    ##
    ## Project commands


class EnduserBofhdExtension(TSDBofhdExtension):
    """The bofhd commands for the end users of TSD.

    End users are Project Administrators (PA), which should have full control of
    their project, and Project Members (PM) which have limited privileges.

    """

    all_commands = {}
    hidden_commands = {}


