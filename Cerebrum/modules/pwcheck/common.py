#!/usr/bin/env python2
# encoding: utf-8
#
# Copyright 2003-2015 University of Oslo, Norway
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
""" This module contains common tools for password checks. """


import cerebrum_path
import cereconf

import string
from Cerebrum.Errors import CerebrumError
from Cerebrum.Account import Account


l33t_speak = string.maketrans('4831!05$72', 'abeiiosstz')
""" Translate strings from 'leet speak'. The value is a translation table
bytestring for `string.translate' """


class PasswordNotGoodEnough(CerebrumError):
    """Exception raised for insufficiently strong passwds."""

    pass


class PasswordChecker(Account):
    """ Password-checker API.

    The Cerebrum.Account provides the same API, but this base class can be used
    in tests, etc...
    """

    def password_good_enough(self, password, **kw):
        """ Check password.

        :param str password: The password to check

        :param dict kw: Other params to certain checks

        :return: Returns on success

        :raise PasswordNotGoodEnough:
            Raises an error if password is not good enough.
        """
        pass


if __name__ == '__main__':
    del cerebrum_path
    del cereconf
