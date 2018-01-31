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

import cereconf
import re
import socket
import urllib
import urllib2
import urlparse

from Cerebrum.Utils import Factory, read_password


class SMSSender():
    """Communicates with a Short Messages Service (SMS) gateway for sending
    out SMS messages.

    This class is meant to be used with UiOs SMS gateway, which uses basic
    HTTPS requests for communicating, and is also used by FS, but then through
    database links. This might not be the solution other institutions want to
    use if they have their own gateway.
    """

    def __init__(self, logger=None, url=None, user=None, system=None):
        self._logger = logger or Factory.get_logger("cronjob")
        self._url = url or cereconf.SMS_URL
        self._system = system or cereconf.SMS_SYSTEM
        self._user = user or cereconf.SMS_USER

    def _validate_response(self, ret):
        """Check that the response from an SMS gateway says that the message
        was sent or not. The SMS gateway we use should respond with a line
        formatted as:

         <msg_id>¤<status>¤<phone_to>¤<timestamp>¤¤¤<message>

        An example:

         UT_19611¤SENDES¤87654321¤20120322-15:36:35¤¤¤Welcome to UiO. Your

        ...followed by the rest of the lines with the message that was sent.

        :rtype: bool
        :returns: True if the server's response says that the message was sent.
        """
        # We're only interested in the first line:
        line = ret.readline()
        try:
            # msg_id, status, to, timestamp, message
            msg_id, status, to, _, _ = line.split('\xa4', 4)
        except ValueError:
            self._logger.warning("SMS: bad response from server: %s" % line)
            return False

        if status == 'SENDES':
            return True
        self._logger.warning(
            "SMS: Bad status '%s' (phone_to='%s', msg_id='%s')" % (
                status, to, msg_id))
        return False

    def _filter_phone_number(self, phone_to):
        """ Check if the mobile number, L{phone_to}, is a valid phone number.

        This function is used to whitelist phone numbers, which in turn will
        prevent sending messages to non-whitelisted numbers.

        This function can also be used if we want to wash phone numbers before
        passing them to the SMS gateway (e.g. strip spaces).

        NOTE: If the phone number is deemed un-sms-worthy, we raise a
            ValueError.

        :param str phone_to:
            The phone number that we will filter.

        :rtype: str
        :returns: The (properly formatted) phone number.
        """
        for regex in cereconf.SMS_ACCEPT_REGEX:
            if re.match(regex, phone_to):
                return phone_to

        raise ValueError("Invalid phone number '%s'" % phone_to)

    def __call__(self, phone_to, message, confirm=False):
        """ Sends an SMS message to the given phone number.

        :param basestring phone_to:
          The phone number to send the message to.

        :param basestring message:
          The message to send to the given phone number.

        :param bool confirm:
          If the gateway should wait for the message to be sent before it
          confirms it being sent.
        """
        try:
            phone_to = self._filter_phone_number(phone_to)
        except ValueError, e:
            self._logger.warning("Unable to send SMS: %s" % str(e))
            return False

        if getattr(cereconf, 'SMS_DISABLE', True):
            self._logger.info('Would have sent \'{}\' to {}'.format(message,
                                                                    phone_to))
            return True

        hostname = urlparse.urlparse(self._url).hostname
        password = read_password(user=self._user, system=hostname)
        postdata = urllib.urlencode({'b': self._user,
                                     'p': password,
                                     's': self._system,
                                     't': phone_to,
                                     'm': message})
        self._logger.debug("Sending SMS to %s (user: %s, system: %s)"
                           % (phone_to, self._user, self._system))

        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(60)  # in seconds

        try:
            ret = urllib2.urlopen(
                self._url,
                postdata)
        except urllib2.URLError, e:
            self._logger.warning('SMS gateway error: %s' % e)
            return False
        finally:
            socket.setdefaulttimeout(old_timeout)

        if ret.code is not 200:
            self._logger.warning("SMS gateway responded with code "
                                 "%s - %s" % (ret.code, ret.msg))
            return False

        resp = self._validate_response(ret)
        if resp:
            self._logger.debug("SMS to %s sent ok" % (phone_to))
        else:
            self._logger.warning("SMS to %s could not be sent" % phone_to)
        return bool(resp)
