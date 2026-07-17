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
This module defines all necessary config for the GPG data module.

Configuration
--------------
The :class:`.GpgEncrypter` tries to encrypt data for one or more *tag*.

Each *tag* can be mapped to a preset list of recipients in a
:class:`.GPGDataConfig`.  This config is usually read from a `gpg_data.yml` (or
`gpg_data.json`) using :func:`.load_config`.

Example `gpg_data.yml`:
::

    tag_to_recipient_map:
      - tag: foo
        recipients:
          - 0123456789ABCDEF0123456789ABCDEF01234567
          - 76543210FEDCBA9876543210FEDCBA9876543210
      - tag: bar
        recipients:
          - 0123456789ABCDEF0123456789ABCDEF01234567
      - tag: baz
        recipients:
          - 76543210FEDCBA9876543210FEDCBA9876543210


Each *tag* are usually tied to a specific set of functionality elsewhere in
Cerebrum.  Look for places where the GpgEncrypter is used.  One notable example
is the :meth:`.data.EntityGPGData.add_gpg_data` mixin method.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.config import configuration
from Cerebrum.config import loader
from Cerebrum.config import settings
from Cerebrum.utils.gpg import gpgme_encrypt


class GPGDataConfig(configuration.Configuration):
    """
    Configuration for the GPG data handler.

    This config maps *tags* to list of recipient key fingerprints.
    """

    tag_to_recipient_map = configuration.ConfigDescriptor(
        settings.Iterable,
        default=[],
        doc='A mapping from tag to one or more recipient fingerprints',
    )


def load_config(filepath=None):
    """ Loads and validates the GPG data configuration. """
    config_cls = GPGDataConfig()
    if filepath:
        config_cls.load_dict(loader.read_config(filepath))
    else:
        loader.read(config_cls, 'gpg_data')
    config_cls.validate()
    return config_cls


class GpgEncrypter(object):
    """
    Helper object to encrypt a message according to config.

    This object provides helper methods that supplements the config with:

    - tag to recipient (key id) lookup
    - encrypt message for all configured recipients for a given tag
    """

    def __init__(self, config):
        self.config = config

    @property
    def recipient_map(self):
        """ tag to recipients map from config.  """
        return {x['tag']: x['recipients']
                for x in self.config.tag_to_recipient_map}

    def get_recipients(self, tag):
        """
        Get recipients for a given tag.

        :param tag: a tag to get recipients for

        :return: a list of recipients (gpg key ids)

        :raises: ValueError if the tag is invalid
        """
        recipients = self.recipient_map.get(tag)

        if recipients is None:
            raise ValueError("Unknown GPG data tag {!r}".format(tag))

        return recipients

    def encrypt_message(self, tag, plaintext):
        """
        Encrypt a plaintext for each recipient for a given tag.

        :param str tag: message tag
        :param plaintext: the raw data to encrypt

        :return:
            a generator that yields tuples with:
            (tag, recipient, encrypted message)
        """
        for recipient in self.get_recipients(tag):
            encrypted = gpgme_encrypt(message=plaintext,
                                      recipient_key_id=recipient)
            yield tag, recipient, encrypted
