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
Generate, validate, and format OTP secrets.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import base64
import os

from passlib.totp import TOTP

from Cerebrum.utils import text_compat


# TODO: How should we handle padding for secret sizes that aren't a multiple of
# 5?  It seems most totp uri parsers strip padding, but totp uris aren't
# specified very well...
DEFAULT_SECRET_SIZE = 10
"""
Default secret size, in bytes.

This is both the default size for new secrets, and the default size requirement
when validating a given secret.

OTP secrets can be of any length, but Feide requires secrets to be 10 bytes
(16 base32 chars).
"""

# Default label for otp uri
DEFAULT_LABEL = 'University of Oslo'
""" Default label for OTP URIs. """

DEFAULT_ISSUER = 'uio.no'
""" Default issuer in OTP URIs. """


def generate_secret(nbytes=DEFAULT_SECRET_SIZE):
    """
    Generate a new base32-encoded OTP shared secret.

    :param int nbytes: Secret size, in bytes.

    :rtype: str
    :returns: A base32-encoded secret.
    """
    # TODO: should we strip padding when nbytes is not a multiple of 5?
    return text_compat.to_text(base64.b32encode(os.urandom(nbytes)))


def validate_secret(secret, nbytes=DEFAULT_SECRET_SIZE):
    """ Check shared secret value.

    :param int nbytes: Required secret size, in bytes.

    :raise ValueError: if secret is invalid
    """
    secret = text_compat.to_bytes(secret)
    try:
        # TODO: should we try to add padding when secret is not of length
        # that is a multiple of 8?
        secret_len = len(base64.b32decode(secret))
    except Exception as e:
        raise ValueError('invalid base32-secret: %s' % (e,))

    if secret_len != nbytes:
        raise ValueError('invalid base32-secret: got %d bytes (expected %d)'
                         % (secret_len, nbytes))


def format_otp_uri(secret, label=DEFAULT_LABEL, issuer=DEFAULT_ISSUER):
    """ Format an otpauth uri for a shared secret.

    :param str secret: The base32-encoded OTP shared secret.
    :param str label: Label for the URI
    :param str issuer: Issuer of the secret in the URI

    :rtype: str
    :returns: An ``otpauth:`` URI

    :raise ValueError: if secret, label or issuer is invalid
    """
    otp_obj = TOTP(key=secret, format='base32', new=False,
                   label=label, issuer=issuer)
    return otp_obj.to_uri()
