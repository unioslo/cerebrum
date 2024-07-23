# -*- coding: utf-8 -*-
#
# Copyright 2020-2024 University of Oslo, Norway
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
Account mixin to provide VoIP auth methods for UiO.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import hashlib

import six

import cereconf
from Cerebrum import auth
from Cerebrum import Account


def encrypt_ha1_md5(account_name, realm, plaintext, salt=None, binary=False):
    if not isinstance(plaintext, six.text_type) and not binary:
        raise ValueError("plaintext cannot be bytestring and not binary")

    if isinstance(account_name, six.text_type):
        account_name = account_name.encode('utf-8')

    if isinstance(realm, six.text_type):
        realm = realm.encode('utf-8')

    if isinstance(plaintext, six.text_type):
        plaintext = plaintext.encode('utf-8')

    secret = b':'.join((account_name, realm, plaintext))
    return auth.to_text(hashlib.md5(secret).hexdigest())


def verify_ha1_md5(account_name, realm, plaintext, cryptstring):
    return encrypt_ha1_md5(account_name, realm, plaintext) == cryptstring


class VoipAuthAccountMixin(Account.Account):

    def encrypt_password(self, method, plaintext, salt=None, binary=False):
        if method == self.const.auth_type_ha1_md5:
            realm = cereconf.AUTH_HA1_REALM
            return encrypt_ha1_md5(self.account_name, realm, plaintext,
                                   salt=salt, binary=binary)

        return super(VoipAuthAccountMixin, self).encrypt_password(
            method,
            plaintext,
            salt=salt,
            binary=binary,
        )

    def verify_password(self, method, plaintext, cryptstring):
        if method == self.const.auth_type_ha1_md5:
            realm = cereconf.AUTH_HA1_REALM
            return verify_ha1_md5(self.account_name, realm, plaintext,
                                  cryptstring)

        return super(VoipAuthAccountMixin, self).verify_password(
            method,
            plaintext,
            cryptstring,
        )
