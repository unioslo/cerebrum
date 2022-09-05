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
Setting for providing secrets in configuration files.

This Configuration/Setting is provides input to :mod:`Cerebrum.utils.secrets`

Example
-------
A short example to show how :class:`.Secret` can be used:

::

    # Define configuration
    class MyConfig(Configuration):

        username = ConfigDescriptor(String)
        password = ConfigDescriptor(Secret)

    # Provide configuration values
    config = MyConfig({
        'username': 'Foo',
        'password': 'file:/etc/secret_password',
    })

    # Fetch secret from configuration.
    password = get_secret_from_string(config.password)
"""
from __future__ import print_function

import six

from Cerebrum.utils import secrets

from .settings import Setting


class Secret(Setting):
    """
    Reuseable configuration for an application secret.

    This should be used to configure ``Cerebrum.utils.secrets``.  Should be
    formatted as ``<source>:<source-args>``.

    Examples:

        'plaintext:hunter2'
        'file:/etc/pki/tls/private/my.key'
        'legacy-file:AzureDiamond@example.org'
    """

    _valid_types = six.string_types

    def validate(self, value):
        """Validates a value.

        :see: Setting.validate

        :raises ValueError:
            If the string value does not pass the configured regex, or is
            shorter or longer than the specified limits.
        """
        # Note: Take care not to expose the raw value in error messages
        #
        # Parent (Setting) only checks type, doesn't include value in exception
        # messages.
        if super(Secret, self).validate(value):
            return True

        # validate format
        source, arg = secrets.split_secret_string(value)

        # validate source value
        secrets.get_handler(source)

        return False

    @property
    def doc_struct(self):
        return super(Secret, self).doc_struct


# for backwards compatibility
get_secret_from_string = secrets.get_secret_from_string


if __name__ == '__main__':
    print(__doc__.strip())
    print()
    print('Setting:', Secret().doc)
