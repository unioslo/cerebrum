#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2009-2015 University of Oslo, Norway
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

from Cerebrum.modules.pwcheck.simple import CheckLengthMixin
from Cerebrum.modules.pwcheck.simple import CheckInvalidCharsMixin
from Cerebrum.modules.pwcheck.simple import CheckCharSeqMixin
from Cerebrum.modules.pwcheck.common import PasswordNotGoodEnough


class VirthomePasswordChecker(CheckLengthMixin,
                              CheckInvalidCharsMixin,
                              CheckCharSeqMixin):

    # CheckLengthMixin
    _password_min_length = 12
    _password_max_length = None

    # CheckInvalidCharsMixin
    _password_illegal_chars = {
        '\0': "Password cannot contain the null character.", }
    _password_illegal_regex = {
        r'[\200-\376]':
            "Password cannot contain 8-bit characters (e.g.  æøå).", }

    def password_good_enough(self, password, **kw):
        """ Virthome password check. """
        if not isinstance(password, basestring):
            raise PasswordNotGoodEnough(
                "Attempting to set non-string password %s" % password)
        super(VirthomePasswordCheckerMixin,
              self).password_good_enough(password, **kw)
