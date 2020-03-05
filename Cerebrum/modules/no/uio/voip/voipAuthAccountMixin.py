import hashlib
import six

import cereconf
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
    return hashlib.md5(secret).hexdigest().decode()


def verify_ha1_md5(account_name, realm, plaintext, cryptstring):
    return (encrypt_ha1_md5(
        account_name, realm, plaintext) == cryptstring)


class VoipAuthAccountMixin(Account.Account):
    def encrypt_password(self, method, plaintext, salt=None, binary=False):
        if method == self.const.auth_type_ha1_md5:
            realm = cereconf.AUTH_HA1_REALM
            return encrypt_ha1_md5(
                self.account_name, realm, plaintext, salt, binary)
        return super(VoipAuthAccountMixin, self).encrypt_password(
            method, plaintext, salt=salt, binary=binary)

    def verify_password(self, method, plaintext, cryptstring):
        if method == self.const.auth_type_ha1_md5:
            realm = cereconf.AUTH_HA1_REALM
            return verify_ha1_md5(
                self.account_name, realm, plaintext, cryptstring)
        return super(VoipAuthAccountMixin, self).verify_password(
            method, plaintext, cryptstring)
