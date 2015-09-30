#!/usr/bin/env python
# coding: utf-8
#
# Copyright 2015 University of Oslo, Norway
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

"""Password check mixin to handle phrases or passwords.
"""

from .common import PasswordChecker


class PhraseWordCheckSplitter(PasswordChecker):
    _passphrase_min_length = 12

    def is_passphrase(self, password):
        return len(password) >= self._passphrase_min_length

    def password_good_enough(self, password, **kw):
        """Categorizes password, and sets params to super() calls.

        Uses is_passphrase to categorize password into passphrase/not
        passphrase. If password is a passphrase, the keyword parameter
        `skip_rigid_password_tests` is set to True for further hierarchy calls.
        Else, it is set to False.
        """
        kw['skip_rigid_password_tests'] = self.is_passphrase(password)
        return super(PhraseWordCheckSplitter, self).password_good_enough(
            password, **kw)
