# -*- coding: utf-8 -*-
#
# Copyright 2012-2018 University of Oslo, Norway
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
""" This is a bofhd module for guest functionality.

The guest commands in this module creates guest accounts.

Guests created by these bofhd-commands are non-personal, owned by a group. A
trait associates the guest with an existing personal account.
"""
import functools

from mx import DateTime

import cereconf
import guestconfig

from Cerebrum import Errors
from Cerebrum.Utils import NotSet
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (AccountName,
                                              Command,
                                              FormatSuggestion,
                                              GroupName,
                                              Integer,
                                              Parameter,
                                              PersonName)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.guest.bofhd_guest_auth import BofhdAuth
from Cerebrum.utils.sms import SMSSender
from Cerebrum.utils.username import suggest_usernames


def format_date(field):
    """ Date format for FormatSuggestion. """
    fmt = "yyyy-MM-dd"  # 10 characters wide
    return ":".join((field, "date", fmt))


class Mobile(Parameter):
    """ Mobile phone Parameter. """
    _type = 'mobilePhone'
    _help_ref = 'guest_mobile_number'


class BofhdExtension(BofhdCommonMethods):
    """ Guest commands. """

    hidden_commands = {}  # Not accessible through bofh
    all_commands = {}
    parent_commands = False
    authz = BofhdAuth

    @classmethod
    def get_help_strings(cls):
        """ Help strings for our commands and arguments. """
        return (HELP_GUEST_GROUP, HELP_GUEST_CMDS, HELP_GUEST_ARGS)

    def _get_owner_group(self):
        """ Get the group that should stand as the owner of the guest accounts.

        Note that this is different from the 'responsible' account for a guest,
        which is stored in a trait.

        The owner group will be created if it doesn't exist.

        @rtype:  Group
        @return: The owner Group object that was found/created.

        """
        gr = self.Group_class(self.db)
        try:
            gr.find_by_name(guestconfig.GUEST_OWNER_GROUP)
            return gr
        except Errors.NotFoundError:
            # Group does not exist, must create it
            pass
        self.logger.info('Creating guest owner group %r',
                         guestconfig.GUEST_OWNER_GROUP)
        ac = self.Account_class(self.db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        gr.populate(creator_id=ac.entity_id,
                    visibility=self.const.group_visibility_all,
                    name=guestconfig.GUEST_OWNER_GROUP,
                    description="The owner of all the guest accounts")
        gr.write_db()
        return gr

    def _get_guest_group(self, groupname, operator_id):
        """ Get the given guest group. Gets created it if it doesn't exist.

        @type  groupname: string
        @param groupname:
            The name of the group that the guest should be member of

        @type  operator_id: int
        @param operator_id:
            The entity ID of the bofh-operator, which is used as creator of the
            group if it needs to be created.

        @rtype:  Group
        @return: The Group object that was found/created.

        """
        if groupname not in guestconfig.GUEST_TYPES:
            raise CerebrumError('Given group not defined as a guest group')
        try:
            return self._get_group(groupname)
        except CerebrumError:
            # Mostlikely not created yet
            pass
        self.logger.info('Creating guest group %r', groupname)
        group = self.Group_class(self.db)
        group.populate(creator_id=operator_id,
                       name=groupname,
                       visibility=self.const.group_visibility_all,
                       description="For guest accounts")
        group.write_db()
        return group

    def _get_guests(self, responsible_id=NotSet, include_expired=True):
        """ Get a list of guest accounts that belongs to a given account.

        @type responsible: int
        @param responsible: The responsible's entity_id

        @type include_expired: bool
        @param include_expired:
            If True, all guests will be returned. If False, guests with a
            'guest_old' quarantine will be filtered from the results. Defaults
            to True.

        @rtype: list
        @return:
            A list of db-rows from ent.list_trait. The interesting keys are
            entity_id, target_id and strval.

        """
        ac = self.Account_class(self.db)
        all = ac.list_traits(code=self.const.trait_guest_owner,
                             target_id=responsible_id)
        if include_expired:
            return all
        # Get entity_ids for expired guests, and filter them out
        expired = [q['entity_id'] for q in
                   ac.list_entity_quarantines(
                       entity_types=self.const.entity_account,
                       quarantine_types=self.const.quarantine_guest_old,
                       only_active=True)]
        return filter(lambda a: a['entity_id'] not in expired, all)

    def _get_account_name(self, account_id):
        """ Simple lookup of C{Account.entity_id} -> C{Account.account_name}.

        @type  account_id: int
        @param account_id: The entity_id to look up

        @rtype: string
        @return: The account name

        """
        account = self.Account_class(self.db)
        account.find(account_id)
        return account.account_name

    def _get_guest_info(self, entity_id):
        """ Get info about a given guest user.

        @type  entity_id: int
        @param entity_id: The guest account entity_id

        @rtype: dict
        @return: A dictionary with relevant information about a guest user.
                 Keys: 'username': <string>, 'created': <DateTime>,
                       'expires': <DateTime>, 'name': <string>,
                       'responsible': <int>, 'status': <string>,
                       'contact': <string>'

        """
        account = self.Account_class(self.db)
        account.clear()
        account.find(entity_id)
        try:
            guest_name = account.get_trait(
                self.const.trait_guest_name)['strval']
            responsible_id = account.get_trait(
                self.const.trait_guest_owner)['target_id']
        except TypeError:
            self.logger.debug('Not a guest user: %s', account.account_name)
            raise CerebrumError('%s is not a guest user' %
                                account.account_name)
        # Get quarantine date
        try:
            end_date = account.get_entity_quarantine(
                self.const.quarantine_guest_old)[0]['start_date']
        except IndexError:
            self.logger.warn('No quarantine for guest user %s',
                             account.account_name)
            end_date = account.expire_date

        # Get contect info
        mobile = None
        try:
            mobile = account.get_contact_info(
                source=self.const.system_manual,
                type=self.const.contact_mobile_phone)[0]['contact_value']
        except IndexError:
            pass
        # Get account state
        status = 'active'
        if end_date < DateTime.now():
            status = 'expired'

        return {
            'username': account.account_name,
            'created': account.created_at,
            'expires': end_date,
            'name': guest_name,
            'responsible': self._get_account_name(responsible_id),
            'status': status,
            'contact': mobile,
        }

    #
    # guest create
    #
    all_commands['guest_create'] = Command(
        ('guest', 'create'),
        Integer(help_ref='guest_days'),
        PersonName(help_ref='guest_fname'),
        PersonName(help_ref='guest_lname'),
        GroupName(help_ref='guest_group_name',
                  default=guestconfig.GUEST_TYPES_DEFAULT),
        Mobile(help_ref='guest_mobile_number',
               optional=(not guestconfig.GUEST_REQUIRE_MOBILE)),
        AccountName(help_ref='guest_responsible', optional=True),
        fs=FormatSuggestion([
            ('Created user %s.', ('username',)),
            (('SMS sent to %s.'), ('sms_to',))
        ]),
        perm_filter='can_create_personal_guest')

    def guest_create(self, operator, days, fname, lname, groupname,
                     mobile=None, responsible=None):
        """Create and set up a new guest account."""
        self.ba.can_create_personal_guest(operator.get_entity_id())

        # input validation
        fname = fname.strip()
        lname = lname.strip()
        try:
            days = int(days)
        except ValueError:
            raise CerebrumError('The number of days must be an integer')
        if not (0 < days <= guestconfig.GUEST_MAX_DAYS):
            raise CerebrumError('Invalid number of days, must be in the '
                                'range 1-%d' % guestconfig.GUEST_MAX_DAYS)
        if (not fname) or len(fname) < 2:
            raise CerebrumError(
                'First name must be at least 2 characters long')
        if (not lname) or len(lname) < 1:
            raise CerebrumError(
                'Last name must be at least one character long')
        if len(fname) + len(lname) >= 512:
            raise CerebrumError('Full name must not exceed 512 characters')
        if guestconfig.GUEST_REQUIRE_MOBILE and not mobile:
            raise CerebrumError('Mobile phone number required')

        # TODO/TBD: Change to cereconf.SMS_ACCEPT_REGEX?
        if mobile and not (len(mobile) == 8 and mobile.isdigit()):
            raise CerebrumError(
                'Invalid phone number, must be 8 digits, no spaces')

        guest_group = self._get_guest_group(groupname,
                                            operator.get_entity_id())

        if responsible:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied('Only superuser can set responsible')
            ac = self._get_account(responsible)
            responsible = ac.entity_id
        else:
            responsible = operator.get_entity_id()

        end_date = DateTime.now() + days

        # Check the maximum number of guest accounts per user
        # TODO: or should we check per person instead?
        if not self.ba.is_superuser(operator.get_entity_id()):
            nr = len(tuple(self._get_guests(responsible,
                                            include_expired=False)))
            if nr >= guestconfig.GUEST_MAX_PER_PERSON:
                self.logger.debug("More than %d guests, stopped",
                                  guestconfig.GUEST_MAX_PER_PERSON)
                raise PermissionDenied('Not allowed to have more than '
                                       '%d active guests, you have %d' %
                                       (guestconfig.GUEST_MAX_PER_PERSON, nr))

        # Everything should now be okay, so we create the guest account
        ac = self._create_guest_account(responsible, end_date, fname, lname,
                                        mobile, guest_group)

        # An extra change log is required in the responsible's log
        ac._db.log_change(responsible, ac.clconst.guest_create, ac.entity_id,
                          change_params={'owner': responsible,
                                         'mobile': mobile,
                                         'name': '%s %s' % (fname, lname)},
                          change_by=operator.get_entity_id())

        # In case a superuser has set a specific account as the responsible,
        # the event should be logged for both operator and responsible:
        if operator.get_entity_id() != responsible:
            ac._db.log_change(operator.get_entity_id(), ac.clconst.guest_create,
                              ac.entity_id, change_params={
                                  'owner': responsible,
                                  'mobile': mobile,
                                  'name': '%s %s' % (fname, lname)},
                              change_by=operator.get_entity_id())

        # Set the password
        password = ac.make_passwd(ac.account_name)
        ac.set_password(password)
        ac.write_db()

        # Store password in session for misc_list_passwords
        operator.store_state("user_passwd", {'account_id': int(ac.entity_id),
                                             'password': password})
        ret = {'username': ac.account_name,
               'expire': end_date.strftime('%Y-%m-%d'), }

        if mobile:
            # TODO: Fix template
            msg = guestconfig.GUEST_WELCOME_SMS % {
                'username': ac.account_name,
                'expire': end_date.strftime('%Y-%m-%d'),
                'password': password}
            if getattr(cereconf, 'SMS_DISABLE', False):
                self.logger.info(
                    "SMS disabled in cereconf, would send to '%s'",
                    mobile)
            else:
                sms = SMSSender(logger=self.logger)
                if not sms(mobile, msg):
                    raise CerebrumError(
                        "Unable to send message to '%s', aborting" % mobile)
                ret['sms_to'] = mobile

        return ret

    def _create_guest_account(self, responsible_id, end_date, fname, lname,
                              mobile, guest_group):
        """ Helper method for creating a guest account.

        Note that this method does not validate any input, that must already
        have been done before calling this method...

        @rtype:  Account
        @return: The created guest account

        """
        owner_group = self._get_owner_group()
        # Get all settings for the given guest type:
        settings = guestconfig.GUEST_TYPES[guest_group.group_name]

        ac = self.Account_class(self.db)
        # create a validation callable (function)
        vfunc = functools.partial(ac.validate_new_uname,
                                  self.const.account_namespace)
        name = suggest_usernames(
            self.const.account_namespace,
            fname,
            lname,
            maxlen=guestconfig.GUEST_MAX_LENGTH_USERNAME,
            prefix=settings['prefix'],
            suffix='',
            validate_func=vfunc)[0]
        if settings['prefix'] and not name.startswith(settings['prefix']):
            # TODO/FIXME: Seems suggest_unames ditches the prefix setting if
            # there's not a lot of good usernames left with the given
            # constraints.
            # We could either fix suggest_uname (but that could lead to
            # complications with the imports), or we could try to mangle the
            # name and come up with new suggestions.
            raise Errors.RealityError("No potential usernames available")

        ac.populate(name=name,
                    owner_type=self.const.entity_group,
                    owner_id=owner_group.entity_id,
                    np_type=self.const.account_guest,
                    creator_id=responsible_id,
                    expire_date=None)
        ac.write_db()

        # Tag the account as a guest account:
        ac.populate_trait(code=self.const.trait_guest_owner,
                          target_id=responsible_id)

        # Save the guest's name:
        ac.populate_trait(code=self.const.trait_guest_name,
                          strval='%s %s' % (fname, lname))

        # Set the quarantine:
        ac.add_entity_quarantine(qtype=self.const.quarantine_guest_old,
                                 creator=responsible_id,
                                 # TBD: or should creator be bootstrap_account?
                                 description='Guest account auto-expire',
                                 start=end_date)

        # Add spreads
        for spr in settings.get('spreads', ()):
            try:
                spr = int(self.const.Spread(spr))
            except Errors.NotFoundError:
                self.logger.warn('Unknown guest spread: %r', spr)
                continue
            ac.add_spread(spr)

        # Add guest account to correct group
        guest_group.add_member(ac.entity_id)

        # Save the phone number
        if mobile:
            ac.add_contact_info(source=self.const.system_manual,
                                type=self.const.contact_mobile_phone,
                                value=mobile)
        ac.write_db()
        return ac

    #
    # guest remove <guest-name>
    #
    all_commands['guest_remove'] = Command(
        ("guest", "remove"),
        AccountName(help_ref='guest_account_name'),
        perm_filter='can_remove_personal_guest')

    def guest_remove(self, operator, username):
        """ Set a new expire-quarantine that starts now.

        The guest account will be blocked from export to any system.

        """
        account = self._get_account(username)
        self.ba.can_remove_personal_guest(operator.get_entity_id(),
                                          guest=account)

        # Deactivate the account (expedite quarantine) and adjust expire_date
        try:
            end_date = account.get_entity_quarantine(
                self.const.quarantine_guest_old)[0]['start_date']
            if end_date < DateTime.now():
                raise CerebrumError("Account '%s' is already deactivated" %
                                    account.account_name)
            account.delete_entity_quarantine(self.const.quarantine_guest_old)
        except IndexError:
            self.logger.warn('Guest %s didn\'t have expire quarantine, '
                             'deactivated anyway.', account.account_name)
        account.add_entity_quarantine(qtype=self.const.quarantine_guest_old,
                                      creator=operator.get_entity_id(),
                                      description='New guest account',
                                      start=DateTime.now())
        account.expire_date = DateTime.now()
        account.write_db()
        return 'Ok, %s quarantined, will be removed' % account.account_name

    #
    # guest info <guest-name>
    #
    all_commands['guest_info'] = Command(
        ("guest", "info"),
        AccountName(help_ref='guest_account_name'),
        perm_filter='can_view_personal_guest',
        fs=FormatSuggestion([
            ('Username:       %s\n'
             'Name:           %s\n'
             'Responsible:    %s\n'
             'Created on:     %s\n'
             'Expires on:     %s\n'
             'Status:         %s\n'
             'Contact:        %s', ('username', 'name', 'responsible',
                                    format_date('created'),
                                    format_date('expires'),
                                    'status', 'contact'))
        ])
    )

    def guest_info(self, operator, username):
        """ Print stored information about a guest account. """
        account = self._get_account(username)
        self.ba.can_view_personal_guest(operator.get_entity_id(),
                                        guest=account)
        return [self._get_guest_info(account.entity_id)]

    #
    # guest list [guest-name]
    #
    all_commands['guest_list'] = Command(
        ("guest", "list"),
        AccountName(help_ref='guest_responsible', optional=True),
        perm_filter='can_create_personal_guest',
        fs=FormatSuggestion([
            ('%-25s %-30s %-10s %-10s', ('username', 'name',
                                         format_date('created'),
                                         format_date('expires')))],
            hdr='%-25s %-30s %-10s %-10s' % ('Username', 'Name', 'Created',
                                             'Expires')
        ))

    def guest_list(self, operator, username=None):
        """ Return a list of guest accounts owned by an entity.

        Defaults to listing guests owned by operator, if no username is given.

        """
        self.ba.can_create_personal_guest(operator.get_entity_id())
        if not username:
            target_id = operator.get_entity_id()
        else:
            account = self._get_account(username)
            target_id = account.entity_id

        ret = []
        for row in self._get_guests(target_id):
            ret.append(self._get_guest_info(row['entity_id']))
        if not ret:
            raise CerebrumError("No guest accounts owned by the user")
        return ret

    #
    # guest list_all
    #
    all_commands['guest_list_all'] = Command(
        ("guest", "list_all"),
        fs=FormatSuggestion([
            ('%-25s %-30s %-15s %-10s %-10s', ('username', 'name',
                                               'responsible',
                                               format_date('created'),
                                               format_date('expires')))],
            hdr='%-25s %-30s %-15s %-10s %-10s' % ('Username', 'Name',
                                                   'Responsible', 'Created',
                                                   'End date')),
        perm_filter='is_superuser')

    def guest_list_all(self, operator):
        """ Return a list of all personal guest accounts in Cerebrum. """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('Only superuser can list all guests')
        ret = []
        for row in self._get_guests():
            try:
                ret.append(self._get_guest_info(row['entity_id']))
            except CerebrumError, e:
                print "Error: %s" % e
                continue
        if not ret:
            raise CerebrumError("Found no guest accounts.")
        return ret

    hidden_commands['guest_reset_password'] = Command(
        ('guest', 'reset_password'),
        AccountName(help_ref='guest_account_name'),
        fs=FormatSuggestion([
            ('New password for user %s, notified %s by SMS.', ('username',
                                                               'mobile', )),
        ]),
        perm_filter='can_reset_guest_password')

    def guest_reset_password(self, operator, username):
        """ Reset the password of a guest account.

        :param BofhdSession operator: The operator
        :param string username: The username of the guest account

        :return dict: A dictionary with keys 'username' and 'mobile'

        """
        account = self._get_account(username)
        self.ba.can_reset_guest_password(operator.get_entity_id(),
                                         guest=account)
        operator_name = self._get_account_name(operator.get_entity_id())

        try:
            mobile = account.get_contact_info(
                source=self.const.system_manual,
                type=self.const.contact_mobile_phone)[0]['contact_value']
        except (IndexError, KeyError):
            raise CerebrumError("No contact info registered for %s" %
                                account.account_name)

        password = account.make_passwd(account.account_name)
        account.set_password(password)
        account.write_db()

        # Store password in session for misc_list_passwords
        operator.store_state("user_passwd",
                             {'account_id': int(account.entity_id),
                              'password': password})

        msg = guestconfig.GUEST_PASSWORD_SMS % {
            'changeby': operator_name,
            'username': account.account_name,
            'password': password}
        if getattr(cereconf, 'SMS_DISABLE', False):
            self.logger.info("SMS disabled in cereconf, would send"
                             " to %r", mobile)
        else:
            sms = SMSSender(logger=self.logger)
            if not sms(mobile, msg):
                raise CerebrumError(
                    "Unable to send SMS to registered number %r" % mobile)

        return {'username': account.account_name,
                'mobile': mobile}


HELP_GUEST_GROUP = {
    'guest': "Commands for handling guest users",
}

HELP_GUEST_CMDS = {
    'guest': {
        'guest_create':
            'Create a new guest user',
        'guest_remove':
            'Deactivate a guest user',
        'guest_info':
            'View information about a guest user',
        'guest_list':
            'List out all guest users for a given owner',
        'guest_list_all':
            'List out all guest users',
        'guest_reset_password':
            'Reset the password of a guest user, and nootify by SMS',
    },
}

HELP_GUEST_ARGS = {
    'guest_days':
        ['days', 'Enter number of days',
         'Enter the number of days the guest user should be active'],
    'guest_fname':
        ['given_name', "Enter guest's given name",
         "Enter the guest's first and middle name"],
    'guest_lname':
        ['family_name', "Enter guest's family name",
         "Enter the guest's surname"],
    'guest_responsible':
        ['responsible', "Enter the responsible user",
         "Enter the user that will be set as the responsible for the guest"],
    'guest_group_name':
        ['group', 'Enter group name',
         "Enter the group the guest should belong to"],
    'guest_mobile_number':
        ['mobile', 'Enter mobile number',
         "Enter the guest's mobile number, where the "
         "username and password will be sent"],
    'guest_account_name':
        ['username', 'Enter username',
         'The name of a guest user account']
}
