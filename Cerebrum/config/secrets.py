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
Setting for providing secrets in configuration files.

This Configuration/Setting is provides input to :mod:`Cerebrum.utils.secrets`


TBD
----
Does this belong in ``Cerebrum.utils.secrets``?


Example
-------
A short example to show how :class:`.Secret` can be used:

::

    # Define configuration
    class MyConfig(Configuration):

        username = ConfigDescriptor(String)
        password = ConfigDescriptor(Namespace, config=Secret)

    # Provide configuration values
    config = MyConfig({
        'username': 'Foo',
        'password': {'source': 'file', 'value': '/etc/secret_password'},
    })

    # Fetch secret from configuration.
    password = get_secret(config.password)
"""
import six

from Cerebrum.utils import secrets

from .configuration import Configuration, ConfigDescriptor
from .settings import Choice, String


class Secret(Configuration):
    """
    Reuseable configuration for an application secret.

    This should be used to configure ``Cerebrum.utils.secrets``

    Examples:

        {'source': 'plaintext', 'value': 'hunter2'}
        {'source': 'file': 'value': '/etc/pki/tls/private/my.key'}
        {'source': 'legacy_file': 'value': 'AzureDiamond@example.org'}
    """

    source = ConfigDescriptor(
        Choice,
        choices=six.viewkeys(secrets.sources),
        doc='Secret type (how the secret is represented)',
    )

    value = ConfigDescriptor(
        String,
        doc='Secret value (where the secret is defined)',
    )


def get_secret(secret_config):
    """ Get password using a Secret configuration. """
    return secrets.get_secret(secret_config.source,
                              secret_config.value)


if __name__ == '__main__':
    print(Secret.documentation())
