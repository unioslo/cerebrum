# -*- coding: utf-8 -*-
#
# Copyright 2016-2026 University of Oslo, Norway
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
GnuPG encryption and decryption utilities.

Configuration
==============
``cereconf.GNUPGHOME`` sets the default GnuPG home directory.

Tests
======
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
    Create a GpgME context.

    :param bool ascii_armor:
        Use ASCII armor (default: True)

    :param str gnupghome:
        GnuPG home directory (default: ``cereconf.GNUPGHOME``)

    :rtype: gpgme.Context
    :returns: A GpgME context with the provided settings.
    """
    home = gnupghome or cereconf.GNUPGHOME
    ctx = gpgme.Context()
    ctx.set_engine_info(gpgme.PROTOCOL_OpenPGP, None, home)
    if ascii_armor:
        ctx.armor = True
    return ctx


def gpgme_encrypt(message, recipient_key_id=None, context=None):
    """
    Encrypt a message using GpgME (pygpgme).

    :type message: str or bytes
    :param message: Data to encrypt (str is encoded as UTF-8)

    :type recipient_key_id: str
    :param recipient_key_id:
        Key id or fingerprint of recipient (multiple recipients not supported)

    :type context: gpgme.Context or None
    :param context: Optional GpgME context with custom settings.

    :rtype: str or bytes
    :returns:
        Encrypted ciphertext.  Returns a unicode string when using ASCII armor
        (default), otherwise raw bytes.

    :raises gpgme.GpgmeError: on missing key or other GPG errors
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
    Decrypt a ciphertext using GpgME (pygpgme).

    :type ciphertext: str or bytes
    :param ciphertext: GPG ciphertext to decrypt

    :type context: gpgme.Context or None
    :param context: Optional GpgME context with custom settings.

    :rtype: bytes
    :returns: The decrypted data.

    :raises gpgme.GpgmeError: on missing key or other GPG errors
    """
    context = context or get_gpgme_context()

    # If unicode ciphertext, we assume an ascii-armored gpg message:
    input_buffer = io.BytesIO(text_compat.to_bytes(ciphertext, "ascii"))
    output_buffer = io.BytesIO()
    context.decrypt(input_buffer, output_buffer)

    return output_buffer.getvalue()


# `_filtercmd`, `legacy_gpg_encrypt` and `legacy_gpg_decrypt` were moved from
# `Cerebrum.Utils` and modernized a bit.  We keep them around because:
#
#   1. `gpgme_decrypt` currently won't work with passphrase protected keys
#   2. These legacy functions don't rely on gpgme or pygpgme
#
# Note that unlocking passphrase protected keys is very finicky, as newer
# versions of gpg/gpgme (2.1/1.4) insist on involving pinentry and gpg-agent,
# while older versions won't accept the config/arguments that allow unlocking
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
    Encrypt a message using gpg in a subprocess.

    :type message: bytes or str
    :param message: Message to encrypt (str is encoded as UTF-8)

    :param str keyid:
        Key id or fingerprint of recipient (multiple recipients not supported)

    :param str gnupghome:
        GnuPG homedir (default: ``cereconf.GNUPGHOME``)

    :returns: ASCII-armored encrypted ciphertext
    :rtype: str

    :raises IOError: on missing key or other GPG errors
    """
    message_bytes = text_compat.to_bytes(message, "utf-8")
    cmd = _get_gpg_cmd(keyid, gnupghome, '--encrypt', '--armor',
                       '--recipient', keyid)
    output_bytes = _filtercmd(cmd, message_bytes)
    return output_bytes.decode("ascii")


@deprecate('use gpgme_decrypt()')
def legacy_gpg_decrypt(message, keyid, passphrase=None, gnupghome=None):
    """
    Decrypt a message using gpg in a subprocess.

    :type message: bytes or str
    :param message: GPG ciphertext to decrypt

    :param str keyid:
        Default key for gpg (historical, not actually used for decryption)

    :param str passphrase:
        Passphrase for unlocking the private key.  Note: won't work with
        gpg 2.1+ without ``--pinentry-mode loopback`` and
        ``allow-loopback-pinentry`` in gpg-agent.conf.

    :param str gnupghome:
        GnuPG homedir (default: ``cereconf.GNUPGHOME``)

    :rtype: bytes
    :returns: The decrypted data.

    :raises IOError: on missing key or other GPG errors
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
