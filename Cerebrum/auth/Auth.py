import base64
import crypt
import hashlib
import passlib
import passlib.hash
import string
import six

from collections import MutableMapping

from Cerebrum import Utils

import cereconf


class AuthBaseClass(object):

    def encrypt_password(self):
        """Returns the plaintext hashed according to the specified
        method.  A mixin for a new method should not call super for
        the method it handles.

        This should be fixed for python3

        :type method: Constants.AccountAuthentication
        :param method: Some auth_type_x constant

        :type plaintext: String (unicode)
        :param plaintext: The plaintext to hash

        :type salt: String (unicode)
        :param salt: Salt for hashing

        :type binary: bool
        :param binary: Treat plaintext as binary data
        """
        raise NotImplementedError

    def decrypt_password(self):
        """Returns the decrypted plaintext according to the specified
        method.  If decryption is impossible, NotImplementedError is
        raised.  A mixin for a new method should not call super for
        the method it handles.
        """
        raise NotImplementedError("This auth method does not support decrypt")

    def verify_hash(self):
        """Returns True if the plaintext matches the cryptstring,
        False if it doesn't.  If the method doesn't support
        verification, NotImplemented is returned.
        """
        raise NotImplementedError


class AuthMap(MutableMapping):
    def __setitem__(self, key, item):
        self.__dict__[key] = item

    def __getitem__(self, key):
        return self.__dict__[key]

    def __len__(self):
        return len(self.__dict__)

    def __delitem__(self, key):
        del self.__dict__[key]

    def __iter__(self):
        return iter(self.__dict__)

    def update(self, *args, **kwargs):
        return self.__dict__.update(*args, **kwargs)

    def __call__(self, method_key):
        def wrapper(cls):
            self.__dict__[str(method_key)] = cls
            return cls
        return wrapper


all_auth_methods = AuthMap()


@all_auth_methods('auth_type_ssha')
class AuthTypeSSHA(AuthBaseClass):
    def encrypt_password(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = "$6$" + Utils.random_string(16, saltchars)
        salt = salt.encode('utf-8')
        return base64.b64encode(
            hashlib.sha1(plaintext + salt).digest() + salt).decode()

    def verify_password(self, plaintext, cryptstring):
        salt = base64.decodestring(cryptstring.encode())[20:].decode()
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('auth_type_sha256')
class AuthTypeSHA256(AuthBaseClass):
    def encrypt_password(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = "$5$" + Utils.random_string(16, saltchars)
        return crypt.crypt(plaintext, salt.encode('utf-8')).decode()

    def verify_password(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('auth_type_sha512')
class AuthTypeSHA512(AuthBaseClass):
    def encrypt_password(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = "$6$" + Utils.random_string(16, saltchars)
        return crypt.crypt(plaintext, salt.encode('utf-8')).decode()

    def verify_password(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('auth_type_md5')
class AuthTypeMD5(AuthBaseClass):
    def encrypt_password(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        if salt is None:
            saltchars = string.ascii_letters + string.digits + "./"
            salt = "$1$" + Utils.random_string(8, saltchars)
        return crypt.crypt(plaintext, salt.encode('utf-8')).decode()

    def verify_password(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('auth_type_md4_nt')
class AuthTypeMD4NT(AuthBaseClass):
    def encrypt_password(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        # Previously the smbpasswd module was used to create nthash, and it
        # only produced uppercase hashes. The hash is case insensitive, but
        # be backwards compatible if some comsumers
        # depend on upper case strings.
        return passlib.hash.nthash.hash(plaintext).decode().upper()

    def verify_password(self, plaintext, cryptstring):
        return passlib.hash.nthash.verify(plaintext, cryptstring)


@all_auth_methods('auth_type_plaintext')
class AuthTypePlaintext(AuthBaseClass):
    def encrypt_password(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        return plaintext

    def decrypt_password(self, plaintext, cryptstring):
        return cryptstring


@all_auth_methods('auth_type_md5_unsalt')
class AuthTypeMD5Unsalt(AuthBaseClass):
    def encrypt_password(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')
        return hashlib.md5(plaintext).hexdigest().decode()

    def decrypt_password(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


@all_auth_methods('auth_type_ha1_md5')
class AuthTypeHA1MD5(AuthBaseClass):
    def encrypt_password(self, plaintext, salt=None, binary=False):
        if not binary:
            assert(isinstance(plaintext, six.text_type))
            plaintext = plaintext.encode('utf-8')

        # TODO: FIXME: This needs some things from Account
        s = ":".join([self.account_name, cereconf.AUTH_HA1_REALM, plaintext])
        return hashlib.md5(s.encode('utf-8')).hexdigest().decode()

    def decrypt_password(self, plaintext, cryptstring):
        salt = cryptstring
        return (self.encrypt_password(plaintext, salt=salt) == cryptstring)


cereconf.AUTH_CRYPT_METHODS = [
    'auth_type_ssha',
    'auth_type_sha256',
    'auth_type_sha512',
    'auth_type_md5',
    'auth_type_md4_nt',
    'auth_type_plaintext',
    'auth_type_md5_unsalt',
    'auth_type_ha1_md5'
]


def get_crypt_methods():
    auth_crypt_methods = AuthMap()
    for m in cereconf.AUTH_CRYPT_METHODS:
        auth_crypt_methods[m] = all_auth_methods[m]
    return auth_crypt_methods
