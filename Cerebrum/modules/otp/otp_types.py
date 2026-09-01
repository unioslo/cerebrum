# -*- coding: utf-8 -*-
#
# Copyright 2022-2026 University of Oslo, Norway
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
This module contains utils for preparing and updating different otp types.

OTP types
----------
Each OTP type is backed by a :class:`.OtpType`.  Formatting and/or
encryption for a given target system is handled by this class.

Currently, we have three otp type values (and implementations):

plaintext
    Stores the secret as-is.  This is only a test-case/demo implementation, and
    should not be used.

radius-otp
    LDAP value for the ``uioRadiusOtpSecret`` attribute. Consists of a
    JWE-encrypted secret using a public key from the Radius system.

feide-ga
    LDAP value for the ``norEduPersonAuthnMethod`` attribute. JWE-encrypted
    using a public key from Feide.


OTP policy
-----------
The :class:`.OtpPolicy` is a collection of OtpType implementations,
and is used to generate a payload for each of its otp types when given a shared
secret.

Cerebrum currently only deals with one, common policy, which is configured by
``cereconf.OTP_POLICY``.  The value should be a tuple of OtpType classes, e.g.:
::

    OTP_POLICY = (
        'Cerebrum.modules.otp.otp_types/OtpTypeFeideJwe',
        'Cerebrum.modules.otp.otp_types/OtpTypeRadiusJwe',
    )

This value is used when fetching the default policy with :func:`.get_policy`.


Storing a new secret
---------------------
The :class:`~.otp_types.PersonOtpUpdater` handles updating all otp types in
the default otp policy

The following code will set a new shared *secret* for *person_id* for all
current otp types in the default policy, and remove any obsolete otp types:
::

    otp_policy = get_policy()
    otp_updater = PersonOtpUpdater(db, otp_policy)
    otp_updater.update(person_id, secret)

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import cereconf
from Cerebrum.utils.funcwrap import deprecate
from Cerebrum.utils.module import resolve
from . import otp_db
from . import otp_utils
from .jwe_utils import get_jwk, jwe_encrypt


@deprecate('use Cerebrum.modules.otp.otp_utils.generate_secret')
def generate_secret(*args, **kwargs):
    return otp_utils.generate_secret(*args, **kwargs)


@deprecate('use Cerebrum.modules.otp.otp_utils.validate_secret')
def validate_secret(*args, **kwargs):
    return otp_utils.validate_secret(*args, **kwargs)


class OtpType(object):
    """
    Abstract implementation of a given otp_type.

    This object is a callable that takes a OTP shared secret, and generates a
    payload to store for a given target system.
    """

    # Must be overridden in sublcasses
    otp_type = None

    def __call__(self, otp_secret):
        raise NotImplementedError()

    @classmethod
    def new(cls):
        return cls()


class OtpTypePlaintext(OtpType):
    """ Prepare a plaintext OTP secret. """

    otp_type = 'plaintext'

    def __call__(self, otp_secret):
        return otp_secret


class OtpTypeFeideJwe(OtpType):
    """
    Prepare a payload for otp type 'feide-ga'.

    .. note::
       Feide requires a 10 byte (16 base32 chars) secret, and uses the Google
       Authenticator defaults for TOTP (SHA-1, 6 digit code, 30 second period).
    """

    otp_type = 'feide-ga'
    """ OTP type to store this payload as. """

    key_alg = 'RSA-OAEP'
    """
    JWE key agreement algorithm to use.

    See :mod:`.jwe_utils` for details.
    """

    claims_enc = 'A128CBC-HS256'
    """
    JWE content encryption algorithm to use.

    See :mod:`.jwe_utils` for details.
    """

    default_pubkey = 'auth-file:feide-authenticator-key.pem'
    """
    Default key to use for encryption.

    See :meth:`.new` for details.
    """

    def __init__(self, jwk):
        """
        :type jwk: jwcrypto.jwk.JWK
        :param jwk: Key to use for JWE encryption
        """
        self.jwk = jwk

    def __call__(self, otp_secret):
        payload = {'secret': otp_secret}
        return jwe_encrypt(payload, self.jwk, alg=self.key_alg,
                           enc=self.claims_enc)

    @classmethod
    def new(cls, pubkey=None):
        """
        Initialize this object from a *pubkey* secret.

        :param str pubkey:
            The pubkey secret to read and use.

            Defaults to :data:`~.default_pubkey`.  See
            :func:`~.jwe_utils.get_jwk` and :mod:`Cerebrum.utils.secrets` for
            details.
        """
        jwk = get_jwk(pubkey or cls.default_pubkey)
        return cls(jwk)


class OtpTypeRadiusJwe(OtpType):
    """
    Prepare a payload for otp type 'radius-otp'.

    .. note::
       This is modelled after :class:`OtpTypeFeideJwe`, but uses a different
       pubkey.
    """

    otp_type = 'radius-otp'
    """ OTP type to store this payload as. """

    key_alg = 'RSA-OAEP'
    """
    JWE key agreement algorithm to use.

    See :mod:`.jwe_utils` for details.
    """

    claims_enc = 'A128CBC-HS256'
    """
    JWE content encryption algorithm to use.

    See :mod:`.jwe_utils` for details.
    """

    default_pubkey = 'auth-file:radius-authenticator.pem'
    """
    Default key to use for encryption.

    See :meth:`.new` for details.
    """

    def __init__(self, jwk):
        self.jwk = jwk

    def __call__(self, otp_secret):
        payload = {'secret': otp_secret}
        return jwe_encrypt(payload, self.jwk, alg=self.key_alg,
                           enc=self.claims_enc)

    @classmethod
    def new(cls, pubkey=None):
        """
        Initialize this object from a *pubkey* secret.

        :param str pubkey:
            The pubkey secret to read and use.

            Defaults to :data:`~.default_pubkey`.  See
            :func:`~.jwe_utils.get_jwk` and :mod:`Cerebrum.utils.secrets` for
            details.
        """
        jwk = get_jwk(pubkey or cls.default_pubkey)
        return cls(jwk)


class OtpPolicy(object):
    """
    Configuration for preparing (otp_type, otp_payload) tuples.
    """

    def __init__(self, otp_type_map):
        """
        :type otp_type_map: dict[str, OtpType]
        :param otp_type_map:
            OTP types and implementation for generating payloads.
        """
        self._otp_config = {}
        for otp_type in otp_type_map:
            self._otp_config[otp_type] = otp_type_map[otp_type]

    @property
    def otp_types(self):
        """ The otp types in this policy. """
        return tuple(self._otp_config.keys())

    def __call__(self, secret):
        """
        Generate payloads according to this policy.

        :param str secret: base-32 encoded shared secret

        :rtype: generator
        :returns:
            Tuples with (otp type, otp payload)
        """
        for otp_type, cb in self._otp_config.items():
            yield otp_type, cb(secret)


class PersonOtpUpdater(object):
    """
    Controller for updating otp data for a given person according to policy.
    """
    def __init__(self, db, policy):
        """
        :type db: Cerebrum.database.Database
        :type policy: OtpPolicy
        """
        self._db = db
        self._policy = policy

    def get_types(self, person_id):
        """ Get currently set otp_types in this policy for a person. """
        policy_types = set(self._policy.otp_types)
        exists = set(r['otp_type']
                     for r in otp_db.sql_search(self._db,
                                                person_id=int(person_id)))
        return policy_types & exists

    def clear_obsolete(self, person_id):
        """ Clear otp secrets that does not appear in policy. """
        exists = set(r['otp_type']
                     for r in otp_db.sql_search(self._db,
                                                person_id=int(person_id)))
        should_exist = self._policy.otp_types

        for otp_type in exists:
            if otp_type not in should_exist:
                otp_db.sql_clear(self._db, int(person_id), otp_type)

    def clear_all(self, person_id):
        """ Clear all otp secrets for a given person. """
        otp_db.sql_delete(self._db, person_id=int(person_id))

    def update(self, person_id, secret):
        """ Set a new otp secret for a given person.  """
        for otp_type, otp_payload in self._policy(secret):
            otp_db.sql_set(self._db, int(person_id), otp_type, otp_payload)

        self.clear_obsolete(person_id)


def get_policy():
    """
    Get the default otp policy.

    :rtype: OtpPolicy
    :returns: Returns the ``cereconf.OTP_POLICY`` as an OtpPolicy object.
    """
    try:
        otp_config = cereconf.OTP_POLICY
    except AttributeError:
        raise NotImplementedError("Missing cereconf.OTP_POLICY")
    otp_types = tuple(resolve(cls) for cls in otp_config)
    return OtpPolicy({cls.otp_type: cls.new() for cls in otp_types})
