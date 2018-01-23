#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2018 University of Oslo, Norway
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
""" This module contains a command for sending passwords by SMS. """

import cereconf

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.no.uio.bofhd_uio_cmds import (
    BofhdExtension as UiOBofhdExtension)
from Cerebrum.modules.bofhd.cmd_param import (
    Command, AccountName, FormatSuggestion, SimpleString, SMSString, Mobile)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.Utils import SMSSender
from Cerebrum.modules.no.uio.bofhd_auth import BofhdAuth
from Cerebrum import Errors

from mx import DateTime

uio_helpers = ['_get_cached_passwords']


class BofhdAuth(BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for SMS commands.
    """

    def can_send_welcome_sms(self, operator, query_run_any=False):
        # Superusers can see and run command
        if self.is_superuser(operator):
            return True
        # Allow access if users can create other users
        if self.can_create_user(operator, query_run_any=True):
            return True
        # Hide command if not in the above groups
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to send Welcome SMS")


@copy_func(
    UiOBofhdExtension,
    methods=uio_helpers)
class BofhdExtension(BofhdCommonMethods):
    all_commands = {}

    authz = BofhdAuth

    # Helper function, get phone number
    def _get_phone_number(self, person_id, phone_types):
        """Search through a person's contact info and return the first found info
        value as defined by the given types and source systems.

        @type  person_id: integer
        @param person_id: Entity ID of the person

        @type  phone_types: list
        @param phone_types: list containing pairs of the source system and
                            contact type to look for, i.e. on the form:
                            (_AuthoritativeSystemCode, _ContactInfoCode)
        """
        person = self._get_person('entity_id', person_id)
        for sys, type in phone_types:
            for row in person.get_contact_info(source=sys, type=type):
                return row['contact_value']

        return None

    #
    # user send_welcome_sms <accountname> [<mobile override>]
    #
    all_commands['user_send_welcome_sms'] = Command(
        ("user", "send_welcome_sms"),
        AccountName(help_ref="account_name", repeat=False),
        Mobile(optional=True),
        fs=FormatSuggestion(
            [('Ok, message sent to %s', ('mobile',)), ]),
        perm_filter='can_send_welcome_sms')

    def user_send_welcome_sms(self, operator, username, mobile=None):
        """ Send a (new) welcome SMS to a user.

        Optional mobile override, if what's registered in Cerebrum is wrong or
        missing. Override must be permitted in the cereconf setting
        BOFHD_ALLOW_MANUAL_MOBILE.

        """
        sms = SMSSender(logger=self.logger)
        account = self._get_account(username)
        # Access Control
        self.ba.can_send_welcome_sms(operator.get_entity_id())
        # Ensure allowed to specify a phone number
        if not cereconf.BOFHD_ALLOW_MANUAL_MOBILE and mobile:
            raise CerebrumError('Not allowed to specify number')
        # Ensure proper formatted phone number
        if mobile and not (len(mobile) == 8 and mobile.isdigit()):
            raise CerebrumError('Invalid phone number, must be 8 digits')
        # Ensure proper account
        if account.is_deleted():
            raise CerebrumError("User is deleted")
        if account.is_expired():
            raise CerebrumError("User is expired")
        if account.owner_type != self.const.entity_person:
            raise CerebrumError("User is not a personal account")
        # Look up the mobile number
        if not mobile:
            phone_types = [(self.const.system_sap,
                            self.const.contact_private_mobile),
                           (self.const.system_sap,
                            self.const.contact_mobile_phone),
                           (self.const.system_fs,
                            self.const.contact_mobile_phone)]
            mobile = self._get_phone_number(account.owner_id, phone_types)
            if not mobile:
                raise CerebrumError("No mobile phone number for '%s'" %
                                    username)
        # Get primary e-mail address, if it exists
        mailaddr = ''
        try:
            mailaddr = account.get_primary_mailaddress()
        except:
            pass
        # NOTE: There's no need to supply the 'email' entry at the moment,
        # but contrib/no/send_welcome_sms.py does it as well
        message = cereconf.AUTOADMIN_WELCOME_SMS % {"username": username,
                                                    "email": mailaddr}
        if not sms(mobile, message):
            raise CerebrumError("Could not send SMS to %s" % mobile)

        # Set sent sms welcome sent-trait, so that it will be ignored by the
        # scheduled job for sending welcome-sms.
        try:
            account.delete_trait(self.const.trait_sms_welcome)
        except Errors.NotFoundError:
            pass
        finally:
            account.populate_trait(code=self.const.trait_sms_welcome,
                                   date=DateTime.now())
            account.write_db()
        return {'mobile': mobile}


    all_commands['misc_sms_password'] = Command(
        ('misc', 'sms_password'),
        AccountName(),
        SimpleString(optional=True, default='no'),
        fs=FormatSuggestion(
            'Password sent to %s.', ('number',)),
        perm_filter='is_superuser')

    def misc_sms_password(self, operator, account_name, language='no'):
        u""" Send last password set for account in cache. """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Only superusers may send passwords by SMS")

        # Select last password change state entry for the victim
        try:
            state = filter(
                lambda k: account_name == k.get('account_id'),
                filter(lambda e: e.get('operation') == 'user_passwd',
                       self._get_cached_passwords(operator)))[-1]
        except IndexError:
            raise CerebrumError(
                'No password for {} in session'.format(account_name))

        # Get person object
        person = self._get_person('account_name', account_name)

        # Select phone number, filter out numbers from systems where we do not
        # have an affiliation.
        try:
            spec = map(lambda (s, t): (self.const.human2constant(s),
                                       self.const.human2constant(t)),
                       cereconf.SMS_NUMBER_SELECTOR)
            mobile = person.sort_contact_info(spec, person.get_contact_info())
            person_in_systems = [int(af['source_system']) for af in
                                 person.list_affiliations(
                                     person_id=person.entity_id)]
            mobile = filter(lambda x: x['source_system'] in person_in_systems,
                            mobile)[0]['contact_value']

        except IndexError:
            raise CerebrumError(
                'No applicable phone number for {}'.format(account_name))

        # Load and fill template for chosen language
        try:
            from os import path
            with open(path.join(cereconf.TEMPLATE_DIR,
                                'password_sms_{}.template'.format(language)),
                      'r') as f:
                msg = f.read().format(account_name=account_name,
                                      password=state.get('password'))
        except IOError:
            raise CerebrumError(
                'Could not load template for language {}'.format(language))

        # Maybe send SMS
        if getattr(cereconf, 'SMS_DISABLE', False):
            self.logger.info(
                'SMS disabled in cereconf, would have '
                'sent password SMS to {}'.format(mobile))
        else:
            sms = SMSSender(logger=self.logger)
            if not sms(mobile, msg, confirm=True):
                raise CerebrumError(
                    'Unable to send message to {}, aborting'.format(mobile))

        return {'number': mobile}

    all_commands['misc_sms_message'] = Command(
        ('misc', 'sms_message'),
        AccountName(),
        SMSString(),
        fs=FormatSuggestion(
            'Message sent to %s.', ('number',)),
        perm_filter='is_superuser')

    def misc_sms_message(self, operator, account_name, message):
        """
        Sends SMS message(s)
        """
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('Only superusers may send messages by SMS')
        # Get person object
        person = self._get_person('account_name', account_name)
        # Select phone number, filter out numbers from systems where we do not
        # have an affiliation.
        try:
            spec = map(lambda (s, t): (self.const.human2constant(s),
                                       self.const.human2constant(t)),
                       cereconf.SMS_NUMBER_SELECTOR)
            mobile = person.sort_contact_info(spec, person.get_contact_info())
            person_in_systems = [int(af['source_system']) for af in
                                 person.list_affiliations(
                                     person_id=person.entity_id)]
            mobile = filter(lambda x: x['source_system'] in person_in_systems,
                            mobile)[0]['contact_value']
        except IndexError:
            raise CerebrumError(
                'No applicable phone number for {}'.format(account_name))
        # Send SMS
        if getattr(cereconf, 'SMS_DISABLE', False):
            self.logger.info(
                'SMS disabled in cereconf, would have '
                'sent password SMS to {}'.format(mobile))
        else:
            sms = SMSSender(logger=self.logger)
            if not sms(mobile, message, confirm=True):
                raise CerebrumError(
                    'Unable to send message to {}. Aborting.'.format(mobile))
        return {'number': mobile}
