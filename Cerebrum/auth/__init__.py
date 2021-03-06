# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
Auth module containers.

This module handles all auth implmentations by wrapping them in a dict-like
object, which you can derive different implementations from.

New implemtations should follow the same pattern as below.
"""
import base64
import crypt
import hashlib
import passlib
import string
from collections import Mapping

import passlib.hash
import six

from Cerebrum import Utils


class AuthBaseClass(object):
    """
    Base class for auth methods.

    Each auth method *must* implement an encrypt method and a verify method,
    and *may* implement a decrypt method.
    """

    def encrypt(self, plaintext, salt=None, binary=False):
        """ Returns the hashed plaintext of a specific method

        :type plaintext: String (unicode)
        :param plaintext: The plaintext to hash

        :type salt: String (unicode)
        :param salt: Salt for hashing

        :type binary: bool
        :param binary: Treat plaintext as binary data
        """
        raise NotImplementedError

    def decrypt(self, cryptstring):
        """ Returns the decrypted plaintext of a specific method

        :type cryptstring: String (unicode)
        :param cryptstring: The plaintext to hash
        """
        raise NotImplementedError("This auth method does not support decrypt")

    def verify(self, plaintext, cryptstring):
        """Returns True if the plaintext matches the cryptstring

        False if it doesn't.  If the method doesn't support
        verification, NotImplemented is returned.
        """
        raise NotImplementedError


class AuthMap(Mapping):
    """
    Container obejct for auth methods
    """

    def __init__(self, *args, **kwargs):
        self._data = dict(*args, **kwargs)

    def __repr__(self):
        return '<{cls.__name__} {methods}>'.format(
            cls=type(self),
            methods=', '.join(str(m) for m in sorted(self._data)),
        )

    def __getitem__(self, key):
        if key not in self._data:
            raise NotImplementedError
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def add_method(self, method_key, method):
        if method_key not in self._data:
            self._data[method_key] = method

    def __call__(self, method_key):
        def wrapper(cls):
            self._data[method_key] = cls
            return cls
        return wrapper

    def get_crypt_subset(self, methods):
        auth_crypt_methods = AuthMap()
        for m in methods:
            if str(m) in self._data:
                auth_crypt_methods.add_method(
                    str(m), self._data[str(m)])
        return auth_crypt_methods


all_auth_methods = AuthMap()


@all_auth_methods('SSHA')
class AuthTypeSSHA(AuthBaseClass):

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = bytes("$6$" + Utils.random_string(16, saltchars))
        elif isinstance(salt, six.text_type):
            salt = bytes(salt)

        return base64.b64encode(
            hashlib.sha1(plaintext + salt).digest() + salt).decode()

    def verify(self, plaintext, cryptstring):
        salt = base64.decodestring(cryptstring.encode())[20:].decode()
        return (self.encrypt(plaintext, salt=salt) == cryptstring)


@all_auth_methods('SHA-256-crypt')
class AuthTypeSHA256(AuthBaseClass):

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = bytes("$5$" + Utils.random_string(16, saltchars))
        elif isinstance(salt, six.text_type):
            salt = bytes(salt)

        return crypt.crypt(plaintext, salt).decode()

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt(plaintext, salt=salt) == cryptstring)


@all_auth_methods('SHA-512-crypt')
class AuthTypeSHA512(AuthBaseClass):

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = bytes("$6$" + Utils.random_string(16, saltchars))
        elif isinstance(salt, six.text_type):
            salt = bytes(salt)

        return crypt.crypt(plaintext, salt).decode()

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt(plaintext, salt=salt) == cryptstring)


@all_auth_methods('MD5-crypt')
class AuthTypeMD5(AuthBaseClass):

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = bytes("$1$" + Utils.random_string(8, saltchars))
        elif isinstance(salt, six.text_type):
            salt = bytes(salt)

        return crypt.crypt(plaintext, salt).decode()

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt(plaintext, salt=salt) == cryptstring)


@all_auth_methods('MD4-NT')
class AuthTypeMD4NT(AuthBaseClass):

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        # Previously the smbpasswd module was used to create nthash, and it
        # only produced uppercase hashes. The hash is case insensitive, but
        # be backwards compatible if some comsumers
        # depend on upper case strings.
        return passlib.hash.nthash.hash(plaintext).decode().upper()

    def verify(self, plaintext, cryptstring):
        return passlib.hash.nthash.verify(plaintext, cryptstring)


@all_auth_methods('plaintext')
class AuthTypePlaintext(AuthBaseClass):

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        # This gets a bit odd -- the encrypt-method returns unicode objects,
        # so if binary is set and we actually get a bytestring?  Let's just
        # assume that we've gotten a utf-8 bytestring?
        if not isinstance(plaintext, six.text_type):
            plaintext = plaintext.decode('utf-8')

        return plaintext

    def decrypt(self, cryptstring):
        return cryptstring

    def verify(self, plaintext, cryptstring):
        return self.encrypt(plaintext, salt=cryptstring) == cryptstring


@all_auth_methods('md5-unsalted')
class AuthTypeMD5Unsalt(AuthBaseClass):

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        return hashlib.md5(plaintext).hexdigest().decode()

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt(plaintext, salt=salt) == cryptstring)
