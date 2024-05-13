# -*- coding: utf-8 -*-
#
# Copyright 2002-2024 University of Oslo, Norway
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

Every implementation consists of a single py:class:`.AuthBaseClass`.  Usage:

py:meth:`.AuthBaseClass.encrypt(plaintext)`
    Create a cryptstring from plaintext.  Both plaintext and cryptstring are
    unicode/text objects.

py:meth:`.AuthBaseClass.encrypt(plaintext, salt=cryptstring)`
    Re-create a cryptstring from plaintext, using the salt from the given
    cryptstring.  Both plaintext and salt/cryptstring are expected to be
    unicode/text objects.

py:meth:`.AuthBaseClass.verify(plaintext, cryptstring)`
    Check that password matches the given cryptstring.  Both plaintext and
    cryptstring must be unicode/text objects.

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import base64
import crypt
import hashlib
import random
import string
import sys

# collections[.abc].Mapping
# (six.moves.collections_abc is broken in some versions)
if sys.version_info < (3,):
    from collections import Mapping
else:
    from collections.abc import Mapping

import passlib.hash
import six


#
# Python 3 compatibility helpers
#

def to_bytes(value):
    """ ensure value is a bytestring """
    if isinstance(value, six.text_type):
        return value.encode('ascii')
    if isinstance(value, bytes):
        return value
    else:
        return bytes(value)


def to_text(value):
    """ ensure value is a unicode text object. """
    if isinstance(value, bytes):
        return value.decode('ascii')
    elif isinstance(value, six.text_type):
        return value
    else:
        return six.text_type(value)


def crypt_bytes(plaintext, salt, encoding='utf-8'):
    """
    Python 3 compatibility function for crypt.crypt().

    `crypt.crypt()` expects str (unicode) objects in Python 3.  This is a bit
    silly, as we've already taken care to ensure plaintext input is a unicode
    object, and the plaintext given to hashing functions is a bytestring in our
    selected encoding.

    `crypt.crypt() in Python 3 seemingly encodes passwords as utf-8 prior to
    hashing.  crypt(3) doesn't specify any particular encodings, as it expects
    bytestrings.
    """
    # TODO: crypt.crypt() is deprecated as of Python 3.11.  We should probably
    # replace all uses of `crypt.crypt` with `passlib.hash`.

    if sys.version_info < (3,):
        # pass our bytestrings along to crypt.crypt
        cryptstring = crypt.crypt(plaintext, salt)
    else:
        cryptstring = crypt.crypt(plaintext.decode(encoding),
                                  salt.decode('ascii'))
    return to_text(cryptstring)


_crypt_salt_chars = string.ascii_letters + string.digits + "./"


def generate_salt(length, prefix=''):
    """
    Generate a crypt(3) compatible salt value.

    :param int length:
        Number of salt bytes/chars

    :param bytes prefix:
        A salt prefix (e.g. "$1$", for use in cryptstrings).  Must be bytes or
        ascii compatible text.

    :returns bytes:
        Returns a salt bytestring.
    """
    # Create a local random object for increased randomness:
    # > Use os.urandom() or SystemRandom if you require a
    # > cryptographically secure pseudo-random number generator.
    # > - <docs.python.org/2.7/library/random.html#random.SystemRandom>
    lrandom = random.SystemRandom()
    salt = "".join(lrandom.choice(_crypt_salt_chars)
                   for _ in range(length))
    return to_bytes(prefix + salt)


class AuthBaseClass(object):
    """
    Base class for auth methods.

    Each auth method *must* implement an encrypt method and a verify method,
    and *may* implement a decrypt method.
    """

    def encrypt(self, plaintext, salt=None, binary=False):
        """ Returns the hashed plaintext of a specific method

        :type plaintext: string
        :param plaintext: a secret to hash or encrypt for the database

        :type salt: string
        :param salt:
            salt for hashing, or a partial cryptstring with salt (and other
            parameters) for re-producing a previous cryptstring.

        :type binary: bool
        :param binary:
            allow bytestring plaintext value

            - False: plaintext *must* be a unicode object, which gets encoded
              as a utf-8 bytestring
            - True: if plaintext is a bytestring object, it is hashed as-is

        :rtype: six.text_type
        :return:
            Returns the hashed or encrypted text value.

            Note that Cerebrum only supports digests and cryptstrings that can
            be represented as text (i.e. no raw binary digests).

        :raise NotImplementedError:
            If this auth type is unsupported
        """
        raise NotImplementedError

    def decrypt(self, cryptstring):
        """ Returns the decrypted plaintext of a specific method

        :type cryptstring: String (unicode)
        :param cryptstring: The plaintext to hash

        :raise NotImplementedError:
            If this auth type cannot be returned to plaintext
        """
        raise NotImplementedError("This auth method does not support decrypt")

    def verify(self, plaintext, cryptstring):
        """ Compare a plaintext and a cryptstring.

        :rtype: bool
        :return:
            - *True* if the plaintext matches the cryptstring
            - *False* if the plaintext *doesn't* match the cryptstring

        :raise NotImplementedError:
            If this auth type cannot be used for verification
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
    """
    Salted SHA1 for LDAP

    See `<https://www.openldap.org/faq/data/cache/347.html>`_ for details.

    .. note::
        This implementation doesn't include a {SSHA} prefix in the result
        from :py:method:`.encrypt`, and does not accept a {SSHA} prefixed
        cryptstring in :py:method:`.verify`.

        This also means that any LDAP auth config for SSHA *must* set the
        correct prefix.

    .. todo::
        Should we replace this with passlib.hash.ldap_salted_sha1 and include
        the actual {SSHA} prefix in auth_data?
    """

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        if salt is None:
            salt = generate_salt(16)
        elif isinstance(salt, six.text_type):
            salt = to_bytes(salt)

        return to_text(
            base64.standard_b64encode(
                hashlib.sha1(plaintext + salt).digest()
                + salt))

    def verify(self, plaintext, cryptstring):
        salt = base64.standard_b64decode(to_bytes(cryptstring))[20:]
        return (self.encrypt(plaintext, salt=salt) == cryptstring)


@all_auth_methods('SHA-256-crypt')
class AuthTypeSHA256(AuthBaseClass):
    """
    Salted SHA-256 cryptstring for use with e.g. ``crypt(3)``.

    .. note::
        This auth method needs to be prefixed by {CRYPT} for use with OpenLDAP.
    """
    _implementation = passlib.hash.sha256_crypt
    _defaults = {
        'rounds': 55000,
    }

    @classmethod
    def encrypt(cls, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        settings = {}
        if salt:
            try:
                parts = cls._implementation.parsehash(salt)
                # *salt* was a valid cryptstring - use the salt and number of
                # rounds embedded within it
                settings.update({
                    'salt': parts['salt'],
                    'rounds': parts['rounds'],
                })
            except ValueError:
                # *salt* was not a valid cryptstring - assume it is an actual
                # byte sequence, and use the default number of rounds
                settings.update({
                    'salt': salt,
                })
        else:
            # no salt - new cryptstring
            settings.update(cls._defaults)

        return cls._implementation.using(**settings).hash(plaintext)

    @classmethod
    def verify(cls, plaintext, cryptstring):
        return cls._implementation.verify(plaintext, cryptstring)


@all_auth_methods('SHA-512-crypt')
class AuthTypeSHA512(AuthTypeSHA256):
    """
    Salted SHA-512 cryptstring for use with e.g. ``crypt(3)``.

    Behaves just like :py:class:`AuthTypeSHA256`.
    """
    _implementation = passlib.hash.sha512_crypt
    _defaults = {
        'rounds': 55000,
    }


@all_auth_methods('MD5-crypt')
class AuthTypeMD5(AuthBaseClass):
    """
    Salted MD5 cryptstring for use with e.g. ``crypt(3)``.

    .. note::
        This auth method needs to be prefixed by {CRYPT} for use with OpenLDAP.
    """

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        if salt is None:
            salt = generate_salt(8, prefix="$1$")
        elif isinstance(salt, six.text_type):
            salt = to_bytes(salt)

        return crypt_bytes(plaintext, salt, encoding='utf-8')

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt(plaintext, salt=salt) == cryptstring)


@all_auth_methods('MD4-NT')
class AuthTypeMD4NT(AuthBaseClass):
    """
    MD4 (NT-HASH) hex digest.
    """

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            # You probably need a degree in archeology to find an actual spec,
            # but NTLMv2 seems to use UCS-2 LE for passwords.
            #
            # `passlib.hash.nthash.hash()` already handles this by decoding
            # bytestrings as utf-8 and re-encoding them as utf-16-le
            plaintext = plaintext.encode('utf-8')

        # Previously the smbpasswd module was used to create nthash, and it
        # produced uppercase hex-string hashes.  This should be case
        # insensitive, but let's be backwards compatible if some comsumers
        # expects this to be upper case.
        return to_text(passlib.hash.nthash.hash(plaintext)).upper()

    def verify(self, plaintext, cryptstring):
        return passlib.hash.nthash.verify(plaintext, cryptstring)


@all_auth_methods('plaintext')
class AuthTypePlaintext(AuthBaseClass):
    """
    Mock auth method for plaintext secrets.
    """

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
    """
    Unsalted MD5 hex digest.
    """

    def encrypt(self, plaintext, salt=None, binary=False):
        if not isinstance(plaintext, six.text_type) and not binary:
            raise ValueError("plaintext cannot be bytestring and not binary")

        if isinstance(plaintext, six.text_type):
            plaintext = plaintext.encode('utf-8')

        return to_text(hashlib.md5(plaintext).hexdigest())

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt(plaintext, salt=salt) == cryptstring)
