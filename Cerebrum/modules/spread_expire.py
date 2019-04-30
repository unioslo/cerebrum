#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2019 University of Oslo, Norway
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
Implementation of mod_spread_expire

This module adds expire_date to entity spreads, and a notification feature to
inform users that gets a spread revoked.
"""
import logging

import mx.DateTime
import six

import cereconf

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Entity import EntitySpread
from Cerebrum.Utils import Factory, argument_to_sql
from Cerebrum.modules.mailq import MailQueueDb, MailQueueEntry

logger = logging.getLogger(__name__)


class SpreadExpire(DatabaseAccessor):
    """
    Access to the spread_expire table.

    TODO: We assume a (entity_id, spread) primary key, but no such constraint
    exists in the database - this may fail horribly if anything else modifies
    that table.
    """

    def __insert(self, entity_id, spread, expire_date):
        """
        Insert a new row in the spread_expire table.
        """
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
            'expire_date': expire_date,
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=spread_expire]
            (entity_id, spread, expire_date)
          VALUES
            (:entity_id, :spread, :expire_date)
        """
        logger.debug('inserting spread_expire entity_id=%r spread=%r',
                     entity_id, spread)
        self.execute(stmt, binds)

    def __update(self, entity_id, spread, expire_date):
        """
        Update an existing row in the spread_expire table.
        """
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
            'expire_date': expire_date,
        }
        stmt = """
          UPDATE [:table schema=cerebrum name=spread_expire]
          SET expire_date = :expire_date
          WHERE
            entity_id = :entity_id AND
            spread = :spread
        """
        logger.debug('updating spread_expire entity_id=%r spread=%r',
                     entity_id, spread)
        self.execute(stmt, binds)

    def exists(self, entity_id, spread):
        """
        """
        if not entity_id or not spread:
            raise ValueError("missing args")
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
        }
        stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=spread_expire]
            WHERE
              entity_id = :entity_id AND
              spread = :spread
          )
        """
        return self.query_1(stmt, binds)

    def get(self, entity_id, spread):
        """
        """
        if not entity_id or not spread:
            raise ValueError("missing args")
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
        }
        stmt = """
          SELECT expire_date
          FROM [:table schema=cerebrum name=spread_expire]
          WHERE
            entity_id = :entity_id AND
            spread = :spread
        """
        return self.query_1(stmt, binds)

    def set(self, entity_id, spread, expire_date):
        """
        Add or update a spread expire date.
        """
        try:
            old_date = self.get(entity_id, spread)
            is_new = False
        except Errors.NotFoundError:
            old_date = None
            is_new = True

        if not is_new and old_date == expire_date:
            logger.debug(
                'No change in spread_expire for entity_id=%r spread=%r',
                entity_id, spread)
            return

        if is_new:
            self.__insert(entity_id, spread, expire_date)
        else:
            self.__update(entity_id, spread, expire_date)

    def delete(self, entity_id, spread):
        """
        Delete a spread expire date.
        """
        if not self.exists(entity_id, spread):
            raise Errors.NotFoundError(
                "No spread expire date for entity_id=%r spread=%r" %
                (entity_id, spread))
        binds = {
            'entity_id': int(entity_id),
            'spread': int(spread),
        }
        stmt = """
          DELETE FROM
            [:table schema=cerebrum name=spread_expire]
          WHERE
            entity_id = :entity_id AND
            spread = :spread
        """
        logger.debug('Deleting spread_expire entity_id=%r spread=%r',
                     entity_id, spread)
        self.execute(stmt, binds)

    def search(self, entity_id=None, spread=None, before_date=None,
               after_date=None, fetchall=False):
        """
        """
        filters = []
        binds = dict()

        if entity_id:
            filters.append(
                argument_to_sql(entity_id, 'entity_id', binds, int))
        if spread:
            filters.append(
                argument_to_sql(spread, 'spread', binds, int))

        if before_date is not None:
            binds['before_date'] = before_date
            filters.append('expire_date < :before_date')

        if after_date is not None:
            binds['after_date'] = before_date
            filters.append('expire_date > :after_date')

        where = ('WHERE ' + ' AND '.join(filters)) if filters else ''

        stmt = """
          SELECT entity_id, spread, expire_date
          FROM [:table schema=cerebrum name=spread_expire]
          {where}
        """.format(where=where)
        return self.query(stmt, binds)


class SpreadExpireNotify(DatabaseAccessor):
    """
    Access to the spread_expire_notification table.

    TODO: We assume a (entity_id, notify_template) primary key, but no such
    constraint exists in the database - this may fail horribly if anything else
    modifies that table.
    """

    def __insert(self, entity_id, notify_template, notify_date=None):
        """
        Insert a new row in the spread_expire_notification.
        """
        binds = {
            'entity_id': int(entity_id),
            'notify_template': six.text_type(notify_template),
            'notify_date': notify_date,
        }
        stmt = """
          INSERT INTO [:table schema=cerebrum name=spread_expire_notification]
            (entity_id, notify_template, notify_date)
          VALUES
            (:entity_id, :notify_template, :notify_date)
        """
        logger.debug('inserting spread_expire_notification for entity_id=%r'
                     ' template=%r', entity_id, notify_template)
        self.execute(stmt, binds)

    def __update(self, entity_id, notify_template, notify_date):
        """
        Update an existing row in the spread_expire_notification table.
        """
        binds = {
            'entity_id': int(entity_id),
            'notify_template': six.text_type(notify_template),
            'notify_date': notify_date,
        }

        stmt = """
          UPDATE [:table schema=cerebrum name=spread_expire_notification]
          SET notify_date = :notify_date
          WHERE
            entity_id = :entity_id AND
            notify_template = :notify_template
        """
        logger.debug('updating spread_expire_notification for entity_id=%r'
                     ' template=%r', entity_id, notify_template)
        self.execute(stmt, binds)

    def exists(self, entity_id, notify_template=None):
        """
        """
        if not entity_id:
            raise ValueError("missing entity_id")
        binds = {
            'entity_id': int(entity_id),
        }
        if notify_template:
            template_cond = 'AND ' + argument_to_sql(
                notify_template, 'notify_template', binds, six.text_type)
        else:
            template_cond = ''
        stmt = """
          SELECT EXISTS (
            SELECT 1
            FROM [:table schema=cerebrum name=spread_expire_notification]
            WHERE entity_id = :entity_id
            {filters}
          )
        """.format(filters=template_cond)
        return self.query_1(stmt, binds)

    def get(self, entity_id, notify_template):
        """
        """
        if not entity_id or not notify_template:
            raise ValueError("missing args")
        binds = {
            'entity_id': int(entity_id),
            'notify_template': six.text_type(notify_template),
        }
        stmt = """
          SELECT notify_date
          FROM [:table schema=cerebrum name=spread_expire_notification]
          WHERE
            entity_id = :entity_id AND
            notify_template = :notify_template
        """
        return self.query_1(stmt, binds)

    def set(self, entity_id, notify_template, notify_date=None):
        """
        Add or update a spread expire notification.
        """
        is_new = self.exists(entity_id, notify_template)

        if is_new:
            self.__insert(entity_id, notify_template, notify_date)
        else:
            self.__update(entity_id, notify_template, notify_date)

    def delete(self, entity_id=None, notify_template=None):
        """
        Delete spread expire notifications.
        """
        binds = {}
        conditions = []
        if entity_id is not None:
            conditions.append(
                argument_to_sql(entity_id, 'entity_id', binds, int))
        if notify_template is not None:
            conditions.append(
                argument_to_sql(notify_template, 'notify_template', binds,
                                six.text_type))
        stmt = """
          DELETE FROM
            [:table schema=cerebrum name=spread_expire_notification]
          {filters}
        )
        """.format(filters=(('WHERE ' + ' AND '.join(conditions))
                            if conditions else ''))
        logger.debug('deleting spread_expire_notification for entity_id=%r'
                     ' template=%r', entity_id, notify_template)
        self.execute(stmt, binds)

    def search(self, entity_id=None, notify_template=None, before_date=None,
               after_date=None, fetchall=False):
        """
        """
        filters = []
        binds = dict()

        if entity_id:
            filters.append(
                argument_to_sql(entity_id, 'entity_id', binds, int))
        if notify_template:
            filters.append(
                argument_to_sql(notify_template, 'notify_template', binds,
                                six.text_type))

        if before_date is not None:
            binds['before_date'] = before_date
            filters.append('notify_date < :before_date')

        if after_date is not None:
            binds['after_date'] = before_date
            filters.append('notify_date > :after_date')

        where = ('WHERE ' + ' AND '.join(filters)) if filters else ''

        stmt = """
          SELECT entity_id, notify_template, notify_date
          FROM [:table schema=cerebrum name=spread_expire_notification]
          {where}
        """.format(where=where)
        return self.query(stmt, binds)


class UitEntitySpreadMixin(EntitySpread):
    """
    Mixin class that will extend EntitySpread funcionality.
    """

    def __init__(self, database):
        super(UitEntitySpreadMixin, self).__init__(database)
        self._spread_expire_db = SpreadExpire(database)

    def delete(self):
        """Delete an entity's spreads."""
        for s in self.get_spread():
            self.delete_spread(s['spread'])
        super(UitEntitySpreadMixin, self).delete()

    def add_spread(self, spread):
        """Add ``spread`` to this entity."""
        self.set_spread_expire(int(spread))
        super(UitEntitySpreadMixin, self).add_spread(spread)

    def delete_spread(self, spread):
        """Remove ``spread`` from this entity."""
        self._spread_expire_db.delete(self.entity_id, spread)
        super(UitEntitySpreadMixin, self).delete_spread(spread)

    def set_spread_expire(self, spread, expire_date=None, entity_id=None):
        """
        Set expire date for a given spread.
        """

        if entity_id is None:
            entity_id = self.entity_id

        if expire_date is None:
            expire_date = mx.DateTime.today()
        self._spread_expire_db.set(entity_id, spread, expire_date)

    def search_spread_expire(self, spread=None, expire_date=None,
                             entity_id=None):
        return list(
            self._spread_expire_db.search(
                entity_id=entity_id,
                spread=spread,
                after_date=expire_date,
            ))


def to_date(obj):
    if obj is None:
        return None
    else:
        return mx.DateTime.DateFrom(obj)


def to_delta(obj):
    if obj is None:
        return None
    else:
        return mx.DateTime.DateTimeDelta(obj)


def get_expire_policy(spread):
    """
    Get spread policy for a given spread.

    :rtype: list
    :return: A list with (num_days, template) pairs
    """
    policy_db = getattr(cereconf, 'SPREAD_EXPIRE_POLICY', {})
    policies = [
        (to_delta(days), template)
        for days, template in policy_db.get(spread, ())]
    if not policies:
        logger.debug('No spread expire policy for spread=%s', repr(spread))
    return policies


def get_reset_policy(spread):
    """
    Get spread reset policy for a given spread.

    :rtype: str
    :return: A reset template.
    """
    policy_db = getattr(cereconf, 'SPREAD_EXPIRE_POLICY_RESET', {})
    policy = policy_db.get(spread, None)
    if not policy:
        logger.debug('No spread reset policy for spread=%s', repr(spread))
    return policy


class UitNotifySpreadMixin(UitEntitySpreadMixin):

    def __init__(self, database):
        super(UitNotifySpreadMixin, self).__init__(database)
        self._spread_notify_db = SpreadExpireNotify(database)
        self._mailq = MailQueueDb(database)

    def delete_spread(self, spread):
        # Delete spread expire notification entries
        templates = [t for _, t in get_expire_policy(spread)]
        if templates:
            self._spread_notify_db.delete(
                entity_id=self.entity_id,
                notify_template=templates)

        super(UitNotifySpreadMixin, self).delete_spread(spread)

    def set_spread_expire(self, spread, expire_date=None, entity_id=None):
        """
        Set expire date for a given spread.
        """
        if entity_id is None:
            entity_id = self.entity_id
        if expire_date is None:
            expire_date = mx.DateTime.today()

        needs_reset = self._spread_expire_db.exists(entity_id, spread)
        super(UitNotifySpreadMixin, self).set_spread_expire(spread,
                                                            expire_date,
                                                            entity_id)
        if needs_reset:
            self.notify_spread_expire_reset(spread, expire_date,
                                            entity_id=entity_id)

    def notify_spread_expire_reset(self, spread, expire_date, entity_id=None):
        # Get notify reset template, if defined
        reset_template = get_reset_policy(spread)
        if not reset_template:
            return

        # Get the expire notification policy for current spread, if defined
        expire_policy = get_expire_policy(spread)
        if not expire_policy:
            return

        # Check if user has a pending spread expire notification for current
        # set of possible templates
        templates = [t for _, t in expire_policy]
        entries = self._spread_notify_db.search(entity_id=entity_id,
                                                notify_template=templates)

        if not entries:
            logger.info(
                "User %s has no pending spread %s expire notifications "
                "within templates %s to reset",
                entity_id, spread, templates)
            return

        today = mx.DateTime.today()
        for _, notify_template, notify_date in entries:
            # Check if new expiry is sufficiently far ahead in time
            expire_date = to_date(expire_date)

            # Check if the longest expiry notification perios (always the
            # first) will catch up with new expire date immediately
            (policy_days, policy_template) = expire_policy[0]
            if expire_date <= (today + policy_days):
                logger.error(
                    "Expire date extended too little to avoid new expiry "
                    "notification. entity_id: %s. spread: %s. Reset "
                    "notification NOT sent.",
                    entity_id, spread)
                continue

            # If sending successful, delete pending notifications
            logger.info(
                "Spread notification reset message being sent. acc: %s "
                "expire_date: %s  spread: %s  template: %s",
                entity_id, expire_date, spread, reset_template)
            template_params = {}
            self._mailq.store(
                MailQueueEntry(
                    entity_id,
                    template=reset_template,
                    parameters=template_params))
            self._spread_notify_db.delete(entity_id,
                                          notify_template=notify_template)

    def notify_spread_expire(self, spread, expire_date, entity_id):
        # Get this spread's expire notification policy from cereconf
        expire_policy = get_expire_policy(spread)
        if not expire_policy:
            return

        # Check if user has a pending spread expire notification for current
        # set of possible templates
        notify_date = None
        notify_template = None

        templates = [t for _, t in expire_policy]
        entries = self._spread_notify_db.search(entity_id=entity_id,
                                                notify_template=templates)

        if not entries:
            logger.info(
                "User %s has no pending spread %s expire notifications "
                "within templates %s to update",
                entity_id, spread, templates)
            return

        today = mx.DateTime.today()
        for _, notify_template, notify_date in entries:
            notify_date = to_date(notify_date)
            # Decide what would be the next template to send out, and how many
            # days before expiry it should be sent
            policy_days = None
            policy_template = None
            found_match = False
            if notify_template is None:
                found_match = True
                (policy_days, policy_template) = expire_policy[0]
            else:
                for (aux_policy_days, aux_policy_template) in expire_policy:
                    if found_match:
                        policy_days = aux_policy_days
                        policy_template = aux_policy_template
                        break
                    if aux_policy_template == notify_template:
                        found_match = True

            if policy_days is None or policy_template is None:
                if found_match:
                    logger.info(
                        "Last spread notification policy already processed "
                        "for spread %s for user %s. User is now awaiting "
                        "spread deletion when due.",
                        spread, entity_id)
                else:
                    logger.error(
                        "Inconsistent spread_expire content vs existing "
                        "policies: entity_id: %s spread: %s",
                        entity_id, spread)
                return

            if expire_date > (today + policy_days):
                return

            account_expire_date = None
            # Instantiate entity and check that it is an account object.
            try:
                en = Factory.get('Entity')(self._db)
                en.find(entity_id)

                co = Factory.get('Constants')(self._db)
                valid_entity_types = [co.entity_account, ]

                if (en.const.EntityType(en.entity_type) not in
                        valid_entity_types):
                    logger.error(
                        "Invalid entity_type (%s) chosen for spread expire. "
                        "entity_id: %s",
                        str(en.const.EntityType(en.entity_type)), entity_id)
                    raise

                ac = Factory.get('Account')(self._db)
                ac.find(entity_id)
                account_expire_date = ac.expire_date
            except Exception as e:
                logger.error(
                    "Failed setting expire date for entity_id %s. Error: %s",
                    entity_id, e)

            # If account expiry date equals spread expire date, don't send
            # notification. A general notification will be sent by a different
            # script.
            if (expire_date is not None and account_expire_date is not None and
                    mx.DateTime.DateFrom(account_expire_date) <=
                    mx.DateTime.DateFrom(expire_date)):
                logger.info(
                    "Will not send notification about spread expire for "
                    "spread %s because the account %s expires the same "
                    "day or before the spread.",
                    spread, entity_id)
                return

            # Don't send two notifications the same day - it looks like
            # spamming. Instead let it pass, and it will be caught the next day
            if (notify_date is not None and
                    mx.DateTime.today() == mx.DateTime.DateFrom(notify_date)):
                logger.info(
                    "Will not send notification about spread expire for "
                    "spread %s because a similar template has already "
                    "been sent to %s before today",
                    spread, entity_id)
                return

            logger.info(
                "Will send notification to user. acc: %s "
                "expire_date: %s spread: %s  template: %s",
                entity_id, expire_date, spread, policy_template)

            # If sending succeeded, update notification information
            template_params = {'expire_date': str(expire_date)[0:10]}
            self._mailq.store(
                MailQueueEntry(
                    entity_id,
                    template=policy_template,
                    parameters=template_params))

            self._spread_notify_db.set(
                entity_id=entity_id,
                notify_template=policy_template,
                notify_date='[:now]',
            )
