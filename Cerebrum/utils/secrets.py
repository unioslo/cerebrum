# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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


@sources.register('auth_file')
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


@sources.register('legacy_file')
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
    return sources[source](value)


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
