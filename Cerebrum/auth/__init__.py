import base64
import crypt
import hashlib
import passlib
import string
from collections import Mapping

import passlib.hash
import six

import cereconf
from Cerebrum import Utils


class AuthBaseClass(object):

    def encrypt(self, plaintext, salt=None, binary=False):
        """Returns the plaintext hashed according to the specified
        method.  A mixin for a new method should not call super for
        the method it handles.

        This should be fixed for python3

        :type plaintext: String (unicode)
        :param plaintext: The plaintext to hash

        :type salt: String (unicode)
        :param salt: Salt for hashing

        :type binary: bool
        :param binary: Treat plaintext as binary data
        """
        raise NotImplementedError

    def decrypt(self, cryptstring):
        """Returns the decrypted plaintext according to the specified
        method.  If decryption is impossible, NotImplementedError is
        raised.  A mixin for a new method should not call super for
        the method it handles.
        """
        raise NotImplementedError("This auth method does not support decrypt")

    def verify(self, plaintext, cryptstring):
        """Returns True if the plaintext matches the cryptstring,
        False if it doesn't.  If the method doesn't support
        verification, NotImplemented is returned.
        """
        raise NotImplementedError


class AuthMap(Mapping):
    def __init__(self, *args, **kwargs):
        self._data = dict(*args, **kwargs)

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def add_method(self, method_key, method):
        if method_key not in self._data:
            self._data[method_key] = method

    def update(self, *args, **kwargs):
        return self._data.update(*args, **kwargs)

    def __call__(self, method_key):
        def wrapper(cls):
            self._data[str(method_key)] = cls
            return cls
        return wrapper

    def get_crypt_subset(self, methods):
        auth_crypt_methods = AuthMap()
        for m in methods:
            if str(m) in all_auth_methods._data:
                auth_crypt_methods.add_method(
                    str(m), all_auth_methods._data[str(m)])
        return auth_crypt_methods


all_auth_methods = AuthMap()


@all_auth_methods('SSHA')
class AuthTypeSSHA(AuthBaseClass):
    def encrypt(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = "$6$" + Utils.random_string(16, saltchars)
        salt = salt.encode('utf-8')
        return base64.b64encode(
            hashlib.sha1(plaintext + salt).digest() + salt).decode()

    def verify(self, plaintext, cryptstring):
        salt = base64.decodestring(cryptstring.encode())[20:].decode()
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('SHA-256-crypt')
class AuthTypeSHA256(AuthBaseClass):
    def encrypt(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = "$5$" + Utils.random_string(16, saltchars)
        return crypt.crypt(plaintext, salt.encode('utf-8')).decode()

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('SHA-512-crypt')
class AuthTypeSHA512(AuthBaseClass):
    def encrypt(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = "$6$" + Utils.random_string(16, saltchars)
        return crypt.crypt(plaintext, salt.encode('utf-8')).decode()

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('MD5-crypt')
class AuthTypeMD5(AuthBaseClass):
    def encrypt(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = "$1$" + Utils.random_string(8, saltchars)
        return crypt.crypt(plaintext, salt.encode('utf-8')).decode()

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('MD4-NT')
class AuthTypeMD4NT(AuthBaseClass):
    def encrypt(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
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
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        return plaintext

    def decrypt(self, cryptstring):
        return cryptstring


@all_auth_methods('md5-unstalted')
class AuthTypeMD5Unsalt(AuthBaseClass):
    def encrypt(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        return hashlib.md5(plaintext).hexdigest().decode()

    def verify(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


