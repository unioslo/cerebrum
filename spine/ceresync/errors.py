# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

"""General exception classes for Ceresync.
Modules might subclass these for module-specific exceptions,
or add those exceptions that are general (like PosixError)
"""

from doc_exception import DocstringException, ProgrammingError

class SyncError(DocstringException):
    """General Sync error"""
    # Base class of Sync exceptions

class WrongModeError(SyncError, ProgrammingError):
    """Not supported in this mode of operation"""
    # For instance trying to do update() while not in incr mode

class BackendError(SyncError):
    """Could not use backend"""
    # For instance, if an LDAP backend could not be contacted

class ServerError(SyncError):
    """Spine Server error"""
    # With "Server" we mean the Spine server.

class LoginError(ServerError):
    """Could not login to Spine"""

class NotSupportedError(SyncError):
    """Object not supported"""
    # Raised if trying to add a user to a groupfile or whenever
    # the backend doesn't support the object's class

class NotPosixError(NotSupportedError):
    """Not POSIX user/group"""
    # Typically raised by UNIX backends

class AlreadyExistsError(BackendError):
    """Object already exists"""
    # Raised if the add could not be completed. For instance, 
    # add(user) with user.name=="root" should give this error in
    # some cases.

# arch-tag: 6e72e042-394c-446a-a668-8daf95076582
