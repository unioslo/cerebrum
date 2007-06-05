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


"""Module for all exceptions in Spine which should be sent to clients.

Contains SpineException, which should be the base class for all exceptions
which should be sent to users.

Implement exceptions localy, in the modules where they fit the most.
Exceptions which have no obvious location can be implemented here.
"""

class SpineException(Exception):
    """Base-class for all exceptions in spine."""

class AccessDeniedError(SpineException):
    """Client doesn't have access to the method."""

class AlreadyLockedError(SpineException):
    """A locking error occurs."""

#class DatabaseError(SpineException):
#    """An error occurs with the database."""

class TransactionError(SpineException):
    """The error is related to a transaction."""

DatabaseError = TransactionError

# TODO: get this from another spine class
from Cerebrum.Utils import Factory
db=Factory.get("Database")()

IntegrityError = db.IntegrityError

IOError = IOError

class CreationError(DatabaseError):
    """Creation of an object fails."""

class DeletionError(DatabaseError):
    """Deletion of an object fails."""

class AlreadyExistsError(DatabaseError):
    """A unique constraint is violated in the database."""

class ClientProgrammingError(SpineException):
    """The client did something illegal."""

class ValueError(ClientProgrammingError):
    """The client does something involving an invalid value."""

class ObjectDeletedError(ClientProgrammingError):
    """Spine object referenced after deletion."""

class ServerProgrammingError(SpineException):
    """Something illegal is done in the server-side code."""

class NotFoundError(SpineException):
    """One or more objects are not found."""

class TooManyMatchesError(SpineException):
    """when a search, find, get or something similar has too many matches."""

# arch-tag: 7c3b53d8-649b-4dfc-8582-1664e52b6e0e
