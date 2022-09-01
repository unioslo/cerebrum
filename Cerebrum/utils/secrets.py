# -*- coding: utf-8 -*-
#
# Copyright 2020-2022 University of Oslo, Norway
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
# Copyright 2002-2015 University of Oslo, Norway
"""
Utilities for fetching passwords and other secrets.

This module contains *handlers* for various sources of secret/protected
information, like passwords or keys.  Each *handler* takes a single argument,
but some sources may require many arguments to be serialized into a single
argument string (e.g. legacy-file).


Sources
-------
file
    Specify the full path to a file with secret data. Trailing newlines are
    removed.  Example argument: ``/path/to/file``

auth-file
    Specify a filename in the ``cereconf.DB_AUTH_DIR`` directory.  Trailing
    newlines are removed.  Example argument: ``passwd-example-file``

legacy-file
    Specify a password to retrieve from ``cereconf.DB_AUTH_DIR`` using the same
    parameters as the legacy ``read_password`` function.

    Note that legacy files contain both a username (for sanity check) and a
    password, separated by a tab character.  This means that passord files
    formatted for legacy-file cannot be fetched using e.g. ``auth-file``
    without further processing.

    Example arguments:

    - ``user@system`` (looks up ``<DB_AUTH_DIR>/passwd-user@system``)
    - ``user@system@host`` (looks up ``<DB_AUTH_DIR>/passwd-user@system@host``)

plaintext
    Provide a plaintext secret, as is.  Useful in configuration files where
    providing the plaintext secret is OK (e.g. mock values for tests).  Example
    argument: ``hunter2``.


To look up a given secret using a given source:

>>> get_secret('plaintext', 'hunter2')
'hunter2'


Secret strings
--------------
Secret strings makes it possible to encode *source* and a *source-argument* as
a single string value, with format ``<source>:<source-argument>``.

This is typically used in config files to allow multiple types of lookup of
secrets.  Example:

>>> config = {"user": "AzureDiamond", "pass": "plaintext:hunter2"}
>>> get_secret_from_string(config["pass"])
'hunter2'

Note that the *source-argument* may contain ``:`` characters:

>>> get_secret_from_string("plaintext::foo:bar:)
':foo:bar:'


TODO
----
- Move ``Cerebrum.Utils.read_password`` here, and deprecate
  ``Cerebrum.Utils.read_password``.

"""
import io
import os

import cereconf

from Cerebrum.utils.mappings import DecoratorMap
from Cerebrum.Utils import read_password


sources = DecoratorMap()


@sources.register('file')
def _read_secret_file(value):
    """
    Read secret from file.

    This assumes that the file is an utf-8 encoded file on disk.

    :param str value:
        Filename for fetching a secret.
    """
    with io.open(value, mode='r', encoding='utf8') as f:
        return f.read().rstrip('\n')


@sources.register('auth-file')
def _read_secret_auth_file(value):
    """
    Read secret from file in ``cereconf.DB_AUTH_DIR``.

    Otherwise exactly like :func:`._read_secret_file`

    :param str value:
        Filename for fetching a secret.
    """
    filename = os.path.join(cereconf.DB_AUTH_DIR, value)
    with io.open(filename, mode='r', encoding='utf8') as f:
        return f.read().rstrip('\n')


@sources.register('legacy-file')
def _read_legacy_password_file(value):
    """
    Read a legacy password file.

    The value should follow the format ``<user>@<system>[@<host>]``.  The
    secret itself is fetched using :func:`Cerebrum.Utils.read_password`, which
    looks up a passwd-* file in ``cereconf.DB_AUTH_DIR``.
    """
    parts = value.split('@')

    def _pop(default):
        try:
            return parts.pop(0)
        except IndexError:
            return default

    return read_password(user=_pop(''), system=_pop(''), host=_pop(None))


sources.register('plaintext')(lambda s: s)


def get_handler(source):
    """
    Fetch a given source handler.

    :param source:
        One of the methods for fetching a secret (as provided by ``sources``).

    :rtype: callable
    """
    if source not in sources:
        raise ValueError("Invalid source %s, must be one of %s"
                         % (repr(source), repr(tuple(sources))))
    return sources[source]


def get_secret(source, value):
    """
    Fetch a secret from a given source.

    :param source:
        One of the methods for fetching a secret (as provided by ``sources``).

    :param value:
        A string argument to pass to the given ``source``.

    :rtype: str
    :returns: Returns a matching secret
    """
    handler = get_handler(source)
    return handler(value)


def split_secret_string(raw_value):
    """
    Split raw secrets string value into (source, args) tuple.

    :param raw_value: A text string with format "<source>:<value>".

    :rtype: tuple
    :returns: Returns a pair with "<source>" and "<value>"
    """
    source, sep, source_arg = raw_value.partition(':')
    if not sep:
        # Missing mandatory ':' separator
        raise ValueError("Invalid format, must be '<source>:<secret>'")
    return source, source_arg


def get_secret_from_string(raw_value):
    """
    Lookup secret from "<source>:<args>" string.

    :rtype: str
    :returns: The secret from the given source
    """
    source, arg = split_secret_string(raw_value)
    return get_secret(source, arg)


def _main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'source',
        choices=sorted(tuple(sources)),
    )
    parser.add_argument(
        'value',
    )

    args = parser.parse_args()

    print(get_secret(args.source, args.value))


if __name__ == '__main__':
    _main()
