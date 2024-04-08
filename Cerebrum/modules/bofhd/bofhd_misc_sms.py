# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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
This module contains a command for sending passwords by SMS.

Configuration
-------------
The following settings in ``cereconf`` are accessed directly in this module:

``AUTOADMIN_WELCOME_SMS``
    SMS template format string for welcome sms.

    The setting should contain a unified SMS welcome sms format string.
    The format string gets replacements for ``username`` and ``email``.

``BOFHD_ALLOW_MANUAL_MOBILE``
    Allow manually specifying mobile numbers for sms.

    Decides if operators are allowed to specify any phone number when sending
    welcome sms.

``SMS_DISABLE``
    Disable sms dispatching.

    This controls whether SMS actually gets sent by these bofhd comands.

``SMS_NUMBER_SELECTOR``
    Number selector for sending sms to account owners.

    Defines which numbers to allow and prioritize when selecting mobile number
    for sending SMS to a user account owner.

    Used in ``misc_sms_password`` (send new account password) and
    ``misc_sms_message`` (send free text sms).

``SMS_WELCOME_TYPE_NUMBER_SELECTOR``
    Number selector for sending welcome sms to account owners.

    Same as ``SMS_NUMBER_SELECTOR``, but for re-sending a welcome sms in
    ``user_send_welcome_sms``.

``TEMPLATE_DIR``
    Template directory for password message.

    ``misc_sms_password`` expects a ``password_sms_<language>.template`` file
    to exist in this directory.  The template should include a format string
    with ``account_name`` and ``password`` placeholders.

TODO
----
We should re-work some things related to SMS messages:

1. Common template system - Some mesasges comes from template files, others
   comes from cereconf settings.

2. Duplicated code - The number selection routines are duplicated in scripts
   that sends sms.  We should implement some common, reusable contact info
   selection routines.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import logging
import os
import textwrap

import cereconf

from Cerebrum import Errors
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (
    AccountName,
    Command,
    FormatSuggestion,
    Mobile,
    SMSString,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.utils import date as date_utils
from Cerebrum.utils.sms import SMSSender

logger = logging.getLogger(__name__)


class BofhdSmsAuth(BofhdAuth):
    """
    Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for SMS commands.
    """

    def can_send_freetext_sms_message(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True

        if self._has_operation_perm_somewhere(
                operator, self.const.auth_misc_sms_message):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("User does not have access")

    def can_send_welcome_sms(self, operator, query_run_any=False):
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        # TBD: Should we check if operator is "owner" of the entity and given
        # operation? I can't see use cases where that limitation is necessary.
        if self._has_operation_perm_somewhere(
                operator, self.const.auth_send_sms_welcome):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to send Welcome SMS")


class BofhdSmsCommands(BofhdCommonMethods):
    """ Various SMS-related bofhd commands. """

    all_commands = {}
    authz = BofhdSmsAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        # No GROUP_HELP, we'll just guess that 'user' and 'misc' exists
        # already.
        # The help structure doesn't really allow command groups to come from
        # different bofhd-extensions, so if we were to implement texts for
        # these groups, they might override texts defined elsewhere...
        return ({}, CMD_HELP, CMD_ARGS)

    def _get_phone_number(self, person_id, phone_types):
        """
        Find the best available contact info for a person.

        :param int person_id:
            entity-id of the person to contact

        :param list phone_types:
            sequence of (source-system, contact-type) pairs to look for
        """
        person = self._get_person('entity_id', person_id)
        for sys, type in phone_types:
            for row in person.get_contact_info(source=sys, type=type):
                return row['contact_value']

        return None

    def _select_sms_number(self, account_name):
        """
        Find the best matching mobile number for SMS.

        Search through an account owners contact info and return the best match
        according to cereconf.SMS_NUMBER_SELECTOR

        :param str account_name: account name
        :return str: mobile phone number
        """
        person = self._get_person('account_name', account_name)
        spec = list(_map_number_selector(self.const,
                                         cereconf.SMS_NUMBER_SELECTOR))
        person_in_systems = set(
            int(row['source_system'])
            for row in person.list_affiliations(person_id=person.entity_id))

        for row in person.sort_contact_info(spec, person.get_contact_info()):
            if row['source_system'] not in person_in_systems:
                # person must also have an active aff from the given system
                continue
            # return first match
            return row['contact_value']

        raise CerebrumError("No applicable phone number for "
                            + repr(account_name))

    #
    # user send_welcome_sms <accountname> [<mobile override>]
    #
    all_commands['user_send_welcome_sms'] = Command(
        ("user", "send_welcome_sms"),
        AccountName(help_ref="account_name", repeat=False),
        Mobile(help_ref='welcome-sms-mobile', optional=True),
        fs=FormatSuggestion([('Ok, message sent to %s', ('mobile',)), ]),
        perm_filter='can_send_welcome_sms',
    )

    def user_send_welcome_sms(self, operator, username, mobile=None):
        """Send a (new) welcome SMS to a user.

        Optional mobile override, if what's registered in Cerebrum is wrong or
        missing. Override must be permitted in the cereconf setting
        BOFHD_ALLOW_MANUAL_MOBILE.
        """
        account = self._get_account(username)
        self.ba.can_send_welcome_sms(operator.get_entity_id())

        # ensure allowed to specify a phone number
        if not cereconf.BOFHD_ALLOW_MANUAL_MOBILE and mobile:
            raise CerebrumError('Not allowed to specify number')

        # Ensure proper formatted phone number
        if mobile and not (len(mobile) == 8 and mobile.isdigit()):
            raise CerebrumError('Invalid phone number, must be 8 digits')

        # Ensure that this is an active, personal account
        if account.is_deleted():
            raise CerebrumError("User is deleted")
        if account.is_expired():
            raise CerebrumError("User is expired")
        if account.owner_type != self.const.entity_person:
            raise CerebrumError("User is not a personal account")

        # Look up the mobile number
        if not mobile:
            phone_types = list(
                _map_number_selector(
                    self.const,
                    cereconf.SMS_WELCOME_TYPE_NUMBER_SELECTOR))
            mobile = self._get_phone_number(account.owner_id, phone_types)

        if not mobile:
            raise CerebrumError("No mobile phone number for " + repr(username))

        # Get primary e-mail address, if it exists
        mailaddr = ''
        try:
            mailaddr = account.get_primary_mailaddress()
        except Exception:
            pass
        # NOTE: There's no need to supply the 'email' entry at the moment,
        # but contrib/no/send_welcome_sms.py does it as well
        message = _format_welcome_sms(username, mailaddr)

        # Set sent sms welcome sent-trait, so that it will be ignored by the
        # scheduled job for sending welcome-sms.
        try:
            account.delete_trait(self.const.trait_sms_welcome)
        except Errors.NotFoundError:
            pass
        finally:
            account.populate_trait(code=self.const.trait_sms_welcome,
                                   date=date_utils.now())
            account.write_db()

        _send_sms(mobile, message)
        return {'mobile': mobile}

    #
    # misc sms_password <username> [lang]
    #
    all_commands['misc_sms_password'] = Command(
        ('misc', 'sms_password'),
        AccountName(help_ref="account_name", repeat=False),
        SimpleString(help_ref='password-sms-language', repeat=False,
                     optional=True, default='no'),
        fs=FormatSuggestion('Password sent to %s.', ('number',)),
        perm_filter='is_superuser',
    )

    def misc_sms_password(self, operator, account_name, language='no'):
        """Send last password set for account in cache."""
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only superusers may send passwords by SMS")

        account = self._get_account(account_name)

        # Select last password change state entry for the account
        password = None
        for state in operator.get_state():
            if state['state_type'] != 'user_passwd':
                continue
            if not state['state_data']:
                continue
            if state['state_data']['account_id'] != account.entity_id:
                continue

            password = state['state_data']['password']

        if not password:
            raise CerebrumError('No password for %s in session'
                                % repr(account.account_name))

        mobile = self._select_sms_number(account.account_name)
        msg = _format_password_sms(language, account.account_name,
                                   password)

        # Maybe send SMS
        if getattr(cereconf, 'SMS_DISABLE', False):
            # SMSSender will do the same check, and log the same thing, but it
            # will also log the message.
            logger.info(
                'SMS disabled in cereconf, would have '
                'sent password to %r', mobile)
            return {'number': mobile}

        _send_sms(mobile, msg, is_sensitive=True)
        return {'number': mobile}

    #
    # misc sms_message <username> <message>
    #
    all_commands['misc_sms_message'] = Command(
        ('misc', 'sms_message'),
        AccountName(help_ref='account_name'),
        SMSString(help_ref='sms-message', repeat=False),
        fs=FormatSuggestion('Message sent to %s.', ('number',)),
        perm_filter='can_send_freetext_sms_message',
    )

    def misc_sms_message(self, operator, account_name, message):
        """
        Sends SMS message(s)
        """
        self.ba.can_send_freetext_sms_message(operator.get_entity_id())

        if not message or not message.strip():
            raise CerebrumError("Invalid message: empty")

        # our current sms gateway can only send text in latin-1
        try:
            message.encode("latin-1")
        except UnicodeError as e:
            raise CerebrumError("Invalid message: %s" % (e,))

        mobile = self._select_sms_number(account_name)
        _send_sms(mobile, message, is_sensitive=True)
        return {'number': mobile}


def _format_password_sms(language, username, password):
    """ Format a password sms message from template.  """
    filename = os.path.join(cereconf.TEMPLATE_DIR,
                            'password_sms_{}.template'.format(language))
    try:
        with io.open(filename, 'r', encoding='utf-8') as f:
            template = f.read()
    except IOError:
        raise CerebrumError("No template for language " + repr(language))
    return template.format(
        account_name=username,
        password=password,
    )


def _format_welcome_sms(username, email):
    """ Format a welcome sms message from config. """
    return cereconf.AUTOADMIN_WELCOME_SMS % {
        'username': username,
        'studentnumber': "",
        'email': email,
    }


def _map_number_selector(const, selector):
    """
    Prepare a contact info number selector from config.

    This function basicaly translates string values from cereconf settings
    (e.g.  SMS_NUMBER_SELECTOR) to actual constants.
    """
    for raw_sys, raw_ctype in selector:
        if raw_sys is None:
            sys = None
        else:
            sys = const.get_constant(const.AuthoritativeSystem, raw_sys)
        if raw_ctype is None:
            ctype = None
        else:
            ctype = const.get_constant(const.ContactInfo, raw_ctype)
        yield (sys, ctype)


def _send_sms(number, message, is_sensitive=False):
    """ Send sms using the SMS dispatcher, with some extra error handling.  """
    sms = SMSSender()

    if is_sensitive and getattr(cereconf, 'SMS_DISABLE', False):
        # SMSSender will do the same check, and log the same thing, but it
        # will also log the message content.
        logger.info(
            "SMS disabled by cereconf.SMS_DISABLE, "
            "would have sent message to %s",
            repr(number))
        return

    is_sent = False
    try:
        is_sent = sms(number, message)
    except UnicodeError:
        logger.warning("Encoding issue in SMS message", exc_info=True)
    except Exception:
        logger.error("Unable to send SMS", exc_info=True)

    if not is_sent:
        raise CerebrumError("Unable to send message to " + repr(number))


CMD_HELP = {
    'user': {
        'user_send_welcome_sms': 're-send the welcome sms to a user',
    },
    'misc': {
        'misc_sms_password': 'send a cached password to a user',
        'misc_sms_message': 'send a specified message to a user',
    },
}

CMD_ARGS = {
    # argname, prompt, help text
    'welcome-sms-mobile': [
        'welcome-sms-mobile',
        'Enter phone number (empty to auto-select)',
        textwrap.dedent(
            """
            A number to send the welcome SMS to, if allowed.

            Use an empty value to automatically select the best available
            number.
            """
        ).lstrip(),
    ],
    'password-sms-language': [
        'password-sms-language',
        'Enter a template language (no, en, ...)',
        'Language to use in the password SMS message',
    ],
    'sms-message': [
        'sms-message',
        'Enter message',
        'A message to send as SMS',
    ],
}
