#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
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
"""Exceptions used by the Exchange Client."""

from Cerebrum.modules.ad2.winrm import PowershellException
from urllib2 import URLError


class ObjectNotFoundException(PowershellException):

    """Exception for telling that an object does not exist in AD."""

    pass


class ADError(BaseException):

    """Exception to be raised when AD-related errors occour."""

    pass


class ExchangeException(BaseException):

    """Exception to be raised when Exchange-related errors occour."""

    pass


class AlreadyPerformedException(BaseException):

    """Exception for operations executed as a result of duplicate events."""

    pass

# TODO: Should this really be defined here?


class ServerUnavailableException(BaseException):

    """Exception to be raised if the servers are down."""

    pass
