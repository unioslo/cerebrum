#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

"""This Module ads expire_date and notification features to entity spreads.
"""


import sys

import mx.DateTime
from exceptions import Exception

import cerebrum_path
import cereconf

from Cerebrum.Utils import NotSet
from Cerebrum.Utils import Factory
from Cerebrum.modules.CLConstants import _ChangeTypeCode
from Cerebrum.Entity import EntitySpread
from Cerebrum import Errors

from Cerebrum.modules.no.uit.MailQ import MailQ


class UitEntitySpreadMixin(EntitySpread):

    """
    Mixin class that will extend EntitySpread funcionality.

    """

    def __init__(self, database):
        super(UitEntitySpreadMixin, self).__init__(database)
        self.db = database
        self.mailq = MailQ(database)

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

        # Delete spread expire entries
        self.execute("""
           DELETE FROM [:table schema=cerebrum name=spread_expire]
           WHERE entity_id=:e_id AND spread=:spread""", {'e_id': self.entity_id,
                                                         'spread': int(spread)})

        # Delete spread expire notification entries
        expire_policy = cereconf.SPREAD_EXPIRE_POLICY.get(spread)
        if expire_policy is not None and len(expire_policy) > 0:
            templates = []
            for (policy_days, policy_template) in expire_policy:
                templates.append("'" + policy_template + "'")
            templates = '(' + ','.join(templates) + ')'

            self.execute("""
               DELETE FROM [:table schema=cerebrum name=spread_expire_notification]
               WHERE entity_id=:e_id AND notify_template in %s""" % templates, {'e_id': self.entity_id})

        super(UitEntitySpreadMixin, self).delete_spread(spread)

    def set_spread_expire(self, spread, expire_date=None, entity_id=None):

        if entity_id is None:
            entity_id = self.entity_id

        if expire_date is None:
            expire_date = mx.DateTime.today()

        # Decides if an insert or update is needed
        sel_query = """
        SELECT CASE WHEN expire_date < :expire_date THEN '1' ELSE '0' END AS update FROM [:table schema=cerebrum name=spread_expire]
        WHERE entity_id=:entity_id AND spread=:spread_code
        """
        sel_binds = {'entity_id': entity_id,
                     'spread_code': spread,
                     'expire_date': expire_date}

        # Insert query
        ins_query = """
        INSERT INTO [:table schema=cerebrum name=spread_expire]
        (entity_id, spread, expire_date)
        VALUES (:entity_id, :spread_code, :expire_date)
        """
        ins_binds = {'entity_id': entity_id,
                     'spread_code': spread,
                     'expire_date': expire_date}

        # Update query
        upd_query = """
        UPDATE [:table schema=cerebrum name=spread_expire]
        SET expire_date=:expire_date
        WHERE entity_id=:entity_id AND spread=:spread_code
        """
        upd_binds = {'entity_id': entity_id,
                     'spread_code': spread,
                     'expire_date': expire_date}

        try:
            res = self.query_1(sel_query, sel_binds)
            if res == '1':
                res = self.execute(upd_query, upd_binds)
                self.logger.info(
                    "Updated expire_date on spread %s for account %s to %s" %
                    (spread, entity_id, expire_date))
                self.notify_spread_expire_reset(
                    spread,
                    expire_date,
                    entity_id=entity_id)
        except Errors.NotFoundError:
            res = self.execute(ins_query, ins_binds)
            self.logger.info(
                "Set expire_date on spread %s for account %s to %s" %
                (spread, entity_id, expire_date))

    def search_spread_expire(
            self, spread=None, expire_date=None, entity_id=None):
        where = []
        where_str = ''
        if expire_date is not None:
            where.append("expire_date >= :expire_date")
        if spread is not None:
            where.append("spread = :spread_code")
        if entity_id is not None:
            where.append("entity_id = :entity_id")
        if len(where) > 0:
            where_str = "WHERE " + " AND ".join(where)

        # Returns search result
        return self.query(
            """SELECT entity_id, spread, expire_date FROM [:table schema=cerebrum name=spread_expire] %s""" % (
                where_str),
            {'entity_id': entity_id,
             'spread_code': spread,
             'expire_date': expire_date})

    def notify_spread_expire_reset(self, spread, expire_date, entity_id=None):

        # Get notify reset template, if defined
        reset_template = cereconf.SPREAD_EXPIRE_POLICY_RESET.get(spread)
        if reset_template is None:
            return

        # Get the expire notification policy for current spread, if defined
        expire_policy = cereconf.SPREAD_EXPIRE_POLICY.get(spread)
        if expire_policy is None or len(expire_policy) == 0:
            return

        # Check if user has a pending spread expire notification for current
        # set of possible templates
        templates = []
        for (policy_days, policy_template) in expire_policy:
            templates.append("'" + policy_template + "'")
        templates = '(' + ','.join(templates) + ')'

        sel_query = """
            SELECT notify_date, notify_template FROM [:table schema=cerebrum name=spread_expire_notification]
            WHERE entity_id=:entity_id AND notify_template IN %s
            """ % templates
        sel_binds = {'entity_id': entity_id}

        try:
            res = self.query_1(sel_query, sel_binds)
        except Errors.NotFoundError:
            self.logger.info(
                "User %s has no pending spread %s expire notifications within templates %s to reset" %
                (entity_id, spread, templates))
            return

        (notify_date, notify_template) = res

        # Check if new expiry is sufficiently far ahead in time
        today = mx.DateTime.today()
        expire_date = mx.DateTime.DateFrom(expire_date)
        if expire_policy is not None and len(expire_policy) > 0:
            # Check if the longest expiry notification perios (always the
            # first) will catch up with new expire date immediately
            (policy_days, policy_template) = expire_policy[0]
            if expire_date <= today + mx.DateTime.DateTimeDelta(policy_days):
                self.logger.error(
                    "Expire date extended too little to avoid new expiry notification. entity_id: %s. spread: %s. Reset notification NOT sent." %
                    (entity_id, spread))
                return

        # If sending successful, delete pending notifications
        self.logger.info(
            "Spread notification reset message being sent. acc: %s  expire_date: %s  spread: %s  template: %s" %
            (entity_id, expire_date, spread, reset_template))
        template_params = {}
        if self.mailq.add(entity_id, reset_template, template_params):
            del_query = """
                 DELETE FROM [:table schema=cerebrum name=spread_expire_notification]
                 WHERE entity_id=:entity_id AND notify_template=:template
                 """
            del_binds = {'entity_id': entity_id,
                         'template': notify_template}
            self.execute(del_query, del_binds)
        return

    def notify_spread_expire(self, spread, expire_date, entity_id):

        # Get this spread's expire notification policy from cereconf
        expire_policy = cereconf.SPREAD_EXPIRE_POLICY.get(spread)
        if expire_policy is None or len(expire_policy) == 0:
            return

        # Check if user has a pending spread expire notification for current
        # set of possible templates
        notify_date = None
        notify_template = None

        templates = []
        for (policy_days, policy_template) in expire_policy:
            templates.append("'" + policy_template + "'")
        templates = '(' + ','.join(templates) + ')'

        sel_query = """
            SELECT notify_date, notify_template FROM [:table schema=cerebrum name=spread_expire_notification]
            WHERE entity_id=:entity_id AND notify_template IN %s
            """ % templates
        sel_binds = {'entity_id': entity_id}

        try:
            res = self.query_1(sel_query, sel_binds)
            (notify_date, notify_template) = res
        except Errors.NotFoundError:
            self.logger.info(
                "User %s has no pending spread %s expire notifications within templates %s to update" %
                (entity_id, spread, templates))

        # Decide what would be the next template to send out, and how many days
        # before expiry it should be sent
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
            if not found_match:
                self.logger.error(
                    "Inconsistent spread_expire content vs existing policies: entity_id: %s spread: %s" %
                    (entity_id, spread))
                return
            else:
                self.logger.info(
                    "Last spread notification policy already processed for spread %s for user %s. User is now awaiting spread deletion when due." %
                    (spread, entity_id))
                return
        elif mx.DateTime.DateFrom(expire_date) <= mx.DateTime.today() + mx.DateTime.DateTimeDelta(policy_days):

            account_expire_date = None
            # Instantiate entity and check that it is an account object.
            try:
                en = Factory.get('Entity')(self.db)
                en.find(entity_id)

                co = Factory.get('Constants')(self.db)
                valid_entity_types = [co.entity_account, ]

                if en.const.EntityType(en.entity_type) not in valid_entity_types:
                    self.logger.error(
                        "Invalid entity_type (%s) chosen for spread expire. entity_id: %s" %
                        (str(en.const.EntityType(en.entity_type)), entity_id))
                    raise

                ac = Factory.get('Account')(self.db)
                ac.find(entity_id)
                account_expire_date = ac.expire_date
            except Exception, e:
                self.logger.error(
                    "Failed setting expire date for entity_id %s. Error: %s" %
                    (entity_id, e))

            # If account expiry date equals spread expire date, don't send
            # notification. A general notification will be sent by a different
            # script.
            if expire_date is not None and account_expire_date is not None and mx.DateTime.DateFrom(account_expire_date) <= mx.DateTime.DateFrom(expire_date):
                self.logger.info(
                    "Will not send notification about spread expire for spread %s because the account %s expires the same day or before the spread." %
                    (spread, entity_id))
                return

            # Don't send two notifications the same day - it looks like
            # spamming. Instead let it pass, and it will be caught the next day
            if notify_date is not None and mx.DateTime.today() == mx.DateTime.DateFrom(notify_date):
                self.logger.info(
                    "Will not send notification about spread expire for spread %s because a similar template has already been sent to %s before today" %
                    (spread, entity_id))
                return

            self.logger.info(
                "Will send notification to user. acc: %s  expire_date: %s  spread: %s  template: %s" %
                (entity_id, expire_date, spread, policy_template))

            # If sending succeeded, update notification information
            template_params = {'expire_date': str(expire_date)[0:10]}
            if self.mailq.add(entity_id, policy_template, template_params):

                if notify_template is None:
                    # New notification
                    query = """
                      INSERT INTO [:table schema=cerebrum name=spread_expire_notification]
                          (entity_id, notify_date, notify_template) VALUES (:entity_id, now(), :template)"""
                    binds = {'entity_id': entity_id,
                             'template': policy_template}
                else:
                    # Updates notification (next level notification)
                    query = """
                      UPDATE [:table schema=cerebrum name=spread_expire_notification]
                      SET notify_template = :new_template, notify_date = now()
                      WHERE entity_id=:entity_id AND notify_template=:old_template"""
                    binds = {'entity_id': entity_id,
                             'old_template': notify_template,
                             'new_template': policy_template}

                self.execute(query, binds)
