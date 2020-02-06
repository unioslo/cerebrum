#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2020 University of Oslo, Norway
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
"""Utilities for encrypting and decrypting GPG messages via GPGME."""
import io
import logging
import subprocess

import gpgme
import six

import cereconf
from .funcwrap import deprecate

logger = logging.getLogger(__name__)


def _unicode2str(obj, encoding='utf-8'):
    """Encode unicode object to a str with the given encoding."""
    if isinstance(obj, unicode):
        return obj.encode(encoding)
    return obj


def get_gpgme_context(ascii_armor=True, gnupghome=None):
    """Creates a gpgme context.

    :param ascii_armor: use ascii armor
    :type ascii_armor: bool

    :param gnupghome: GnuPG home directory
    :type gnupghome: str

    :returns: a gpgme context
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

    :param message: the message that is to be encrypted
    :type message: str or unicode
    :param recipient_key_id: the private key id
    :type recipient_key_id: str or unicode
    :param context: set to use alternative gpgme context
    :type context: gpgme.Context or None

    :returns: the encrypted message (ciphertext)
    :rtype: str

    May throw a gpgme.GpgmeError. Should be handled by the caller.

    The private key id is used by pygpgme to determine which public key
    to use for encryption.
    'gpg2 -k --fingerprint' can be used to list all available public keys
    in the current GnuPG database, along with their fingerprints.
    Possible values:
    uid: (f.i. "Cerebrum Test <cerebrum@uio.no>")
    key-id: (f.i. "FEAC69E4")
    fingerprint (recommended): (f.i.'78D9E8FEB39594D4EAB7A9B85B17D23FFEAC69E4')
    """
    context = context or get_gpgme_context()
    recipient_key = context.get_key(recipient_key_id)
    plaintext = io.BytesIO(_unicode2str(message))
    ciphertext = io.BytesIO()
    context.encrypt([recipient_key], 0, plaintext, ciphertext)
    return ciphertext.getvalue()


def gpgme_decrypt(ciphertext, context=None):
    """
    Decrypts a ciphertext using GnuPG (pygpgme).

    :param ciphertext: the ciphertext that is to be decrypted
    :type ciphertext: str

    :param context: set to use alternative gpgme context
    :type context: gpgme.Context or None

    :returns: the decrypted ciphertext (message)
    :rtype: str

    May throw a gpgme.GpgmeError. Should be handled by the caller.

    Just like GnuPG, pygpgme extracts the private key corresponding to the
    ciphertext (encrypted message) automatically from the local
    GnuPG key database situated in cereconf.GNUPGHOME or the provided context.
    """
    context = context or get_gpgme_context()
    ciphertext = io.BytesIO(ciphertext)
    plaintext = io.BytesIO()
    context.decrypt(ciphertext, plaintext)
    return plaintext.getvalue()


# _filtercmd, legacy_gpg_encrypt and legacy_gpg_decrypt was moved from
# Cerebrum.Utils and modernized a bit. The only reason they are kept around is
# that gpgme_decrypt() currently won't work with passphrase protected keys.
#
# Note that unlocking passphrase protected keys is very finicky, as newer
# versions of gpg/gpgme (2.1/1.4) insists on involving pinentry and gpg-agent,
# while older versions won't accept the config/arguments that allows unlocking
# these keys using the loopback pinentry-mode.


def _filtercmd(cmd, input_data):
    """Send input on stdin to a command and collect the output from stdout.

    :param cmd:
        a sequence of arguments, where the first element is the full path to
        the command

    :param input_data:
        data to be sent on stdin to the executable

    :return:
        stdout from command

    :raises IOError:
        throws an IOError if the command exits with an error code.

    Example use:

    >>> _filtercmd(["sed", "s/kak/ost/"], "kakekake")
    'ostekake'

    """

    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=False,
    )
    if isinstance(input_data, six.text_type):
        input_data = input_data.encode('utf-8')

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

    :param message:
        message to encrypt

    :param keyid:
        key to use for encryption

    :param gnupghome:
        gpg homedir - defaults to cereconf.GNUPGHOME

    :return:
        encrypted message (ascii armor)

    :raises IOError:
        May raise an IOError if encryption fails.
    """
    cmd = _get_gpg_cmd(keyid, gnupghome, '--encrypt', '--armor',
                       '--recipient', keyid)
    return _filtercmd(cmd, message)


@deprecate('use gpgme_decrypt()')
def legacy_gpg_decrypt(message, keyid, passphrase=None, gnupghome=None):
    """
    Decrypts a message using gpg in a subprocess.

    ..warning::

        Passphrase will not work with gpg 2.1/gpgme 1.4: gpg requires a
        '--pinentry-mode loopback' option and 'allow-loopback-pinentry' in
        gpg-agent.conf, which is not supported in 2.0

    :param message:
        gpg encrypted message to decrypt

    :param keyid:
        key to use for decryption

    :param passphrase:
        passphrase for unlocking private key

    :param gnupghome:
        gpg homedir - defaults to cereconf.GNUPGHOME

    :return:
        decrypted message

    :raises IOError:
        May raise an IOError if decryption fails.
    """
    if passphrase:
        pass_opts = ('--passphrase-fd', '0')
        message = passphrase + "\n" + message
    else:
        pass_opts = ()

    cmd = _get_gpg_cmd(keyid, gnupghome, '--decrypt', *pass_opts)
    return _filtercmd(cmd, message)
