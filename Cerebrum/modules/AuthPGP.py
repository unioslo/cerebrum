# -*- coding: utf-8 -*-
# Copyright 2005 University of Oslo, Norway
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
Mixin for PGP encrypted passwords.

Supports several PGP recipients, storing each system as a seperate
authentication code.

To use, add something like this to the cereconf.py:
::

    AUTH_PGP = {
       "offline": "0x8f382f1",
       "ad_ntnu_no": "0x82f1821d",
    }
    CLASS_ACCOUNT = ['Cerebrum.Account/Account',
                    (..)
                    'Cerebrum.modules.AuthPGP/AuthPGPAccountMixin']

    CLASS_CONSTANTS = [(..)
                      'Cerebrum.modules.AuthPGP/Constants']

Remember to run makedb --update-codes to add constants to the database
"""
import cereconf

from Cerebrum import Account
from Cerebrum.Constants import _AuthenticationCode
from Cerebrum.Utils import pgp_encrypt, pgp_decrypt
from Cerebrum.Utils import read_password


def _get_auth_code(system):
    codename = 'PGP-' + system
    auth_code = _AuthenticationCode(
        codename,
        "PGP encrypted password for the system %s" % system,
    )
    attr_name = "auth_type_pgp_%s" % system
    return attr_name, auth_code


class AuthPGPAccountMixin(Account.Account):
    """ Mixin for encryption methods """

    def _pgp_auth(self, system):
        _, const = _get_auth_code(system)
        return const

    def encrypt_password(self, method, plaintext, salt=None, binary=False):
        for system, pgpkey in cereconf.AUTH_PGP.items():
            if method == self._pgp_auth(system):
                return pgp_encrypt(plaintext, pgpkey)
        return self.__super.encrypt_password(method, plaintext, salt=salt,
                                             binary=binary)

    def decrypt_password(self, method, cryptstring):
        for system, pgpkey in cereconf.AUTH_PGP.items():
            if method == self._pgp_auth(system):
                passphrase = read_password(pgpkey, system)
                return pgp_decrypt(cryptstring, pgpkey, passphrase)
        return self.__super.decrypt_password(method, cryptstring)

    def verify_password(self, method, plaintext, cryptstring):
        for system, pgpkey in cereconf.AUTH_PGP.items():
            if method == self._pgp_auth(system):
                # TODO: it is possible to verify the plaintext if the
                # private key is available.
                return NotImplemented
        return self.__super.verify_password(method, plaintext, cryptstring)

    def delete(self):
        # TODO: Implement a log_change for this operation
        # Remove the entity from the gpg_data table when deleting an account
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_gpg_data]
        WHERE entity_id=:e_id""", {'e_id': self.entity_id})
        self.__super.delete()


class Constants:
    # Will add constants dynamically
    pass


_pgp_auth_codes = tuple(_get_auth_code(sys) for sys in cereconf.AUTH_PGP)


# WARNING: Hackish code below =)

# Generate authcode constants dynamically, one for each AUTH_PGP
# system, and add them to AUTH_CRYPT_METHODS


# Patch Constants mixin
for attr, code in _pgp_auth_codes:
    setattr(Constants, attr, code)


# Patch AUTH_CRYPT_METHODS:
# for _, code in _pgp_auth_codes:
#     cereconf.AUTH_CRYPT_METHODS += (str(code),)
