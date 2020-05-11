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
