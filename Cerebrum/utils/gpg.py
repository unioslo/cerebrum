# -*- coding: utf-8 -*-
#
# Copyright 2016-2024 University of Oslo, Norway
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
Utilities for encrypting and decrypting messages with GnuPG.

Configuration
-------------
The cereconf setting *GNUPGHOME* sets the default home directory for GnuPG.

Tests
-----
As this module depends on GPG, unit tests are in a non-standard location,
``tests/gpg/``.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import logging
import subprocess

import gpgme
import six

import cereconf
from . import text_compat
from .funcwrap import deprecate

logger = logging.getLogger(__name__)


def get_gpgme_context(ascii_armor=True, gnupghome=None):
    """
    Create a GPGME context.

    :param bool ascii_armor:
        Use ascii armor (default: True).

    :param str gnupghome:
        GnuPG home directory with keys, etc...

    :rtype: gpgme.Context
    """
    home = gnupghome or cereconf.GNUPGHOME
    ctx = gpgme.Context()
    ctx.set_engine_info(gpgme.PROTOCOL_OpenPGP, None, home)
    if ascii_armor:
        ctx.armor = True
    return ctx


def gpgme_encrypt(message, recipient_key_id=None, context=None):
    """
    Encrypts a message using GnuPG (pygpgme).

    :type message: bytes, str
    :param message:
        Message to encrypt.  Encoded with UTF-8 if not given bytes.

    :param str recipient_key_id:
        key-id or fingerprint of a recipient.

        This function does not support multiple recipients.

    :type context: gpgme.Context
    :param context: A context to use (or None for the default context)

    :rtype: bytes, str
    :returns:
        The encrypted message.

        When using ascii-armor (default), this will be a ascii-compatible
        unicode string.
        If no ascii-armor is used (i.e. a custom context), this function
        returns raw bytes.

    :raises gpgme.GpgmeError:
        If e.g. missing the recipient key, or other GPG-related errors.
    """
    context = context or get_gpgme_context()
    try:
        recipient_key = context.get_key(recipient_key_id)
    except Exception as e:
        # Some logging to identify the failing key
        logger.warning('Unable to get key=%s: %s',
                       repr(recipient_key_id), six.text_type(e))
        raise

    # We encode the message to utf-8, unless we already got bytes
    input_buffer = io.BytesIO(text_compat.to_bytes(message))
    output_buffer = io.BytesIO()
    context.encrypt([recipient_key], 0, input_buffer, output_buffer)

    output_bytes = output_buffer.getvalue()
    if context.armor:
        return text_compat.to_text(output_bytes, "ascii")
    else:
        return output_bytes


def gpgme_decrypt(ciphertext, context=None):
    """
    Decrypts a ciphertext using GnuPG (pygpgme).

    :type ciphertext: bytes, str
    :param ciphertext: GPG message to decrypt

    :param context: set to use alternative gpgme context
    :type context: gpgme.Context or None

    :rtype: bytes
    :returns: the decrypted ciphertext (message)

    :rtype: bytes
    :returns: The decrypted data

    :raises gpgme.GpgmeError:
        If e.g. missing the decryption key, or other GPG-related errors.
    """
    context = context or get_gpgme_context()

    # If unicode ciphertext, we assume an ascii-armored gpg message:
    input_buffer = io.BytesIO(text_compat.to_bytes(ciphertext, "ascii"))
    output_buffer = io.BytesIO()
    context.decrypt(input_buffer, output_buffer)

    return output_buffer.getvalue()


# `_filtercmd`, `legacy_gpg_encrypt` and `legacy_gpg_decrypt` was moved from
# `Cerebrum.Utils` and modernized a bit.  We keep them around because:
#
#   1. `gpgme_decrypt` currently won't work with passphrase protected keys
#   2. These legacy functions don't rely on gpgme or pygpgme
#
# Note that unlocking passphrase protected keys is very finicky, as newer
# versions of gpg/gpgme (2.1/1.4) insists on involving pinentry and gpg-agent,
# while older versions won't accept the config/arguments that allows unlocking
# these keys using the loopback pinentry-mode.


def _filtercmd(cmd, input_data):
    """Send input on stdin to a command and collect the output from stdout.

    :param list cmd: command and arguments (same as popen)
    :param bytes input_data: data to be sent on stdin to the executable

    :returns bytes: stdout from command
    :raises IOError: if the command exits with an error code

    Example use:

      >>> _filtercmd(["sed", "s/bak/ost/"], b"bakekake")
      b'ostekake'
    """
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=False,
    )

    stdout, stderr = p.communicate(input_data)

    if stderr.strip():
        logger.warning('gpg stderr: %r', stderr)

    if p.returncode:
        raise IOError("%r exited with %i" % (cmd, p.returncode))

    return stdout


_GPG_BIN = '/usr/bin/gpg'


def _get_gpg_cmd(keyid, gnupghome, *args):
    return (
        _GPG_BIN,
        '--no-secmem-warning',
        '--quiet',
        '--batch',
        '--homedir', gnupghome or cereconf.GNUPGHOME,
        '--default-key', keyid,
    ) + args


@deprecate('use gpgme_encrypt()')
def legacy_gpg_encrypt(message, keyid, gnupghome=None):
    """
    Encrypts a message using gpg in a subprocess.

    :type message: bytes, str
    :param message:
        Message to encrypt.  Encoded with UTF-8 if not given bytes.

    :param str keyid:
        key-id or fingerprint of a recipient.

        This function does not support multiple recipients.

    :param str gnupghome:
        gpg homedir (defaults to cereconf.GNUPGHOME)

    :returns str:
        Returns an ascii-armored, encrypted gpg message

    :raises IOError:
        If e.g. missing the recipient key, or other GPG-related errors.
    """
    message_bytes = text_compat.to_bytes(message, "utf-8")
    cmd = _get_gpg_cmd(keyid, gnupghome, '--encrypt', '--armor',
                       '--recipient', keyid)
    output_bytes = _filtercmd(cmd, message_bytes)
    return output_bytes.decode("ascii")


@deprecate('use gpgme_decrypt()')
def legacy_gpg_decrypt(message, keyid, passphrase=None, gnupghome=None):
    """
    Decrypts a message using gpg in a subprocess.

    ..warning::


    :type message: bytes, str
    :param message: GPG message to decrypt

    :param str keyid:
        Default key for the gpg command.

        Note:  This is a historical argument  It's given as ``--default-key``
        to the gpg command, and doesn't really have any function, as the
        message itself should include the key-id to use for decryption.

    :param str passphrase:
        Passphrase for unlocking the private key

        Note:  Passphrase will not work with gpg 2.1/gpgme 1.4: gpg requires a
        '--pinentry-mode loopback' option and 'allow-loopback-pinentry' in
        gpg-agent.conf, which is not supported in 2.0

    :param str gnupghome:
        gpg homedir (defaults to cereconf.GNUPGHOME)

    :returns bytes:
        Returns the raw, decrypted message

    :raises IOError:
        If e.g. missing the decryption key, or other GPG-related errors.
    """
    # If unicode, we assume it's an ascii-armored gpg message:
    message_bytes = text_compat.to_bytes(message, "ascii")
    if passphrase:
        pass_opts = ('--passphrase-fd', '0')
        message_bytes = (text_compat.to_bytes(passphrase, "utf-8")
                         + b"\n"
                         + message_bytes)
    else:
        pass_opts = ()

    cmd = _get_gpg_cmd(keyid, gnupghome, '--decrypt', *pass_opts)
    return _filtercmd(cmd, message_bytes)
