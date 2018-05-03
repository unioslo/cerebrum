#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2016 University of Oslo, Norway
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
"""

from __future__ import unicode_literals

from .checker import pwchecker, PasswordChecker


@pwchecker('brute_history')
class BruteCheckPasswordHistory(PasswordChecker):
    """ Match the password against PasswordHistory. """

    def __init__(self):
        self._requirement = _(
            'Must not be too similar to an old password')

    def check_password(self, password, account=None):
        if not account:
            return
        if not hasattr(account, '_bruteforce_check_password_history'):
            return
        if (account._bruteforce_check_password_history(password) or
                account._bruteforce_check_password_history(password[0:8])):
            return [_('Password too similar to an old password')]


@pwchecker('history')
class CheckPasswordHistory(PasswordChecker):
    """ Match the password against PasswordHistory. """

    def __init__(self):
        self._requirement = _(
            'Must not be the same as an old password')

    def check_password(self, password, account=None):
        if not account:
            return
        if not hasattr(account, '_check_password_history'):
            return
        if (account._check_password_history(password) or
                account._check_password_history(password[0:8])):
            return [_('Password is the same as an old password')]
