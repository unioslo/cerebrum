#!/usr/bin/env python
# -*- encoding: iso-8859-1-*-
#
#
# Copyright 2009 University of Oslo, Norway
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

"""VirtHome's extension to password strength checking.

This module is a stub. We don't know yet what rules we should implement
here. 
"""

import re

from Cerebrum.modules.PasswordChecker import msgs
from Cerebrum.modules.PasswordChecker import PasswordGoodEnoughException
import Cerebrum.modules.PasswordChecker as MPC




class PasswordChecker(MPC.PasswordChecker):


    def _check_password_has_no_invalid_characters(self, password):
        """Check that only valid characters are allowed.
        """

        # nul is not allowed
        if '\0' in password:
            raise PasswordGoodEnoughException(msgs['not_null_char'])

        # 8-bit chars are problematic 
        if re.search(r'[\200-\376]', password):
            raise PasswordGoodEnoughException(msgs['8bit'])
    # end _check_password_has_no_invalid_characters



    def goodenough(self, account, plaintext, uname=None):
        """Check whether plaintext makes for a sufficiently good password.
        
        This method performs a number of checks on L{plaintext} to determine
        whether it makes a sufficienly good password in VirtHome (FIXME:
        outline the specific procedure below).

        @type account: VirtAccount instance or None.
        @param account:
          Account (VirtAccount) that we check the password for. If it's None,
          no account-specific checks will be performed (typically password
          history).

        @type plaintext: str
        @param plaintext:
          Plaintext password we want to test.

        @type uname: str:
        @param uname:
          Username we want to check. If None, no username-specific checks can
          be performed.

        @rtype: None
        @return:
          If all checks pass, this method returns nothing. If any of the
          requirements are not fullfilled, PasswordGoodEnoughException is
          raised. 
        """

        # Passwords must be strings...
        if not isinstance(plaintext, basestring):
            raise PasswordGoodEnoughException("Attempting to set non-string "
                                              "password %s" % plaintext)
        
        # Passwords must be printable ascii chars
        self._check_password_has_no_invalid_characters(plaintext)

        # Passwords must be at least 12 chars long
        if len(plaintext.strip()) < 12:
            raise PasswordGoodEnoughException("Password too short")

        # Passwords cannot be sequences
        self._check_sequence(plaintext)

        # Passwords must be printable ascii chars
        self._check_password_has_no_invalid_characters(plaintext)
    # end goodenough
# end class PasswordChecker        


