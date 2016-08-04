#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
    Command, AccountName, FormatSuggestion, SimpleString, SMSString)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.bofhd_utils import copy_func
from Cerebrum.Utils import SMSSender
from Cerebrum.modules.no.uio.bofhd_auth import BofhdAuth

uio_helpers = ['_get_cached_passwords']


@copy_func(
    UiOBofhdExtension,
    methods=uio_helpers)
class BofhdExtension(BofhdCommonMethods):
    all_commands = {}

    authz = BofhdAuth

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

        # Select phone number
        try:
            from Cerebrum.modules.cis.Individuation import Individuation
            lookup_class = Individuation()
            mobile = lookup_class.get_phone_numbers(person)[0]['number']
        except IndexError:
            raise CerebrumError(
                'No applicable phone number for {}'.format(account_name))

        # Load and fill template for chosen language
        try:
            from os import path
            with open(path.join(cereconf.TEMPLATE_DIR,
                                'password_sms_{}.template'.format(language)),
                      'r') as f:
                msg = f.read().format(account_name, state.get('password'))
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
        """
        print('Message: {}'.format(message))
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied('Only superusers may send passwords by SMS')
        # Get person object
        person = self._get_person('account_name', account_name)
        # TODO: fetch mobile phone
        mobile = None
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
        return {'number': 12345}
