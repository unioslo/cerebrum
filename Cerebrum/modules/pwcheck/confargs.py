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

"""
Password check mixin to insert default args from cereconf.
Important: add this to cereconf.CLASS_ACCOUNT before the other
PasswordCheckers
"""

from .common import PasswordChecker
import cereconf


class CereconfMixin(PasswordChecker):
    def password_good_enough(self, password, **kw):
        """Insert cereconf.PASSWORD_TEST_ARGUMENTS into keywords"""
        dta = cereconf.PASSWORD_TEST_ARGUMENTS.copy()
        dta.update(kw)
        super(CereconfMixin, self).password_good_enough(password, **dta)
