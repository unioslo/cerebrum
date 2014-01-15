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

from Cerebrum.modules.ad2.winrm import PowershellException
from urllib2 import URLError

class ObjectNotFoundException(PowershellException):
    """Exception for telling that an object does not exist in AD."""
    pass

class ObjectAlreadyExistsException(PowershellException):
    """Exception for telling that an object already exists in AD."""
    pass

class NoAccessException(PowershellException):
    """Exception for telling that Cerebrum were not allowed to execute an
    operation due to limited access rights in Active Directory.

    """
    pass

class SizeLimitException(PowershellException):
    """Exception for when too many rows are tried to be returned from AD.

    This is triggered by AD when you try to get lists of more than 1500? 2000?
    objects, for example all objects in an OU or all members of a large group.
    The limit is a standard value in AD, but it could be set to other values.

    """
    pass

class OUUnknownException(PowershellException):
    """Exception for when an OU was not found.

    This could happen in various scenarios, e.g. when trying to create an object
    in a given, nonexisting OU, or trying to get all objects from a given OU.

    """
    pass


class ADError(BaseException):
    """Exception to be raised when AD-related errors occour"""
    pass

class ExchangeException(BaseException):
    """Exception to be raised when Exchange-related errors occour"""
    pass

#TODO: Should this really be defined here?

class ServerUnavailableException(BaseException):
    """Exception to be raised if the servers are down"""
    pass


