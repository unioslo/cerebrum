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
"""
Accessors for the mod_gpg tables.
"""
import logging

import six

from Cerebrum import DatabaseAccessor
from Cerebrum import Entity
from Cerebrum.Utils import argument_to_sql
from Cerebrum.utils.funcwrap import memoize

from .config import GpgEncrypter, load_config


logger = logging.getLogger(__name__)


class GpgData(DatabaseAccessor.DatabaseAccessor):
    """
    Basic access to the mod_gpg tables.

    Messages can be accessed either by message_id, or by (entity_id, tag,
    recipient). In the latter case, multiple messages may exist, but only the
    latest should be used.
    """

    # columns and column ordering
    columns = (
        'message_id',
        'entity_id',
        'tag',
        'recipient',
        'created',
        'message',
    )

    def add_message(self, entity_id, tag, recipient, encrypted):
        """
        Add a new gpg encrypted message.

        :param entity_id:
            an entity to bind the message to
        :param tag:
            a tag used to identify the message
        :param recipient:
            the recipient key id that the message is encrypted for
        :param encrypted:
            the encrypted message or data

        :return:
            all columns of the inserted message
        """
        message_id = self._db.nextval('gpg_message_id_seq')
        binds = {
            'message_id': int(message_id),
            'entity_id': int(entity_id),
            'tag': six.text_type(tag),
            'recipient': six.text_type(recipient),
            'message': six.text_type(encrypted),
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=entity_gpg_data]
            (message_id, entity_id, tag, recipient, message)
          VALUES
            (:message_id, :entity_id, :tag, :recipient, :message)
          RETURNING
            {columns}
        """.format(columns=', '.join(self.columns))
        return self.query_1(stmt, binds)

    def get_message_by_id(self, message_id):
        """
        Find a message by its message_id.

        :param message_id: unique message_id
        :return: all columns of the message
        """
        binds = {
            'message_id': int(message_id),
        }
        stmt = """
          SELECT
            {columns}
          FROM
            [:table schema=cerebrum name=entity_gpg_data]
          WHERE
            message_id = :message_id
        """.format(columns=', '.join(self.columns))
        return self.query_1(stmt, binds)

    def delete_message_by_id(self, message_id):
        """
        Delete a message by its message_id.

        :param message_id: unique message_id
        :return: all columns of the deleted message
        """
        binds = {
            'message_id': int(message_id),
        }
        stmt = """
          DELETE FROM
            [:table schema=cerebrum name=entity_gpg_data]
          WHERE
            message_id = :message_id
          RETURNING
            {columns}
        """.format(columns=', '.join(self.columns))
        return self.query_1(stmt, binds)

    def delete(self, entity_id=None, tag=None, recipient=None):
        """
        Delete messages for some given entities, tags, or recipients.

        :param entity_id:
            an entity_id or sequence of entity_ids to delete messages for
        :param tag:
            a tag or sequence of tags to delete messages for
        :param recipient:
            a recipient or sequence of recipients to delete messages for

        :return:
            rows of deleted messages
        """
        binds = {}
        conds = []

        if not any((entity_id, tag, recipient)):
            raise TypeError('No argument given (expected at least one)')

        if entity_id is not None:
            conds.append(
                argument_to_sql(entity_id, 'entity_id', binds, int))
        if tag is not None:
            conds.append(
                argument_to_sql(tag, 'tag', binds, six.text_type))
        if recipient is not None:
            conds.append(
                argument_to_sql(recipient, 'recipient', binds, six.text_type))

        stmt = """
          DELETE FROM
            [:table schema=cerebrum name=entity_gpg_data]
          WHERE
            {where}
          RETURNING
            {columns}
        """.format(where=' AND '.join(conds),
                   columns=', '.join(self.columns))
        return self.query(stmt, binds)

    def search(self, entity_id=None, tag=None, recipient=None,
               message_id=None):
        """
        Find messages for some given entities, tags, or recipients.

        :param entity_id:
            an entity_id or sequence of entity_ids to find
        :param tag:
            a tag or sequence of tags to find
        :param recipient:
            a recipient or sequence of recipients to find
        :param message_id:
            a message_id or sequence of message_ids to find

        :return:
            rows of matching messages.

            Messages are ordered by entity_id, tag, recipient, created.
        """
        binds = {}
        conds = []

        if entity_id is not None:
            conds.append(
                argument_to_sql(entity_id, 'entity_id', binds, int))

        if tag is not None:
            conds.append(
                argument_to_sql(tag, 'tag', binds, six.text_type))

        if recipient is not None:
            conds.append(
                argument_to_sql(recipient, 'recipient', binds, six.text_type))

        if message_id is not None:
            conds.append(
                argument_to_sql(message_id, 'message_id', binds, int))

        stmt = """
          SELECT
            {columns}
          FROM
            [:table schema=cerebrum name=entity_gpg_data]
          {where}
          ORDER BY
            entity_id, tag, recipient, created DESC
        """.format(where='WHERE ' + ' AND '.join(conds) if conds else '',
                   columns=', '.join(self.columns))
        return self.query(stmt, binds)


class EntityMixin(Entity.Entity):
    """
    A mixin that implements mod_gpg cleanup for entities.
    """

    def delete(self):
        gpg_data = GpgData(self._db)
        gpg_data.delete(entity_id=self.entity_id)
        return super(EntityMixin, self).delete()


class EntityGPGData(EntityMixin):
    """Mixin for attaching GPG data to entities."""

    @property
    @memoize
    def _gpg_encrypter(self):
        """ encryption config for add_gpg_data() """
        config = load_config()
        return GpgEncrypter(config)

    def add_gpg_data(self, tag, data):
        """Add GPG encrypted data for the current entity.

        :param str tag: Data tag
        :param str data: Raw payload

        :returns: The saved message IDs, if any
        :rtype: list of ints or empty list
        """
        gpg_data = GpgData(self._db)
        message_ids = []
        for t, r, m in self._gpg_encrypter.encrypt_message(tag, data):
            row = gpg_data.add_message(entity_id=self.entity_id,
                                       tag=t, recipient=r, encrypted=m)
            message_ids.append(row['message_id'])
        return message_ids

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
        # TODO: We should replace use of this method with:
        # - gpg_data.search()
        # - a dedicated method that implements search for the latest entry for
        #   a given (entity_id, tag, recipient) tuple
        gpg_data = GpgData(self._db)
        result = list(
            gpg_data.search(
                message_id=message_id,
                entity_id=entity_id,
                tag=tag,
                recipient=recipient))
        if latest:
            return result[:1]
        else:
            return result
