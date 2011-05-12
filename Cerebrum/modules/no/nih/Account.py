# -*- coding: iso-8859-1 -*-
# Copyright 2010 University of Oslo, Norway
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

""""""

import re

import cereconf

from Cerebrum import Account



class AccountNIHMixin(Account.Account):
    """Account mixin class providing functionality specific to NIH."""
    
    def suggest_unames(self, domain, fname, lname, maxlen=8, suffix=""):
        # Override Account.suggest_unames as HiHH allows up to 10 chars
        # in unames
        return self.__super.suggest_unames(domain, fname, lname, maxlen=10)
    

    def illegal_name(self, name):
        """ NIH can only allow max 10 characters in usernames.

        """
        # Max len should be 10; set to 30 to proceed with testing
        if len(name) > 30:
            return "too long (%s); max 10 chars allowed" % name
        if re.search("[^a-z0-9._-]", name):
            return "contains illegal characters (%s); only a-z allowed" % name
                
        return False



class AccountNIHEmailMixin(Account.Account):
    """Account mixin class providing email-related functionality
    specific to NIH.

    """
    pass
