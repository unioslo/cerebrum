# -*- coding: utf-8 -*-
#
# Copyright 2012-2024 University of Oslo, Norway
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
"""
This is a bofhd module for managing personal guests.

The guest commands in this module creates guest accounts.

Guests created by these bofhd-commands are non-personal, owned by a group.
A trait associates the guest with an existing personal account.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import functools
import logging

import cereconf
import guestconfig

from Cerebrum import Errors
from Cerebrum.Utils import NotSet
from Cerebrum.group.template import GroupTemplate
from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.utils import date_compat
from Cerebrum.utils.sms import SMSSender
from Cerebrum.utils.username import suggest_usernames

from .bofhd_guest_auth import BofhdGuestAuth

logger = logging.getLogger(__name__)


def format_date(field):
    """ Date format for FormatSuggestion. """
    fmt = "yyyy-MM-dd"  # 10 characters wide
    return ":".join((field, "date", fmt))


class Mobile(cmd_param.Parameter):
    """ Mobile phone Parameter. """
    _type = "mobilePhone"
    _help_ref = "guest_mobile_number"


class GuestAccountName(cmd_param.AccountName):
    _help_ref = "guest_account_name"


class GuestOwner(cmd_param.AccountName):
    _help_ref = "guest_responsible"


GUEST_OWNER_GROUP_TEMPLATE = GroupTemplate(
    group_name=guestconfig.GUEST_OWNER_GROUP,
    group_description="The owner of all the guest accounts",
    group_type="internal-group",
    group_visibility="A",
    conflict=GroupTemplate.CONFLICT_UPDATE,
)


def _get_guest_type_template(guest_type):
    """ Get a guest type group template. """
    if guest_type not in guestconfig.GUEST_TYPES:
        raise CerebrumError("Given group not defined as a guest group")
    return GroupTemplate(
        group_name=guest_type,
        group_description="For guest accounts",
        group_type="internal-group",
        group_visibility="A",
        conflict=GroupTemplate.CONFLICT_IGNORE,  # for historical reasons
    )


class BofhdGuestCommands(BofhdCommonMethods):
    """ Guest commands. """

    hidden_commands = {}  # Not accessible through bofh
    all_commands = {}
    parent_commands = False
    authz = BofhdGuestAuth

    @classmethod
    def get_help_strings(cls):
        """ Help strings for our commands and arguments. """
        return (HELP_GUEST_GROUP, HELP_GUEST_CMDS, HELP_GUEST_ARGS)

    def _get_owner_group(self):
        """
        Get the group that should stand as the owner of all guest accounts.

        :returns: a group that should be used as the owner for guest accounts
        """
        return GUEST_OWNER_GROUP_TEMPLATE(self.db)

    def _get_guest_group(self, guest_type, operator_id):
        """
        Get the group for a given *guest type*.

        :param str guest_type: one of the group types from guestconfig
        :param int operator_id: entity id of the current bofh-operator.

        :returns: the group object that was found/created.
        """
        group_template = _get_guest_type_template(guest_type)
        return group_template(self.db, creator_id=operator_id)

    def _get_guests(self, responsible_id=NotSet, include_expired=True):
        """ Get guest accounts that belongs to a given account.

        :param int responsible: Filter list by guest owner (sponsor) entity id
        :param bool include_expired:
            If expired (quarantined) guests should be included in results.
            Defaults to True.

        :returns set: account ids of matching guest accounts
        """
        ac = self.Account_class(self.db)
        all_guests = set(
            row['entity_id']
            for row in ac.list_traits(code=self.const.trait_guest_owner,
                                      target_id=responsible_id)
        )
        if include_expired:
            return all_guests

        expired_ids = set(
            row['entity_id']
            for row in ac.list_entity_quarantines(
                entity_types=self.const.entity_account,
                quarantine_types=self.const.quarantine_guest_old,
                only_active=True,
            )
        )
        return (all_guests - expired_ids)

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

        :rtype: dict
        :returns dict:
            A mapping with relevant information about a guest user:

            - 'username': <string>
            - 'responsible': <str>
            - 'name': <string>,
            - 'contact': <string>'
            - 'created': <datetime>
            - 'expires': <date>
            - 'status': <string>

        """
        account = self.Account_class(self.db)
        account.find(entity_id)
        try:
            guest_name = account.get_trait(
                self.const.trait_guest_name)['strval']
            responsible_id = account.get_trait(
                self.const.trait_guest_owner)['target_id']
        except TypeError:
            logger.warning('Not a guest user: %s (%d)',
                           account.account_name, account.entity_id)
            raise CerebrumError('%s is not a guest user'
                                % repr(account.account_name))

        # Get quarantine date
        try:
            end_date = date_compat.get_date(
                account.get_entity_quarantine(
                    account.const.quarantine_guest_old)[0]['start_date'])
        except IndexError:
            logger.warning("No quarantine for guest account %s (%d)",
                           account.account_name, account.entity_id)
            end_date = date_compat.get_date(account.expire_date)

        # Get contact info
        try:
            mobile = account.get_contact_info(
                source=self.const.system_manual,
                type=self.const.contact_mobile_phone)[0]['contact_value']
        except IndexError:
            mobile = None

        # Get account state
        if end_date and end_date < datetime.date.today():
            status = 'expired'
        else:
            status = 'active'

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
    all_commands['guest_create'] = cmd_param.Command(
        ('guest', 'create'),
        cmd_param.Integer(help_ref='guest_days'),
        cmd_param.PersonName(help_ref='guest_fname'),
        cmd_param.PersonName(help_ref='guest_lname'),
        cmd_param.GroupName(help_ref='guest_group_name',
                            default=guestconfig.GUEST_TYPES_DEFAULT),
        Mobile(help_ref='guest_mobile_number',
               optional=(not guestconfig.GUEST_REQUIRE_MOBILE)),
        GuestOwner(optional=True),
        fs=cmd_param.FormatSuggestion([
            ('Created user %s.', ('username',)),
            (('SMS sent to %s.'), ('sms_to',))
        ]),
        perm_filter='can_create_personal_guest',
    )

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

        # TODO: Maybe this check should be in can_create_personal_guest()?
        if responsible:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied('Only superuser can set responsible')
            ac = self._get_account(responsible)
            responsible = ac.entity_id
        else:
            responsible = operator.get_entity_id()

        end_date = datetime.date.today() + datetime.timedelta(days=days)

        # Check the maximum number of guest accounts per user
        #
        # TODO: There's a mismatch here in how guests are registered, and how
        # we end up validating max number of guests.  We should ideally change
        # the guest_owner trait to actually be the *person* who registers the
        # geust, and limit the number of guests per person rather than account.
        #
        # Also, this should probably be moved to can_create_personal_guest()
        if not self.ba.is_superuser(operator.get_entity_id()):
            nr = len(self._get_guests(responsible, include_expired=False))
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
            ac._db.log_change(
                operator.get_entity_id(),
                ac.clconst.guest_create,
                ac.entity_id,
                change_params={
                    'owner': responsible,
                    'mobile': mobile,
                    'name': '%s %s' % (fname, lname),
                },
                change_by=operator.get_entity_id(),
            )

        # Set the password
        password = ac.make_passwd(ac.account_name)
        ac.set_password(password)
        ac.write_db()

        # Store password in session for misc_list_passwords
        operator.store_state("user_passwd", {'account_id': int(ac.entity_id),
                                             'password': password})
        ret = {
            'username': ac.account_name,
            'expire': end_date.strftime('%Y-%m-%d'),
        }
        if mobile:
            # TODO: Fix template
            msg = guestconfig.GUEST_WELCOME_SMS % {
                'username': ac.account_name,
                'expire': end_date.strftime('%Y-%m-%d'),
                'password': password,
            }
            if getattr(cereconf, 'SMS_DISABLE', False):
                logger.info("SMS disabled in cereconf, would send to %s",
                            repr(mobile))
            else:
                sms = SMSSender()
                if not sms(mobile, msg):
                    raise CerebrumError(
                        "Unable to send message to %s, aborting"
                        % repr(mobile))
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
            fname,
            lname,
            maxlen=guestconfig.GUEST_MAX_LENGTH_USERNAME,
            prefix=settings['prefix'],
            suffix='',
            validate_func=vfunc,
        )[0]
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
                logger.warn('Unknown guest spread: %s', repr(spr))
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
    all_commands['guest_remove'] = cmd_param.Command(
        ("guest", "remove"),
        GuestAccountName(),
        perm_filter='can_remove_personal_guest',
    )

    def guest_remove(self, operator, username):
        """ Set a new expire-quarantine that starts now.

        The guest account will be blocked from export to any system.

        """
        account = self._get_account(username)
        self.ba.can_remove_personal_guest(operator.get_entity_id(),
                                          guest=account)

        today = datetime.date.today()
        # Deactivate the account (expedite quarantine) and adjust expire_date
        try:
            end_date = date_compat.get_date(
                account.get_entity_quarantine(
                    self.const.quarantine_guest_old)[0]['start_date'])
            if end_date and end_date < today:
                raise CerebrumError("Account '%s' is already deactivated"
                                    % account.account_name)
            account.delete_entity_quarantine(self.const.quarantine_guest_old)
        except IndexError:
            logger.warning(
                "Guest %s didn't have expire quarantine, deactivated anyway",
                account.account_name)
        account.add_entity_quarantine(qtype=self.const.quarantine_guest_old,
                                      creator=operator.get_entity_id(),
                                      description='New guest account',
                                      start=today)
        account.expire_date = today
        account.write_db()
        return 'Ok, %s quarantined, will be removed' % (account.account_name,)

    #
    # guest info <guest-name>
    #
    all_commands['guest_info'] = cmd_param.Command(
        ("guest", "info"),
        GuestAccountName(),
        fs=cmd_param.FormatSuggestion([
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
        ]),
        perm_filter='can_view_personal_guest',
    )

    def guest_info(self, operator, username):
        """ Print stored information about a guest account. """
        account = self._get_account(username)
        self.ba.can_view_personal_guest(operator.get_entity_id(),
                                        guest=account)
        # No reason this should be a list, but we can't change this without
        # fixing WOFH
        return [self._get_guest_info(account.entity_id)]

    #
    # guest list [guest-name]
    #
    all_commands['guest_list'] = cmd_param.Command(
        ("guest", "list"),
        GuestOwner(optional=True),
        fs=cmd_param.get_format_suggestion_table(
            ("username", "Username", 25, "s", True),
            ("name", "Name", 30, "s", True),
            (format_date("created"), "Created", 10, "s", True),
            (format_date("expires"), "Expires", 10, "s", True),
        ),
        perm_filter='can_create_personal_guest',
    )

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
        for entity_id in sorted(self._get_guests(target_id)):
            ret.append(self._get_guest_info(entity_id))
        if not ret:
            raise CerebrumError("No guest accounts owned by the user")
        return ret

    #
    # guest list_all
    #
    all_commands['guest_list_all'] = cmd_param.Command(
        ("guest", "list_all"),
        fs=cmd_param.get_format_suggestion_table(
            ("username", "Username", 25, "s", True),
            ("name", "Name", 30, "s", True),
            ("responsible", "Responsible", 15, "s", True),
            (format_date("created"), "Created", 10, "s", True),
            (format_date("expires"), "Expires", 10, "s", True),
        ),
        perm_filter='is_superuser',
    )

    def guest_list_all(self, operator):
        """ Return a list of all personal guest accounts in Cerebrum. """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('Only superuser can list all guests')
        ret = []
        for entity_id in sorted(self._get_guests()):
            try:
                ret.append(self._get_guest_info(entity_id))
            except CerebrumError:
                logger.error("unable to get guest info on entity_id=%s",
                             repr(entity_id), exc_info=True)
                continue
        if not ret:
            raise CerebrumError("Found no guest accounts.")
        return ret

    hidden_commands['guest_reset_password'] = cmd_param.Command(
        ('guest', 'reset_password'),
        GuestAccountName(),
        fs=cmd_param.FormatSuggestion([
            ('New password for user %s, notified %s by SMS.',
             ('username', 'mobile', )),
        ]),
        perm_filter='can_reset_guest_password',
    )

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
            'password': password,
        }
        if getattr(cereconf, 'SMS_DISABLE', False):
            self.logger.info("SMS disabled in cereconf, would send"
                             " to %r", mobile)
        else:
            sms = SMSSender(logger=self.logger)
            if not sms(mobile, msg):
                raise CerebrumError(
                    "Unable to send SMS to registered number %s"
                    % repr(mobile))
        return {
            'username': account.account_name,
            'mobile': mobile,
        }


HELP_GUEST_GROUP = {
    'guest': "Commands for handling guest users",
}

HELP_GUEST_CMDS = {
    'guest': {
        'guest_create': (
            'Create a new guest user'
        ),
        'guest_remove': (
            'Deactivate a guest user'
        ),
        'guest_info': (
            'View information about a guest user'
        ),
        'guest_list': (
            'List out all guest users for a given owner'
        ),
        'guest_list_all': (
            'List out all guest users'
        ),
        'guest_reset_password': (
            'Reset the password of a guest user, and notify by SMS'
        ),
    },
}

HELP_GUEST_ARGS = {
    'guest_days': [
        'days',
        'Enter number of days',
        'Enter the number of days the guest user should be active',
    ],
    'guest_fname': [
        'given_name',
        "Enter guest's given name",
        "Enter the guest's first and middle name",
    ],
    'guest_lname': [
        'family_name',
        "Enter guest's family name",
        "Enter the guest's surname",
    ],
    'guest_responsible': [
        'responsible',
        "Enter the responsible user",
        "Enter the user that will be set as the responsible for the guest",
    ],
    'guest_group_name': [
        'group',
        'Enter group name',
        "Enter the group the guest should belong to",
    ],
    'guest_mobile_number': [
        'mobile',
        'Enter mobile number',
        (
            "Enter the guest's mobile number, where the "
            "username and password will be sent"
        ),
    ],
    'guest_account_name': [
        'username',
        'Enter username',
        'The name of a guest user account',
    ],
}
