# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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


from Cerebrum import Account
from Cerebrum import Errors
import re

account_name_regex=re.compile("^[a-z][a-z0-9]*$")

class AccountNoturMixin(Account.Account):
    def illegal_name(self, name):
        if len(name) > 8:
            return "too long (%s)" % name
        if not re.match(account_name_regex, name):
            return "misformed (%s)" % name
        return self.__super.illegal_name(name)


