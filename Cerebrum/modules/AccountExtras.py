# -*- coding: utf-8 -*-
#
# Copyright 2004-2025 University of Oslo, Norway
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
Useful account logic mixins.

This module currently only provides one extra mixin, the
:class:`.AutoPriorityAccountMixin`.

Configuration
=============
``cereconf.ACCOUNT_PRIORITY_RANGES``
    The account priority ranges for :class:`.AutoPriorityAccountMixin`.  This
    value maps affiliation/status to (min-priority, max-priority) tuples.  Note
    that all values in the mapping should have fallback values (``"*"``).
    Example:
    ::

        ACCOUNT_PRIORITY_RANGES = {
            "ANSATT": {
                "tekadm": (100, 200),
                "*": (200, 300),
            },
            "*": {
                "*": (300, 400),
            },
        }
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import six

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Account


class AutoPriorityAccountMixin(Account.Account):
    """
    Provide configurable account priority ranges.

    This mixin can help set a default priority based on various account types
    (rather than just auto-incrementing a priority value for secondary
    accounts).  The account priority ranges are set by
    ``cereconf.ACCOUNT_PRIORITY_RANGES``.
    """

    def set_account_type(self, ou_id, affiliation, priority=None):
        if priority is None:
            priority = self._calculate_account_priority(ou_id, affiliation)
        return self.__super.set_account_type(ou_id, affiliation, priority)

    def _calculate_account_priority(self, ou_id, affiliation,
                                    current_pri=None):
        # Determine the status this affiliation resolves to
        if self.owner_id is None:
            raise ValueError("non-owned account can't have account_type")
        person = Factory.get('Person')(self._db)
        status = None
        for row in person.list_affiliations(person_id=self.owner_id,
                                            include_deleted=True):
            if row['ou_id'] == ou_id and row['affiliation'] == affiliation:
                status = six.text_type(
                    self.const.PersonAffStatus(row['status']).str)
                break
        if status is None:
            raise ValueError("Person %s don't have aff %s at ou_id %s"
                             % (self.owner_id, affiliation, ou_id))
        affiliation = six.text_type(
            self.const.PersonAffiliation(int(affiliation)))

        # Find the range that we resolve to
        pri_ranges = cereconf.ACCOUNT_PRIORITY_RANGES
        if not isinstance(pri_ranges, dict):
            return None
        if affiliation not in pri_ranges:
            affiliation = '*'
        if status not in pri_ranges[affiliation]:
            status = '*'
        pri_min, pri_max = pri_ranges[affiliation][status]

        if current_pri and pri_min <= current_pri < pri_max:
            # We have a current_pri, and the current_pri is in the
            # configured range
            return current_pri

        # Find taken values in this range and sort them
        taken = []
        for row in self.get_account_types(all_persons_types=True,
                                          filter_expired=False):
            taken.append(int(row['priority']))
        taken = [x for x in taken if x >= pri_min and x < pri_max]
        taken.sort()
        if (not taken):
            taken.append(pri_min)
        new_pri = taken[-1] + 2
        if new_pri < pri_max:
            return new_pri

        # In the unlikely event that the previous taken value was at the
        # end of the range
        new_pri = pri_max - 1
        while new_pri >= pri_min:
            if new_pri not in taken:
                return new_pri
            new_pri -= 1
        raise ValueError("No free priorities for that account_type!")
