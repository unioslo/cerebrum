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
"""This module defines all necessary config for the GPG data module"""
from __future__ import absolute_import, unicode_literals

from Cerebrum.config.configuration import (ConfigDescriptor,
                                           Configuration)
from Cerebrum.config.loader import read, read_config
from Cerebrum.config.settings import Iterable
from Cerebrum.utils.gpg import gpgme_encrypt


class GPGDataConfig(Configuration):
    """ Configuration for the GPG data handler """

    tag_to_recipient_map = ConfigDescriptor(
        Iterable,
        default=[],
        doc='A mapping from tag to one or more recipient fingerprints')


def load_config(filepath=None):
    """ Loads and validates the GPG data configuration. """
    config_cls = GPGDataConfig()
    if filepath:
        config_cls.load_dict(read_config(filepath))
    else:
        read(config_cls, 'gpg_data')
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

        :param tag: message tag
        :param plaintext: the raw data to encrypt

        :return:
            a generator that yields tuples with:
            (tag, recipient, encrypted message)
        """
        for recipient in self.get_recipients(tag):
            encrypted = gpgme_encrypt(message=plaintext,
                                      recipient_key_id=recipient)
            yield tag, recipient, encrypted
