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
Adds spread expire notifications.
"""
import logging

import mx.DateTime

import cereconf

from Cerebrum.modules import spread_expire
from Cerebrum.Utils import Factory
from Cerebrum.modules.mailq import MailQueueDb, MailQueueEntry

logger = logging.getLogger(__name__)


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


class UitEntitySpreadMixin(spread_expire.EntitySpreadMixin):

    def __init__(self, database):
        super(UitEntitySpreadMixin, self).__init__(database)
        self._spread_notify_db = spread_expire.SpreadExpireNotify(database)
        self._mailq = MailQueueDb(database)

    def delete_spread(self, spread):
        # Delete spread expire notification entries
        templates = [t for _, t in get_expire_policy(spread)]
        if templates:
            self._spread_notify_db.delete(
                entity_id=self.entity_id,
                notify_template=templates)

        super(UitEntitySpreadMixin, self).delete_spread(spread)

    def set_spread_expire(self, spread, expire_date=None, entity_id=None):
        """
        Set expire date for a given spread.
        """
        if entity_id is None:
            entity_id = self.entity_id
        if expire_date is None:
            expire_date = mx.DateTime.today()

        needs_reset = self._spread_expire_db.exists(entity_id, spread)
        super(UitEntitySpreadMixin, self).set_spread_expire(spread,
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
