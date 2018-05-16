#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2018 University of Oslo, Norway
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
"""Utilities for sending SMS."""
from __future__ import unicode_literals

import logging
import re
import warnings

import requests
from six import text_type
from six.moves.urllib.parse import urlparse

import cereconf
from Cerebrum.Utils import read_password

logger = logging.getLogger(__name__)


class SMSSender():
    """Communicates with a Short Messages Service (SMS) gateway for sending
    out SMS messages.

    This class is meant to be used with UiOs SMS gateway, which uses basic
    HTTPS requests for communicating, and is also used by FS, but then through
    database links. This might not be the solution other institutions want to
    use if they have their own gateway.
    """

    def __init__(self, logger=None, url=None, user=None, system=None,
                 timeout=None):
        if logger is not None:
            warnings.warn("passing logger is deprecated", DeprecationWarning)
        self._url = url or cereconf.SMS_URL
        self._system = system or cereconf.SMS_SYSTEM
        self._user = user or cereconf.SMS_USER
        self._timeout = timeout or 10.0

    def _validate_response(self, response):
        """Check that the response from an SMS gateway says that the message
        was sent or not. The SMS gateway we use should respond with a
        latin1-encoded line formatted as:

         <msg_id>¤<status>¤<phone_to>¤<timestamp>¤¤¤<message>

        An example:

         UT_19611¤SENDES¤87654321¤20120322-15:36:35¤¤¤Welcome to UiO. Your

        ...followed by the rest of the lines with the message that was sent.

        :param requests.Response response: The response

        :rtype: bool
        :returns: True if the server's response says that the message was sent.
        """
        sep = b'\xa4'  # latin1 '¤'
        try:
            # msg_id, status, to, timestamp, message
            msg_id, status, to, _, _ = response.content.split(sep, 4)
        except ValueError:
            logger.warning("SMS: Bad response from server: %r",
                           response.content)
            return False

        if status == b'SENDES':
            return True
        logger.warning("SMS: Bad status=%r (phone_to=%r, msg_id=%r)",
                       status, to, msg_id)
        return False

    def _filter_phone_number(self, phone_to):
        """ Check if the mobile number, L{phone_to}, is a valid phone number.

        This function is used to whitelist phone numbers, which in turn will
        prevent sending messages to non-whitelisted numbers.

        This function can also be used if we want to wash phone numbers before
        passing them to the SMS gateway (e.g. strip spaces).

        NOTE: If the phone number is deemed un-sms-worthy, we raise a
            ValueError.

        :param unicode phone_to:
            The phone number that we will filter.

        :rtype: unicode
        :returns: The (properly formatted) phone number.
        """
        for regex in cereconf.SMS_ACCEPT_REGEX:
            if re.match(regex, phone_to):
                return phone_to
        raise ValueError("Invalid phone number '{}'".format(phone_to))

    def __call__(self, phone_to, message):
        """ Sends an SMS message to the given phone number.

        :param unicode phone_to:
          The phone number to send the message to.

        :param unicode message:
          The message to send to the given phone number.
        """
        assert isinstance(phone_to, text_type)
        assert isinstance(message, text_type)

        try:
            phone_to = self._filter_phone_number(phone_to)
        except ValueError as e:
            logger.warning("Unable to send SMS: %s", e)
            return False

        if getattr(cereconf, 'SMS_DISABLE', True):
            logger.info("Would have sent %r to %r'", message, phone_to)
            return True

        hostname = urlparse(self._url).hostname
        password = read_password(user=self._user, system=hostname)
        data = {
            'b': self._user,
            'p': password,
            's': self._system,
            't': phone_to,
            'm': message,
        }
        logger.debug("Sending SMS to %r (user=%r, system=%r)",
                     phone_to, self._user, self._system)

        try:
            response = requests.post(
                self._url, data=data, timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            logger.warning('SMS gateway error: %s', e)
            return False

        if response.status_code != 200:
            logger.warning("SMS gateway responded with code=%r body=%r",
                           response.status_code,
                           response.text)
            return False

        success = self._validate_response(response)
        if success:
            logger.debug("SMS to %r sent OK", phone_to)
        else:
            logger.warning("SMS to %r could not be sent", phone_to)
        return bool(success)
