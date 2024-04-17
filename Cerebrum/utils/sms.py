# -*- coding: utf-8 -*-
#
# Copyright 2004-2024 University of Oslo, Norway
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
Utilities for sending SMS.

Configuration
-------------
The following ``cereconf`` settings affect this module:

``SMS_ACCEPT_REGEX`` (list, required)
    A list of regex patterns for validating phone numbers.

    Phone numbers must match at least one pattern from this setting for SMS
    messaging to work.  If no patterns are set, or none of the provided
    patterns matches a given number, then sending SMS to that number will fail.

``SMS_DISABLE`` (bool, optional, default: ``True``)
    This value must be set to ``False`` to send messages to the SMS service.

    This is a failsafe to prevent mass-sending messages in test environments.
    It should always be set to ``False`` in production, and ``True`` in any
    other environment.

``SMS_SYSTEM`` (str, required)
    A system value to use for authentication.

    This decides which budget to use for invoicing.  The ``SMS_USER`` must have
    access to this ``SMS_SYSTEM``.

``SMS_URL`` (str, required)
    The URL to a supported SMS messaging API.

``SMS_USER`` (str, required)
    A username to use for authentication.

    The username must be tied to the ``SMS_SYSTEM`` in our SMS gateway.

Authentication
--------------
The password for authentication must be available as a *legacy secret*.  See
:func:`.secrets.legacy_read_password` for details.

Note that the *system* portion of the legacy secret name comes from the
``SMS_URL`` setting: ``passwd-<SMS_USER>@<SMS_URL hostname>``
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging
import re
import warnings

import requests
import six
from six.moves.urllib import parse as urllib_parse

import cereconf
from . import secrets

logger = logging.getLogger(__name__)


class SMSSender():
    """
    Communicates with a Short Messages Service (SMS) gateway for sending
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
        """
        Check the API reposnse from our SMS gateway.

        The SMS gateway we use should respond with a
        latin-1 encoded line formatted as:
        ::

            <msg_id>¤<status>¤<phone_to>¤<timestamp>¤¤¤<message>

        An example:

            UT_19611¤SENDES¤87654321¤20120322-15:36:35¤¤¤Welcome to UiO. ...

        followed by the rest of the lines from the message that was sent.

        :type reposnse: requests.Response

        :returns bool:
            True if the response says that the message was sent.
        """
        sep = b'\xa4'  # latin1 '¤'
        try:
            # msg_id, status, to, timestamp, message
            msg_id, status, to, _, _ = response.content.split(sep, 4)
        except ValueError:
            logger.warning("SMS: Bad response from server: %s",
                           repr(response.content))
            return False

        if status == b'SENDES':
            return True
        logger.warning("SMS: Bad status=%s (phone_to=%s, msg_id=%s)",
                       repr(status), repr(to), repr(msg_id))
        return False

    def _filter_phone_number(self, phone_to):
        """
        Validate and normalize the *phone_to* mobile number.

        This function is used to whitelist phone numbers, which in turn will
        prevent sending messages to non-whitelisted numbers.

        This function can also be used if we want to wash phone numbers before
        passing them to the SMS gateway (e.g. strip spaces).

        NOTE: If the phone number is deemed un-sms-worthy, we raise a
            ValueError.

        :param str phone_to:
            The phone number to check

        :returns str:
            The (properly formatted) phone number.

        :raises ValueError:
            If the phone number is deemed un-sms-worthy
        """
        for regex in cereconf.SMS_ACCEPT_REGEX:
            if re.match(regex, phone_to):
                return phone_to
        raise ValueError("Invalid phone number '{}'".format(phone_to))

    def __call__(self, phone_to, message):
        """
        Sends an SMS message to the given phone number.

        :param str phone_to:
            The phone number to send the message to.

        :param str message:
            The message to send to the given phone number.
        """
        assert isinstance(phone_to, six.text_type)
        assert isinstance(message, six.text_type)

        try:
            phone_to = self._filter_phone_number(phone_to)
        except ValueError as e:
            logger.warning("Unable to send SMS: %s", e)
            return False

        if getattr(cereconf, 'SMS_DISABLE', True):
            logger.info("Would have sent %r to %r'", message, phone_to)
            return True

        hostname = urllib_parse.urlparse(self._url).hostname
        password = secrets.legacy_read_password(user=self._user,
                                                system=hostname)
        data = {
            b'b': self._user.encode('latin1'),
            b'p': password.encode('latin1'),
            b's': self._system.encode('latin1'),
            b't': phone_to.encode('latin1'),
            b'm': message.encode('latin1'),
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
