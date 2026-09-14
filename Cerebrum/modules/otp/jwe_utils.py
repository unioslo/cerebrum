# -*- coding: utf-8 -*-
#
# Copyright 2021-2026 University of Oslo, Norway
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
JWK/JWE utils for encrypting otp secrets.

This module adds wrappers around the third party :mod:`jwcrypto` module, and
provides functions for loading JWKs (`RFC-7517`_), and encrypting and
decrypting JWEs (`RFC-7516`_).

JWKs are loaded using :mod:`Cerebrum.utils.secrets`.

.. _RFC-7516: https://datatracker.ietf.org/doc/html/rfc7516
.. _RFC-7517: https://datatracker.ietf.org/doc/html/rfc7517


Example use
------------
To encrypt a JWE using a PEM-formatted key with the default *alg* and *enc*:

.. code-block::

    secret_d = {'username': 'AzureDiamond', 'password': 'hunter2'}
    jwk = get_jwk('auth-file:pubkey.pem')
    token = jwe_encrypt(secret_d, jwk)
    print(token)


To decrypt a JWE:

.. code-block::

    jwk = get_jwk('auth-file:privkey.pem')
    print(jwe_decrypt(token, jwk))

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import json

import jwcrypto
import jwcrypto.jwe
import jwcrypto.jwk
import six

from Cerebrum.utils.secrets import get_secret_from_string


DEFAULT_KEY_ALG = 'RSA-OAEP'
"""
Default JWE key agreement algorithm.

This determines the default 'alg' header for JWE tokens created by
:func:`jwe_encrypt`.
"""

DEFAULT_CLAIMS_ENC = 'A128CBC-HS256'
"""
Default JWE content encryption algorithm.

This determines the default 'enc' header for JWE tokens created by
:func:`jwe_encrypt`.
"""


def _pem_to_jwk(pem):
    """ Get JWK object from a pem-formatted pubkey text. """
    if isinstance(pem, six.text_type):
        pem = pem.encode('ascii')
    return jwcrypto.jwk.JWK.from_pem(pem)


def get_jwk(value):
    """
    Load a JWK from a PEM-formatted secrets value.

    :param value:
        Where to look up the key (<source>:<args>).

        The key should be a PEM-formatted private or public key, depending on
        what it will be used for.  Examples:

        - ``auth-file:my-pubkey.pem``
        - ``file:/path/to/secret.pem``

        See :mod:`Cerebrum.utils.secrets` for details.

    :rtype: jwcrypto.jwk.JWK
    """
    pem_value = get_secret_from_string(value)
    return _pem_to_jwk(pem_value)


def jwe_encrypt(secret_data,
                jwk,
                alg=DEFAULT_KEY_ALG,
                enc=DEFAULT_CLAIMS_ENC):
    """
    Encrypt a data structure to a compact, serialized JWE token.

    :param secret_data: A serializable data structure to encrypt.
    :type key: jwcrypto.jwk.JWK
    :param alg: JWE key agreement to use.
    :param enc: JWE content encryption method to use.

    See :class:`jwcrypto.jwe.JWE` and `RFC-7516`_ for more info on the *alg*
    and *enc* values.

    :returns: A serialized JWE token.
    """
    payload = json.dumps(secret_data)
    header = {
        'alg': alg,
        'enc': enc,
        'typ': 'JWE',
        'kid': jwk.thumbprint(),
    }
    jwe = jwcrypto.jwe.JWE(
        payload,
        recipient=jwk,
        protected=header,
    )
    return jwe.serialize(compact=True)


def jwe_decrypt(token, jwk):
    """
    Decrypt a serialized JWE token.

    :param data: A serialized JWE token.
    :type key: jwcrypto.jwk.JWK

    :rtype: jwcrypto.jwe.JWE
    """
    jwe = jwcrypto.jwe.JWE()
    jwe.deserialize(token)
    jwe.decrypt(jwk)
    return json.loads(jwe.payload)
