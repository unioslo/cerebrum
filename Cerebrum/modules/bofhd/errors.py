# -*- coding: utf-8 -*-
# Copyright 2002-2014 University of Oslo, Norway
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
""" Bofh client/server exceptions.

The errors defined in this class, are errors that the bofhd server can
communicate to the client.

All client implementations should be aware of these exception types.

"""


class CerebrumError(StandardError):

    """ Signal a user-error. """

    pass


class PermissionDenied(CerebrumError):

    """ The operation was not permitted. """

    pass


class UnknownError(CerebrumError):

    """ An unknown error has occured. """

    def __init__(self, type, value, msg=None):
        """ Wrap a non-L{CerebrumError} in a L{CerebrumError} exception.

        @type type: type
        @param type: The exception class

        @type value: Exception
        @param value: The exception instance

        @type msg: None or basestring
        @param msg:
            An additional error message. This message will be prepended to the
            string value of this exception.

        """
        self._type = type
        self._value = value
        self._msg = msg or ''

    def __str__(self):
        return "Unknown error (%s): %s" % (getattr(self._type, '__name__', ''),
                                           self._msg)


class ServerRestartedError(CerebrumError):

    """ Notify the client that the server has restarted.

    When receiving this error, clients should flush any cached data.

    """

    pass


class SessionExpiredError(CerebrumError):

    """ Indicate that the C{session_id} is expired.

    This happens when the received C{session_id} is unknown.

    """

    pass
