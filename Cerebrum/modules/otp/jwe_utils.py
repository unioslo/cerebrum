# -*- coding: utf-8 -*-
#
# Copyright 2021-2024 University of Oslo, Norway
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

Example use
-----------
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

from Cerebrum.utils.secrets import get_secret


DEFAULT_KEY_ALG = 'RSA-OAEP'
DEFAULT_CLAIMS_ENC = 'A128CBC-HS256'


def _get_pem_content(value):
    """ fetch pem content from config value. """
    source, _, value = value.partition(':')
    return get_secret(source, value)


def _pem_to_jwk(pem):
    """ Get JWK object from a pem-formatted pubkey text. """
    if isinstance(pem, six.text_type):
        pem = pem.encode('ascii')
    return jwcrypto.jwk.JWK.from_pem(pem)


def get_jwk(value):
    """
    Get JWK from config value.

    :param value:
        How/where to fetch the jwk public key (<source>:<args>).

        Examples: 'auth-file:my-pubkey.pem', 'file:/path/to/secret.txt'.  See
        py:mod:`Cerebrum.utils.secrets` for details.

    :rtype: jwcrypto.jwk.JWK
    """
    return _pem_to_jwk(_get_pem_content(value))


def jwe_encrypt(secret_data,
                jwk,
                alg=DEFAULT_KEY_ALG,
                enc=DEFAULT_CLAIMS_ENC):
    """
    Encrypt a data structure using JWE.

    :param secret_data: A serializable data structure to encrypt.
    :type key: jwcrypto.jwk.JWK
    :param alg: JWE key agreement to use.
    :param enc: JWE content encryption method to use.

    See py:mod:`jwcrypto.jwe` for allowed alg and enc values.

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
    Decrypt a serialized JWE text.

    :param data: A serialized JWE token.
    :type key: jwcrypto.jwk.JWK

    :rtype: jwcrypto.jwe.JWE
    """
    jwe = jwcrypto.jwe.JWE()
    jwe.deserialize(token)
    jwe.decrypt(jwk)
    return json.loads(jwe.payload)
