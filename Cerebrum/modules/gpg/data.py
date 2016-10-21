#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 University of Oslo, Norway
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
"""Mixin for attaching GPG data to entities."""

from Cerebrum.Entity import Entity
from Cerebrum.modules.gpg.config import load_config
from Cerebrum.utils.gpg import gpgme_encrypt
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.Utils import argument_to_sql


class EntityGPGData(Entity):
    """Mixin for attaching GPG data to entities."""

    @property
    @memoize
    def _tag_to_recipients(self):
        """Fetch mapping from config and convert it to a dictionary.

        :returns: map from tag -> list of recipient key ids
        """
        config = load_config()
        return {x['tag']: x['recipients'] for x
                in config.tag_to_recipient_map}

    def add_gpg_data(self, tag, data):
        """Add GPG encrypted data for the current entity.

        :param str tag: Data tag
        :param str data: Raw payload

        :returns: The saved message IDs, if any
        :rtype: list of ints or empty list
        """
        message_ids = []
        recipients = self._tag_to_recipients.get(tag, None)
        if recipients is None:
            raise ValueError("Unknown GPG data tag {!r}".format(tag))
        for recipient in recipients:
            message = gpgme_encrypt(message=data,
                                    recipient_key_id=recipient)
            message_id = self.add_gpg_message(tag=tag,
                                              recipient=recipient,
                                              message=message)
            message_ids.append(message_id)
        return message_ids

    def remove_gpg_data_by_tag(self, tag):
        """Remove GPG encrypted data by tag for the current entity.

        :param tag: Tag for data to be removed
        :type tag: str or sequence thereof

        :returns: Number of deleted rows
        """
        where = []
        binds = {}
        where.append(
            argument_to_sql(self.entity_id, 'entity_id', binds, int))
        where.append(
            argument_to_sql(tag, 'tag', binds, str))
        sql = "DELETE FROM [:table schema=cerebrum name=entity_gpg_data] "
        sql += " WHERE " + " AND ".join(where)
        self.execute(sql, binds)
        return self._db.rowcount

    def delete(self):
        """Delete GPG data for the current entity."""
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=entity_gpg_data]
        WHERE entity_id = :entity_id
        """, {"entity_id": self.entity_id})
        super(EntityGPGData, self).delete()

    def add_gpg_message(self, tag, recipient, message):
        """Add a GPG encrypted message for the current entity.

        :param str tag: Data tag
        :param str recipient: Recipient key ID (40-bit fingerprint)
        :param str message: The encrypted message

        :returns: Message ID
        :rtype: int/long
        """
        message_id = int(self._db.nextval('gpg_message_id_seq'))
        return self.query_1(
            "INSERT INTO [:table schema=cerebrum name=entity_gpg_data] "
            "(message_id, entity_id, recipient, tag, message) "
            "VALUES (:message_id, :entity_id, :recipient, :tag, :message) "
            "RETURNING message_id",
            {'message_id': message_id,
             'entity_id': int(self.entity_id),
             'recipient': recipient,
             'tag': tag,
             'message': message})

    def remove_gpg_message(self, message_id):
        """Remove GPG message(s) by message ID.

        :param message_id: Message ID(s) to be removed
        :type message_id: int or sequence thereof

        :returns: Number of deleted rows
        """
        binds = {}
        where = [argument_to_sql(message_id, 'message_id', binds, int)]
        sql = "DELETE FROM [:table schema=cerebrum name=entity_gpg_data] "
        sql += " WHERE " + " AND ".join(where)
        self.execute(sql, binds)
        return self._db.rowcount

    def search_gpg_data(self, message_id=None, entity_id=None, tag=None,
                        recipient=None, latest=False):
        """Search for GPG messages.

        :param message_id: Message ID(s)
        :type message_id: int or a seqence thereof

        :param entity_id: Entity ID(s)
        :type entity_id: int or a sequence thereof

        :param tag: Tag
        :type tag: str or a sequence thereof

        :param recipient: Recipient key ID(s)
        :type recipient: str or a sequence thereof

        :returns: list of db rows
        """
        tables = []
        where = []
        binds = {}
        tables.append("[:table schema=cerebrum name=entity_gpg_data]")

        if message_id is not None:
            where.append(
                argument_to_sql(message_id, 'message_id', binds, int))

        if entity_id is not None:
            where.append(
                argument_to_sql(entity_id, 'entity_id', binds, int))

        if tag is not None:
            where.append(
                argument_to_sql(tag, 'tag', binds, str))

        if recipient is not None:
            where.append(
                argument_to_sql(recipient, 'recipient', binds, str))

        sql = "SELECT * FROM {}".format(','.join(tables))
        if where:
            sql += " WHERE " + " AND ".join(where)
        if latest:
            sql += " ORDER BY created DESC LIMIT 1"
        return self.query(sql, binds)
