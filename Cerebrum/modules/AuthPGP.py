# -*- coding: iso-8859-1 -*-
# Copyright 2004 University of Oslo, Norway
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

import cereconf
from Cerebrum.Constants import _AuthenticationCode
from Cerebrum.Utils import pgp_encrypt

"""Mixin for PGP encrypted passwords. Supports several PGP recipients,
storing each system as a seperate authentication code."""

# To use, add something like this to the cereconf.py
##AUTH_PGP = {
##    "offline": "0x8f382f1",
##    "ad_ntnu_no": "0x82f1821d",
##}
##CLASS_ACCOUNT = ['Cerebrum.Account/Account',
##                 (..)
##                 'Cerebrum.modules.AuthPGP/Account']
##
##CLASS_CONSTANTS = [(..)
##                   'Cerebrum.modules.AuthPGP/Constants']


# Mixin for encryption methods
class Account:
    # Will add methods dynamically
    pass

class Constants:
    # Will add constants dynamically
    pass

# WARNING: Hackish code below =)

# Generate authcode constants and encryption methods dynamically, one
# for each AUTH_PGP system
for (system, pgpkey) in cereconf.AUTH_PGP.items():
    auth_code = _AuthenticationCode('PGP-%s' % system,
                    "PGP encrypted password for the system %s" % system)
    name = "auth_type_pgp_%s" % system
    setattr(Constants, name, auth_code)

    # Each system is another method so they can be stored as
    # different "authentication types" and will be included by
    # set_password()
    if not name in cereconf.AUTH_CRYPT_METHODS:
        cereconf.AUTH_CRYPT_METHODS += (name,)

    # Generate a method that uses this PGP key
    def generate_method(name, pgpkey):
        """Closure for storing name/key"""
        methodname = "enc_" + name
        def method(self, plaintext, salt=None):
            """PGP encryption for system %s""" % system
            return pgp_encrypt(plaintext, pgpkey)
        method.func_name = methodname
        return method
    method = generate_method(name, pgpkey)
    # Add to our mixin so set_password() will find the method 
    setattr(Account, method.func_name, method)
        
